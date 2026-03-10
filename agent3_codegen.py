from google import genai
import config
import os
import json
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

from qgis.core import QgsApplication, QgsProcessingFeedback

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
        
        self.client = genai.Client(api_key=api_key)
        self.model_name = "gemini-2.5-flash"

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
    import sys, os, QgsApplication, qgs.initQgis(), import processing...

YOUR JOB: write ONLY the task-specific code block below:

TASK:
- Algorithm: {algo}
- Description: {description}
- Input files (relative paths from project root): {inputs}
- Output file (relative path from project root): {output}
- Suggested Parameters (from schematizer): {json.dumps(params_dict, indent=2)}

TECHNICAL REFERENCE (PyQGIS Algorithms/Parameters):
{context}

RULES:
1. DO NOT import QgsApplication, initQgis, or exitQgis. They are handled.
2. Use processing.run("{algo}", params, feedback=feedback) — use EXACTLY the algorithm id from the task. Always pass feedback=feedback.
3. Use exact parameter names from the TECHNICAL REFERENCE.
4. For Enum parameters, use the INTEGER INDEX from the Options listed in the reference.
5. For Extent parameters, load the input layer and format as: 
   f"{{ext.xMinimum()}},{{ext.xMaximum()}},{{ext.yMinimum()}},{{ext.yMaximum()}} [EPSG:4326]"
6. FILE PATHS: Input/output paths are relative to the project root. DO NOT prepend os.path.dirname(__file__). Use `os.path.abspath('path')` directly. 
7. If the output file is successfully created, you MUST print exactly: print("SUCCESS")
8. Output ONLY the Python code block (no markdown fences).
"""


        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            task_body = extract_python_code(response.text)

            # ── Assemble the full script ────────────────────────────────────
            # Wrap the task body in a try/finally so exitQgis is always called.
            indented_body = "\n".join(
                "    " + line for line in task_body.splitlines()
            )
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
