import subprocess
import os
import sys
import json
from google import genai
import config

from data_manager import DataManager
from extract_python_code import extract_python_code
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

class Agent4Debugger:
    def __init__(self, log_callback=None):
        self.qgis_python = config.QGIS_PYTHON_EXECUTABLE
        self.data_manager = DataManager()
        self.log_callback = log_callback # For GUI updates
        
        # Configure Gemini for debugging
        self.genai_client = genai.Client(api_key=config.GEMINI_API_KEY)
        self.model_name = "gemini-2.5-flash"
        
        # Load vector store for PyQGIS algorithm knowledge (RAG)
        try:
            self.embedding_model = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
            self.vectorstore = FAISS.load_local(
                "agent2_knowledge_base", self.embedding_model, 
                allow_dangerous_deserialization=True)
            self.retriever = self.vectorstore.as_retriever(search_kwargs={"k": 5})
            print("Debugger: Loaded QGIS Knowledge Base for RAG.")
        except Exception as e:
            print(f"Debugger: Knowledge Base not found or error loading ({e}).")
            self.retriever = None
        self.qgis_python = config.QGIS_PYTHON_EXECUTABLE
        self.data_manager = DataManager()
        self.log_callback = log_callback # For GUI updates
        
        # Configure Gemini for debugging
        self.genai_client = genai.Client(api_key=config.GEMINI_API_KEY)
        self.model_name = "gemini-2.5-flash"

    def _log(self, message, category="info"):
        if self.log_callback:
            self.log_callback(message, category)
        print(f"[{category.upper()}] {message}")
        
    def sync_inputs(self, input_files):
        """Downloads input files from Supabase if not present locally."""
        for file_path in input_files:
            # Handle relative paths, assume they are in DATA_DIR
            filename = os.path.basename(file_path)
            local_path = os.path.join(config.DATA_DIR, filename)
            
            if not os.path.exists(local_path):
                self._log(f"Downloading input: {filename}", "sync")
                self.data_manager.download_file(filename, config.DATA_DIR)
            else:
                self._log(f"Input exists locally: {filename}", "sync-ok")

    def sync_output(self, output_file):
        """Uploads output file to Supabase."""
        if not output_file: 
            return

        filename = os.path.basename(output_file)
        local_path = os.path.join(config.DATA_DIR, filename) # Outputs usually goto DATA_DIR or OUTPUT_DIR? 
        # Adjust based on where scripts write. Scripts usually write to config.OUTPUT_DIR or config.DATA_DIR 
        # For simplicity, let's look in both or assume absolute path from script
        
        if not os.path.exists(local_path):
            # Try config.OUTPUT_DIR
            local_path = os.path.join(config.OUTPUT_DIR, filename)

        if os.path.exists(local_path):
            self._log(f"Uploading output: {filename}", "sync")
            self.data_manager.upload_file(local_path, filename)
        else:
            self._log(f"Output file not found for upload: {output_file}", "warning")

    def debug_code(self, code, error_log, step_data=None):
        """Uses LLM to fix the code based on the error log and plan context."""
        step_info = ""
        context = ""
        
        if step_data:
            algo_id = step_data.get('algorithm_id') or step_data.get('algorithm', '')
            step_info = f"""
        PLAN CONTEXT (STRICTLY USE THESE FILENAMES):
        - Step ID: {step_data.get('step_id')}
        - Algorithm: {algo_id}
        - Inputs: {step_data.get('input_files')}
        - Expected Output: {step_data.get('output_file')}
        - Suggested Parameters: {json.dumps(step_data.get('parameters', {}), indent=2)}
        """
            # Retrieve technical context for the specific algorithm
            if self.retriever and algo_id:
                try:
                    query = f"PyQGIS algorithm {algo_id}"
                    docs = self.retriever.invoke(query)
                    context = "\n\n".join([d.page_content[:1000] for d in docs])
                except Exception as e:
                    print(f"Debugger Retrieval failed: {e}")

        prompt = f"""
        You are a PyQGIS debugger. Fix the following QGIS 3.40.8 script based on the error.
        
        {step_info}

        TECHNICAL REFERENCE (PyQGIS Algorithms/Parameters):
        {context}

        IMPORTANT RULES:
        1. The script runs via `python-qgis-ltr.bat` (QGIS paths already configured).
        2. The header (QgsApplication init, initQgis, import processing) is CORRECT. Do NOT change import order.
        3. STRICT FILENAME RULE: DO NOT use generic names like "input.tif". 
           ONLY use the paths provided in the PLAN CONTEXT above.
        4. Fix ONLY: wrong algorithm IDs, wrong parameter names, missing output dirs, logic bugs.
        5. Use exact parameter names from the TECHNICAL REFERENCE.
        6. For Enum parameters, use the INTEGER INDEX from the Options listed in the reference.
        7. For Extent parameters, load the input layer and format as: 
           f"{{ext.xMinimum()}},{{ext.xMaximum()}},{{ext.yMinimum()}},{{ext.yMaximum()}} [EPSG:4326]"
        8. FILE PATHS: Input/output paths are relative to the project root. DO NOT prepend os.path.dirname(__file__). Use `os.path.abspath('path')` directly. 
        9. If the output file is successfully created, you MUST print exactly: print("SUCCESS")
        10. Output ONLY the fixed Python code (no markdown fences).
        11. RASTER DIMENSION MISMATCH FIX: If the error is "Dimensions of file X are different from other files":
            - BEFORE running gdal:rastercalculator, align all secondary input rasters (INPUT_B, INPUT_C, ...) to match INPUT_A.
            - Load INPUT_A as a QgsRasterLayer to get its extent, CRS, and pixel resolution.
            - Use processing.run("gdal:warpreproject", ...) on each secondary raster with:
              TARGET_CRS matching INPUT_A, TARGET_EXTENT matching INPUT_A's extent string,
              TARGET_RESOLUTION matching INPUT_A's rasterUnitsPerPixelX(), RESAMPLING=0.
            - Then use the aligned raster paths in the gdal:rastercalculator parameters.
        12. NEVER CREATE DUMMY DATA. If an input file is missing, do NOT create fake/dummy layers.
            Instead, raise an error so the pipeline can fail properly.
        13. POLYGONIZE FIELD: 'gdal:polygonize' ALWAYS creates field 'DN'. Downstream filters must use FIELD='DN'.
        14. For 'gdal:cliprasterbymasklayer', ONLY use: INPUT, MASK, CROP_TO_CUTLINE=True, KEEP_RESOLUTION=True, OUTPUT. No other params.
        15. For 'gdal:rastercalculator', always use parameter name 'FORMULA' (never 'EXPRESSION'). Syntax: '*' for AND, '==' for equals.

        Error Log:
        {error_log[:3000]}

        Broken Script:
        {code}
        """


        
        try:
            response = self.genai_client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            return extract_python_code(response.text)
        except Exception as e:
            print(f"Debugger LLM failed: {e}")
            return code # Return original if fix fails

    def _check_success(self, result, output_file):
        """Strict success check: stdout must say SUCCESS and output file must exist.
        
        QGIS_ERROR / QGIS_WARNING lines are GDAL/QGIS feedback messages, NOT Python errors.
        They do NOT mean the step failed. Only a Python Traceback in stderr, or the absence
        of the word SUCCESS in stdout, constitutes a real failure.
        """
        stdout = result.stdout or ""
        stderr = result.stderr or ""

        # A Python Traceback in stderr = real crash
        if "Traceback" in stderr:
            return False

        # Script must have explicitly printed SUCCESS
        if "SUCCESS" not in stdout:
            return False

        # Output file must actually exist on disk
        if output_file:
            local_path = output_file if os.path.isabs(output_file) else os.path.join(config.BASE_DIR, output_file)
            if not os.path.exists(local_path):
                self._log(f"Output file not found on disk: {local_path}", "warning")
                return False

        return True


    def run_step(self, script_path, step_data=None, max_retries=3):
        """Executes a script with retries and debugging."""
        input_files = step_data.get("input_files", []) if step_data else []
        output_file = step_data.get("output_file") if step_data else None

        # 1. Sync Inputs from Supabase if missing locally
        self.sync_inputs(input_files)

        
        # Read original code
        with open(script_path, "r") as f:
            current_code = f.read()

        for attempt in range(max_retries + 1):
            self._log(f"Executing Step (Attempt {attempt+1}/{max_retries+1})...", "exec")
            
            env = os.environ.copy()
            env['CPL_LOG'] = 'ERROR' # Suppress GDAL noise
            
            result = subprocess.run(
                [self.qgis_python, script_path],
                capture_output=True,
                text=True,
                cwd=config.BASE_DIR,  # Run from project root so relative paths work
                env=env
            )
            
            success = self._check_success(result, output_file)
            
            if success:
                self._log("Step executed successfully.", "success")
                if result.stdout: self._log(result.stdout, "stdout")
                self.sync_output(output_file)
                return True
            else:
                self._log("Step execution failed.", "error")
                if result.stdout: self._log(result.stdout, "stdout")
                if result.stderr: self._log(result.stderr, "stderr")
                
                if attempt < max_retries:
                    self._log("Attempting to debug and fix code...", "debug")
                    error_log = f"{result.stdout}\n{result.stderr}"
                    fixed_code = self.debug_code(current_code, error_log, step_data=step_data)

                    
                    if fixed_code and fixed_code != current_code:
                        current_code = fixed_code
                        with open(script_path, "w") as f:
                            f.write(current_code)
                        self._log("Script updated with fix.", "debug-fix")
                    else:
                        self._log("Debugger could not produce a better script.", "warning")
                        break
                else:
                    self._log("Max retries reached.", "critical")

        return False

import re
def extract_python_code(text):
    match = re.search(r'```python\n(.*?)\n```', text, re.DOTALL)
    if match:
        return match.group(1)
    return text