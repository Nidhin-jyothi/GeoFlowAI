import json
import os
from google import genai
import config
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

class Agent2Schematizer:
    def __init__(self):
        api_key = config.GEMINI_API_KEY
        if not api_key:
            raise ValueError("Gemini API Key not found in config")

        self.client = genai.Client(api_key=api_key)
        self.model = "gemini-2.5-flash"

        # Load Data Schema for available files
        schema_path = os.path.join(config.BASE_DIR, "data_schema.json")
        try:
            with open(schema_path, "r") as f:
                self.data_schema = json.load(f)
        except FileNotFoundError:
            print("Warning: Data schema not found.")
            self.data_schema = {}

        # Load the FULL algorithm index for validation
        self.valid_algos = set()
        try:
            index_path = os.path.join(config.BASE_DIR, "all_alg_ids.txt")
            with open(index_path, "r") as f:
                self.valid_algos = {line.strip() for line in f if line.strip()}
            print(f"Schematizer: Loaded {len(self.valid_algos)} valid algorithm IDs.")
        except Exception as e:
            print(f"Schematizer: Could not load algorithm index ({e}).")

        # Load vector store for algorithm knowledge (RAG)
        try:
            self.embedding_model = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
            self.vectorstore = FAISS.load_local(
                "agent2_knowledge_base", self.embedding_model,
                allow_dangerous_deserialization=True)
            self.retriever = self.vectorstore.as_retriever(search_kwargs={"k": 10})
            print("Schematizer: Loaded QGIS Knowledge Base for RAG.")
        except Exception as e:
            print(f"Schematizer: Knowledge Base not found ({e}).")
            self.retriever = None

        # Load Workflow Pattern Store (few-shot examples via RAG)
        self.workflow_retriever = None
        try:
            wf_store = FAISS.load_local(
                "workflow_patterns_store", self.embedding_model,
                allow_dangerous_deserialization=True)
            self.workflow_retriever = wf_store.as_retriever(search_kwargs={"k": 2})
            print("Schematizer: Loaded Workflow Pattern Store for few-shot examples.")
        except Exception as e:
            print(f"Schematizer: Workflow Pattern Store not found ({e}).")

    def validate_algorithms(self, steps):
        """Check that every algorithm ID in the plan actually exists in QGIS."""
        if not self.valid_algos:
            return True, []

        invalid = []
        for step in steps:
            algo = step.get("algorithm", "")
            if algo and algo not in self.valid_algos:
                invalid.append((step.get("step_id", "?"), algo))
        return len(invalid) == 0, invalid

    def _retrieve_workflow_patterns(self, query_text):
        """Retrieve similar workflow patterns from the Workflow Pattern Store."""
        if not self.workflow_retriever:
            return ""
        try:
            docs = self.workflow_retriever.invoke(query_text[:500])
            examples = []
            for i, doc in enumerate(docs):
                wf_json = doc.metadata.get("workflow", "[]")
                original_query = doc.metadata.get("query", "")
                examples.append(f"EXAMPLE {i+1} — Query: \"{original_query}\"\n{wf_json}")
            print(f"Schematizer: Retrieved {len(docs)} workflow patterns.")
            return "\n\n".join(examples)
        except Exception as e:
            print(f"Schematizer: Workflow Pattern retrieval failed: {e}")
            return ""

    def structure_plan(self, planner_text):
        """Converts textual plan to JSON using schema and RAG context."""

        context = ""
        if self.retriever:
            try:
                docs = self.retriever.invoke(planner_text[:1000])
                context = "\n\n".join([d.page_content[:1500] for d in docs])
                print(f"Schematizer: Retrieved {len(docs)} context chunks.")
            except Exception as e:
                print(f"Schematizer Retrieval failed: {e}")

        # Retrieve similar workflow patterns as few-shot examples
        workflow_examples = self._retrieve_workflow_patterns(planner_text)

        # Build algo index for the prompt
        algo_list_str = "\n".join(sorted(self.valid_algos)) if self.valid_algos else ""

        prompt = f"""You are a GIS workflow structuring agent.
Convert the plan below into a JSON execution schema.

PLAN:
{planner_text}

AVAILABLE DATA:
{json.dumps(self.data_schema, indent=2)}

COMPLETE ALGORITHM INDEX (ONLY use IDs from this list):
{algo_list_str}

DETAILED ALGORITHM REFERENCE (parameters & types):
{context}

OUTPUT FORMAT: JSON array of steps, each with:
- "step_id": e.g. "step_01"
- "algorithm": exact ALGORITHM ID from the COMPLETE ALGORITHM INDEX
- "parameters": dict with ALL mandatory parameters. For Enum params, use the integer index.
- "input_files": list of input paths from Available Data or from previous step outputs
- "output_file": path in "outputs/" — every step MUST have a non-null output_file
- "script_filename": e.g. "step_01_extract_boundary.py" — descriptive name

═══════════════════════════════════════════════════
BANNED ALGORITHMS (NEVER USE THESE):
═══════════════════════════════════════════════════
- qgis:selectbyattribute — does NOT produce an output file. Use 'native:extractbyattribute' instead.
- native:saveselectedfeatures — requires a pre-selected layer that doesn't exist in headless mode.
- qgis:rastercalculator — does NOT work in headless mode. Use 'gdal:rastercalculator' instead.

═══════════════════════════════════════════════════
RULES:
═══════════════════════════════════════════════════
1. Use ONLY algorithm IDs from the COMPLETE ALGORITHM INDEX. Do NOT invent IDs.
2. Every step MUST have a non-null "output_file" in "outputs/".
3. To extract features by attribute, ALWAYS use 'native:extractbyattribute' (single value) or 'native:extractbyexpression' (multi-value OR).
   - native:extractbyattribute params: INPUT, FIELD, OPERATOR (0=equals), VALUE, OUTPUT.
4. For 'gdal:rastercalculator':
   - Use parameter name 'FORMULA' (NEVER 'EXPRESSION').
   - Syntax: Python math operators. '*' for AND, '+' for OR, '==' for equals.
   - Example: FORMULA: "(A > 5.0) * (B > 4.5)"
5. For 'gdal:cliprasterbymasklayer', ONLY use: INPUT, MASK, CROP_TO_CUTLINE (true), KEEP_RESOLUTION (true), OUTPUT. No other params.
6. For 'gdal:polygonize': FIELD param is always ignored by GDAL. The output field is ALWAYS 'DN'.
   - Any downstream filter on polygonized output MUST use FIELD='DN', OPERATOR=0, VALUE='1'.
7. UNIT-AWARE: If distance in meters/km but input is EPSG:4326, inject 'native:reprojectlayer' to EPSG:3857 first.
8. CRS CONSISTENCY: If a vector was reprojected to 3857 for buffering, reproject it BACK to 4326 before rasterizing against a 4326 DEM.
9. MULTI-VALUE FILTERS: Use 'native:extractbyexpression' with EXPRESSION for OR conditions.
10. Output ONLY valid JSON. No markdown, no explanation.
11. FINAL CLIP: If the workflow involves polygonizing a raster, the LAST step MUST be 'native:clip' with INPUT=the filtered polygons and OVERLAY=the administrative boundary from step 01. This clips the blocky pixel-grid edges to the smooth administrative boundary.

═══════════════════════════════════════════════════
SIMILAR WORKFLOW EXAMPLES (retrieved dynamically — follow these patterns):
═══════════════════════════════════════════════════
{workflow_examples if workflow_examples else "No similar patterns found. Follow the rules strictly."}
"""

        import time
        max_retries = 5
        for attempt in range(max_retries):
            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=prompt
                )
                content = response.text

                # Strip markdown fences if present
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0]
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0]

                data = json.loads(content.strip())
                if isinstance(data, dict) and "steps" in data:
                    steps = data["steps"]
                elif isinstance(data, list):
                    steps = data
                else:
                    steps = [data]

                # Validate algorithms against known index
                valid, invalid = self.validate_algorithms(steps)
                if not valid:
                    for sid, algo in invalid:
                        print(f"⚠️  VALIDATION FAILED: {sid} uses unknown algorithm '{algo}'")
                    print("The generated plan contains invalid algorithm IDs. Please review.")

                return steps

            except Exception as e:
                err_msg = str(e)
                if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
                    print(f"⚠️ Schematizer Rate limited (429). Waiting 35s... (Attempt {attempt+1}/{max_retries})")
                    time.sleep(35)
                else:
                    print(f"Error structuring plan: {e}")
                    return []

        print("Error: Max retries reached for Schematizer.")
        return []

if __name__ == "__main__":
    agent = Agent2Schematizer()
    steps = agent.structure_plan("Step 1: Clip DEM. Step 2: Calculate Slope.")
    print(json.dumps(steps, indent=2))