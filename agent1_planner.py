import os
import json
from google import genai
import config
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

class Agent1Planner:
    def __init__(self):
        api_key = config.GEMINI_API_KEY
        if not api_key:
            raise ValueError("Gemini API Key not found in config")

        self.client = genai.Client(api_key=api_key)
        self.model = "gemini-2.5-flash"

        # Load the FULL algorithm index for grounding
        self.algo_index = []
        try:
            index_path = os.path.join(config.BASE_DIR, "all_alg_ids.txt")
            with open(index_path, "r") as f:
                self.algo_index = [line.strip() for line in f if line.strip()]
            print(f"Planner: Loaded {len(self.algo_index)} algorithm IDs from index.")
        except Exception as e:
            print(f"Planner: Could not load algorithm index ({e}).")

        # Load vector store for RAG (detailed parameter info)
        try:
            self.embedding_model = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
            self.vectorstore = FAISS.load_local(
                "agent2_knowledge_base", self.embedding_model,
                allow_dangerous_deserialization=True)
            self.retriever = self.vectorstore.as_retriever(search_kwargs={"k": 10})
            print("Planner: Loaded QGIS Knowledge Base (Grounding enabled).")
        except Exception as e:
            print(f"Planner: Knowledge Base not found ({e}).")
            self.retriever = None

    def generate_plan(self, query):
        """Generates a high-level textual workflow plan."""

        context = ""
        if self.retriever:
            try:
                docs = self.retriever.invoke(query)
                context = "\n\n".join([d.page_content[:1500] for d in docs])
                print(f"Agent 1: Retrieved {len(docs)} context chunks.")
            except Exception as e:
                print(f"Retrieval failed: {e}")

        # Load available data schema
        data_schema_content = "{}"
        try:
            with open(os.path.join(config.BASE_DIR, "data_schema.json"), "r") as f:
                data_schema = json.load(f)
                data_schema_content = json.dumps(data_schema, indent=2)
        except Exception as e:
            print(f"Agent 1: Could not load data schema ({e})")

        # Build the compact algo index string
        algo_list_str = "\n".join(self.algo_index) if self.algo_index else "No algorithm index loaded."

        prompt = f"""You are a geospatial analysis planner.
Plan a QGIS workflow for: "{query}"

AVAILABLE DATA CATALOG (these are the ONLY files you can use):
{data_schema_content}

COMPLETE ALGORITHM INDEX (ONLY use IDs from this list):
{algo_list_str}

DETAILED ALGORITHM REFERENCE (parameters & types):
{context}

RULES:
1. Break the task into sequential steps (keep it minimal, 2-4 steps max).
2. Use ONLY algorithm IDs that appear EXACTLY in the COMPLETE ALGORITHM INDEX above. Do NOT invent or guess algorithm names.
3. Check INPUT DATA TYPE: raster algorithms need .tif, vector algorithms need .shp.
4. ONLY use files from the AVAILABLE DATA CATALOG. Do NOT hallucinate files that don't exist.
5. For clipping a raster using a vector mask, use `gdal:cliprasterbymasklayer`.
6. Do NOT write code. Output only the logical plan with algorithm IDs.
7. Be concise. No rambling or repeating yourself.

Plan:"""

        import time
        max_retries = 5
        for attempt in range(max_retries):
            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=prompt
                )
                return response.text
            except Exception as e:
                err_msg = str(e)
                if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
                    print(f"⚠️ Planner Rate limited (429). Waiting 35s... (Attempt {attempt+1}/{max_retries})")
                    time.sleep(35)
                else:
                    return f"Error generating plan: {e}"

        return "Error: Max retries reached for Planner."

if __name__ == "__main__":
    agent = Agent1Planner()
    query = "Clip the Kerala DEM using the state boundary shapefile, then calculate the slope of the clipped DEM."
    print(f"Generating plan for: {query}")
    plan = agent.generate_plan(query)

    output_path = os.path.join(config.OUTPUT_DIR, "step1_plan.txt")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(plan)

    print(f"Plan saved to: {output_path}")
    print("-" * 40)
    print(plan)
    print("-" * 40)
