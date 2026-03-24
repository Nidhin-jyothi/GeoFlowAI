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
- "input_files": list of input paths from Available Data
- "output_file": path in "outputs/"
- "script_filename": e.g. "step_01_slope.py"

RULES:
1. Use ONLY algorithm IDs that appear EXACTLY in the COMPLETE ALGORITHM INDEX. Do NOT invent IDs.
2. Check INPUT DATA TYPE: raster algorithms need .tif, vector algorithms need .shp.
3. Include ALL mandatory parameters with correct types. Enum = integer index.
4. Output ONLY valid JSON. No markdown, no explanation.
5. CRITICAL: NEVER use 'qgis:rastercalculator'. It does NOT work in headless/script mode. Use 'gdal:rastercalculator' instead.
   - gdal:rastercalculator parameters: INPUT_A (raster path), BAND_A (int), INPUT_B, BAND_B, INPUT_C, BAND_C, FORMULA (e.g. "(A<10)*(B<5)"), OUTPUT (path).
   - The FORMULA uses single letters A, B, C etc. that correspond to INPUT_A, INPUT_B, INPUT_C.
   - Example: {{"INPUT_A": "outputs/dem.tif", "BAND_A": 1, "FORMULA": "A<10", "OUTPUT": "outputs/result.tif"}}
6. For 'gdal:rasterize', you MUST include 'EXTENT', 'WIDTH', and 'HEIGHT'.
   - 'EXTENT' is string: 'minx,maxx,miny,maxy [EPSG:4326]'.
   - 'UNITS' should be 0 (Pixels).
   - Use 'BURN' value (float) to set the output pixel value.
7. UNIT-AWARE GEOPROCESSING: If a query specifies a distance in METERS or KM (e.g. '10km buffer'), but the input layer is in Degrees (EPSG:4326), you MUST:
   - Inject a 'native:reprojectlayer' step to EPSG:3857 BEFORE the distance operation.
   - Use EPSG:3857 (meters) for all subsequent spatial operations in that chain.
   - Assume GADM (gadm41_IND_*) and OSM roads are in Degrees.
8. MULTI-VALUE FILTERS: If the plan requires filtering by multiple attribute values (e.g. fclass = 'motorway' OR fclass = 'primary'), you MUST use 'native:extractbyexpression' with an EXPRESSION parameter (e.g. EXPRESSION: "\"fclass\" = 'motorway' OR \"fclass\" = 'primary'"). 
   - DO NOT use 'native:extractbyattribute' for multi-value OR conditions — it only supports a single value match.
   - 'native:extractbyexpression' parameters: INPUT (layer path), EXPRESSION (QGIS expression string), OUTPUT (output path).
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
