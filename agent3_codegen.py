from google import genai
import config
import os
import json
import textwrap
from langchain_huggingface import HuggingFaceEmbeddings

from langchain_community.vectorstores import FAISS
from extract_python_code import extract_python_code

# ─── Hardcoded QGIS boilerplate header ────────────────────────────────────────
# sys.path must include python/plugins BEFORE importing processing.
# The `processing` plugin lives in: <QGIS>/apps/qgis-ltr/python/plugins/processing
# python-qgis-ltr.bat does NOT always add the plugins directory to sys.path.
QGIS_HEADER = r"""import sys
import os

QGIS_INSTALL_PATH = r"C:\Program Files\QGIS 3.40.8\apps\qgis-ltr"

# Add QGIS Python dirs to sys.path (must be done before any qgis imports)
sys.path.insert(0, os.path.join(QGIS_INSTALL_PATH, "python"))
sys.path.insert(0, os.path.join(QGIS_INSTALL_PATH, "python", "plugins"))

from qgis.core import (
    QgsApplication, 
    QgsProcessingFeedback, 
    QgsVectorLayer, 
    QgsRasterLayer,
    QgsProject,
    QgsCoordinateReferenceSystem
)

# Initialize QGIS (headless mode)
qgs = QgsApplication([], False)
qgs.setPrefixPath(QGIS_INSTALL_PATH, True)
qgs.initQgis()

# Import processing AFTER initQgis and path setup
import processing
from processing.core.Processing import Processing
Processing.initialize()
from qgis.analysis import QgsNativeAlgorithms
QgsApplication.processingRegistry().addProvider(QgsNativeAlgorithms())

# Custom feedback class to capture internal QGIS C++ errors
class LoggingFeedback(QgsProcessingFeedback):
    def reportError(self, error, fatalError=False):
        print(f"QGIS_ERROR: {error}", flush=True)
    def pushWarning(self, warning):
        print(f"QGIS_WARNING: {warning}", flush=True)
    def pushInfo(self, info):
        print(f"QGIS_INFO: {info}", flush=True)
    def pushDebugInfo(self, info):
        pass  # Suppress debug noise

feedback = LoggingFeedback()
"""

QGIS_FOOTER = r"""
finally:
    qgs.exitQgis()
"""

class Agent3CodeGen:
    def __init__(self):
        api_key = config.GEMINI_API_KEY
        if not api_key:
            raise ValueError("Gemini API Key not found in config")
        
        self.model_name = "gemini-2.0-flash" # Use 2.0 for coding stability
        self.client = genai.Client(api_key=api_key)

        # Load vector store for PyQGIS code patterns (RAG)
        try:
            self.embedding_model = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
            self.vectorstore = FAISS.load_local(
                "agent2_knowledge_base", self.embedding_model,
                allow_dangerous_deserialization=True)
            self.retriever = self.vectorstore.as_retriever(search_kwargs={"k": 5})
            print("✅ CodeGen: Loaded PyQGIS Knowledge Base for RAG.")
        except Exception as e:
            print(f"⚠️  CodeGen: Knowledge Base not available ({e}). Proceeding without RAG.")
            self.retriever = None

    def generate_code(self, step_data):
        """
        Generates a complete PyQGIS script for a single step.
        The QGIS boilerplate header is hardcoded and prepended; the LLM
        only generates the task-specific processing block.
        """
        description = step_data.get("description", "")
        algo        = step_data.get("algorithm_id") or step_data.get("algorithm", "")
        inputs      = step_data.get("input_files", [])
        output      = step_data.get("output_file", "")
        params_dict = step_data.get("parameters", {})


        # RAG Context retrieval
        context = ""
        if self.retriever:
            try:
                query   = f"PyQGIS algorithm {algo}: {description}"
                docs    = self.retriever.invoke(query)
                context = "\n\n".join([d.page_content[:1000] for d in docs])
                print(f"🔍 CodeGen: Retrieved {len(docs)} RAG snippets.")
            except Exception as e:
                print(f"⚠️  CodeGen RAG retrieval failed: {e}")

        # ── Ask the LLM only for the task body ──────────────────────────────
        # The header (QgsApplication init + processing import) is injected by us.
        prompt = f"""
You are a PyQGIS developer writing the TASK BODY of a headless QGIS script.

The script already has this boilerplate at the top (DO NOT repeat it):
    import sys, os, QgsApplication, QgsRasterLayer, QgsVectorLayer, processing...

YOUR JOB: write ONLY the task-specific code block below:

TASK:
- Algorithm: {algo}
- Description: {description}
- Input files (use these EXACT paths): {inputs}
- Output file (use this EXACT path): {output}
- Suggested Parameters (from schematizer): {json.dumps(params_dict, indent=2)}

TECHNICAL REFERENCE (PyQGIS Algorithms/Parameters):
{context}

RULES:
1. DO NOT import QgsApplication, initQgis, or exitQgis. They are handled.
2. Use processing.run("{algo}", params, feedback=feedback) — use EXACTLY the algorithm id from the task. Always pass feedback=feedback.
3. Use EXACT file paths provided in the TASK (e.g. {inputs}). NEVER use placeholders like '@step_01_output' or invent new filenames.
4. If you need to load a layer (e.g. to get its extent), use:
   layer = QgsVectorLayer(path, "name", "ogr") or QgsRasterLayer(path, "name")
5. Use exact parameter names from the TECHNICAL REFERENCE.
6. For Enum parameters, use the INTEGER INDEX from the Options listed in the reference.
7. FILE PATHS: Use absolute paths by doing: `os.path.abspath('path')`.
8. If the output file is successfully created, you MUST print exactly: print("SUCCESS")
9. Output ONLY the Python code block (no markdown fences).
10. CRITICAL: NEVER use the algorithm 'qgis:rastercalculator'. Use 'gdal:rastercalculator' instead.
    - gdal:rastercalculator FORMULA uses single letters (A, B, C...) for each input raster.
    - Parameters: INPUT_A=path_to_raster1, BAND_A=1, INPUT_B=path_to_raster2, BAND_B=1, FORMULA="(A<10)*(B<5)", OUTPUT=output_path
    - Example formula for flood risk: "(A<10)*(B<5)*(C==1)" where A=DEM, B=Slope, C=BufferRaster
11. For 'gdal:cliprasterbymasklayer', ONLY use these parameters: INPUT, MASK, CROP_TO_CUTLINE=True, KEEP_RESOLUTION=True, NODATA=None, ALPHA_BAND=False, OPTIONS='', OUTPUT.
    - Do NOT add SOURCE_CRS, TARGET_CRS, or TARGET_EXTENT — these cause 'Process returned error code 1'.
12. For 'gdal:rasterize', you MUST load a reference raster (e.g. the original DEM) to get its WIDTH, HEIGHT, and EXTENT.
    - EXTENT string format: f"{{ext.xMinimum()}},{{ext.xMaximum()}},{{ext.yMinimum()}},{{ext.yMaximum()}} [EPSG:4326]"
    - Parameters: INPUT, BURN=1, UNITS=0 (Pixels), WIDTH=width, HEIGHT=height, EXTENT=extent_str, DATA_TYPE=0 (Byte), OUTPUT.
13. For 'gdal:rastercalculator', use single letters A, B, C... as variables in the FORMULA.
14. CRITICAL: Start all top-level code (like params = { ... }) at column 0 (NO INDENTATION).
15. CRITICAL: For 'gdal:rastercalculator' with MULTIPLE input rasters (INPUT_A + INPUT_B, etc.):
    - The rasters MUST have IDENTICAL pixel dimensions (width x height). gdal_calc.py will CRASH if they differ even by 1 pixel.
    - BEFORE running the raster calculator, you MUST align all secondary rasters (B, C, ...) to match raster A.
    - Do this by loading raster A with QgsRasterLayer, extracting its extent and size, then using processing.run("gdal:warpreproject", ...) on each secondary raster to match:
      ```
      ref = QgsRasterLayer(input_a_path, "ref")
      ext = ref.extent()
      extent_str = f"{{ext.xMinimum()}},{{ext.xMaximum()}},{{ext.yMinimum()}},{{ext.yMaximum()}} [{{ref.crs().authid()}}]"
      aligned = processing.run("gdal:warpreproject", {{
          'INPUT': input_b_path,
          'TARGET_CRS': ref.crs().authid(),
          'TARGET_EXTENT': extent_str,
          'TARGET_RESOLUTION': ref.rasterUnitsPerPixelX(),
          'RESAMPLING': 0,
          'OUTPUT': aligned_b_path
      }}, feedback=feedback)
      ```
    - Then use the aligned raster as INPUT_B in the calculator.
"""

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            # Remove any markdown fences or extraneous whitespace
            task_body = extract_python_code(response.text).strip()

            # ── Assembly ──────────────────────────────────────────────────
            # Indent the task body correctly for the try: block
            indented_body = textwrap.indent(task_body, "    ")
            
            full_script = (
                QGIS_HEADER
                + "\ntry:\n"
                + indented_body
                + "\nfinally:\n"
                + "    qgs.exitQgis()\n"
            )
            return full_script

        except Exception as e:
            print(f"Error generating code: {e}")
            return ""


if __name__ == "__main__":
    agent = Agent3CodeGen()
    code = agent.generate_code({
        "description": "Fill NoData values in the DEM",
        "algorithm": "gdal:fillnodata",
        "input_files": ["data/kerala_dem.tif"],
        "output_file": "outputs/step_01_filled_dem.tif"
    })
    print(code)
