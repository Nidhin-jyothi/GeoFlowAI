import os
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import SentenceTransformerEmbeddings
from langchain_community.document_loaders import UnstructuredFileLoader
from langchain.text_splitter import CharacterTextSplitter
from groq import Groq
from langchain.chains import RetrievalQA
from groq import Groq
from langchain.schema import Document
import google.generativeai as genai
import json
from run_all_steps import run_qgis_steps
from extract_python_code import extract_python_code 


# Load vectorstore
embedding_model = SentenceTransformerEmbeddings(model_name="all-MiniLM-L6-v2")
vectorstore = FAISS.load_local("qgis_knowledge_base", embedding_model, allow_dangerous_deserialization=True)

#load data schema
with open("data_schema.json", "r") as f:
    data_schema = json.load(f)  

# Load code plan
with open("code_plan_test.json", "r") as f:
    code_plan = json.load(f)

query = "QGIS geoprocessing task: " + code_plan[0]["description"]

# Use Maximal Marginal Relevance (MMR) retriever
retriever = vectorstore.as_retriever(
    search_type="similarity",
    search_kwargs={"k": 5}
)

description = code_plan[0]["description"]
# Retrieve top docs
relevant_docs = retriever.get_relevant_documents(query)

context = "\n\n".join([doc.page_content for doc in relevant_docs])

'''
# Display full content of all retrieved documents
print(f"\n Query: {query}\n")
for i, doc in enumerate(relevant_docs):
    print(f" Doc {i+1} (source: {doc.metadata.get('source', 'Unknown')}):\n{doc.page_content}\n{'-'*80}")
'''

# --- Setup Gemini 1.5 Flash ---
genai.configure(api_key="AIzaSyDsNq_Ibw8f1tFuOMZJ6TWYE2n4rnNa_a0")  # 🔐 Replace with your API key
model = genai.GenerativeModel("gemini-1.5-flash-latest")

# --- Construct Prompt ---
prompt = f"""
You are a professional Python geospatial developer working in a Windows environment using QGIS 3.40.8 with PyQGIS and the GDAL/OGR processing toolbox. Your goal is to generate a complete and runnable Python script that can be executed headlessly in this QGIS environment.

## SYSTEM ENVIRONMENT:
- QGIS Version: 3.40.8 (LTR)
- Python runs via batch automation using OSGEO4W shell.
- PyQGIS is initialized in headless (offscreen) mode with the following:
  - QGIS_PREFIX_PATH = "C:/Program Files/QGIS 3.40.8/apps/qgis-ltr"
  - Required paths are inserted into `sys.path`.
  - All native and GDAL processing providers are registered via:
    `QgsApplication.processingRegistry().addProvider(QgsNativeAlgorithms())`
    and `processing.core.Processing.Processing.initialize()`.
- The script will be executed in a **Windows environment** with QGIS 3.40.8 installed.
- The script will be launched via:
  `"C:/Program Files/QGIS 3.40.8/bin/python-qgis-ltr.bat"`

- Make sure the script runs in **headless mode**, without GUI dependencies.    

## TASK:
{description}

## INPUT DATA SCHEMA:
{json.dumps(data_schema, indent=2)}

## INPUT FILE CONSTRAINTS:
- Use these exact paths:
  - Raster: `C:/QGIS_Auto/data/kerala_dem.tif`
  - Vector: `C:/QGIS_Auto/data/gadm41_IND_1.shp`
- The vector file includes a "NAME_1" field to filter for Kerala.

## OUTPUT:
- Save clipped raster to: `C:/QGIS_Auto/data/clipped_dem.tif`

## IMPORTANT INSTRUCTIONS:
- strcitly All required QGIS Python and plugin paths must be included for imports like `processing` to work as this

  import os
  import sys
  from qgis.core import (
    QgsApplication,
    QgsVectorLayer,
    QgsRasterLayer,
    QgsProcessingFeedback,
    QgsCoordinateReferenceSystem,
    QgsPointXY,
    QgsGeometry
  )

  # Initialize QGIS in headless mode
  qgs = QgsApplication([], False)
  qgs.setPrefixPath("C:/Program Files/QGIS 3.40.8/apps/qgis-ltr", True)
  qgs.initQgis()

  # Add necessary paths to sys.path
  sys.path.append("C:/Program Files/QGIS 3.40.8/apps/qgis-ltr/python/plugins")

  from qgis.analysis import QgsNativeAlgorithms
  import processing

- Use `processing.run()` with algorithms like `"gdal:cliprasterbymasklayer"` or `"qgis:cliprasterbymasklayer"`.
- Always check if input files exist using `os.path.exists(...)`.
- Load vector layers using `QgsVectorLayer(...)` and filter features using `setSubsetString(...)`.
- Check if `'NAME_1'` exists before filtering.
- Use `QgsProcessingFeedback` or custom subclass for logging output.
- Match CRS between raster and vector before processing.
- Wrap all file-dependent operations inside `try-except` blocks.
- Use `os.makedirs(..., exist_ok=True)` to ensure the output directory exists.
- The script should print meaningful logs and confirm the clipped file was saved.

## EXAMPLES:
If the algorithm fails, try fallback names like:
- `"native:cliprasterbymasklayer"`
- `"gdal:cliprasterbypolygon"`

## DOCUMENTATION CONTEXT (LANGCHAIN-RAG):
{context}

- Output only the Python script as a single valid code block.
- Do not explain the code or add Markdown formatting.
- The script must be compatible with the QGIS Python API in a headless batch execution setup.

"""

# --- Query Gemini 1.5 Flash ---
response = model.generate_content(prompt)
code = response.text.strip()

with open("template_code.py", "r") as f:
    template_code = f.read()

prompt2 = f"""

  you are a professional python geospatial code debuuger, based on the generated code compare it with the template code to ensure accuracy of the final code

  if found error modify the code to ensure it is accurate and runnable in a headless QGIS environment

  generated code:
{code}

template code:
{template_code}

  strictly only output the complete modified code as a single valid code block after debugging.

  """

response = model.generate_content(prompt2)
code2 = response.text.strip()

clean_code = extract_python_code(code2)

# --- Save Script to File ---
output_filename = filename if 'filename' in locals() else "clip1.py"
with open(output_filename, "w") as f:
    f.write(clean_code)

print(f" Saved {output_filename} for step: {step_id if 'step_id' in locals() else 'default'}")

run_qgis_steps([output_filename], script_dir=r"C:\Users\nj825\OneDrive\Desktop\code red\BAH")
