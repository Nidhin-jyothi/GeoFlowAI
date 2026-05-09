import os
import json
from google import genai
from google.genai import types
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

        # Load vector store for RAG
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
        """Standard plan generation (non-streaming)."""
        content = ""
        def collect(c): nonlocal content; content += c
        self.generate_plan_stream(query, collect)
        return content

    def generate_plan_stream(self, query, chunk_callback, thought_callback=None):
        """
        Streams the plan from Gemini 2.5 Flash with native thinking.
        - thought_callback(text): receives the model's internal reasoning
        - chunk_callback(text):   receives the final plan output
        """
        context = ""
        if self.retriever:
            try:
                docs = self.retriever.invoke(query)
                context = "\n\n".join([d.page_content[:1500] for d in docs])
            except Exception:
                pass

        data_schema_content = "{}"
        try:
            with open(os.path.join(config.BASE_DIR, "data_schema.json"), "r") as f:
                data_schema = json.load(f)
                data_schema_content = json.dumps(data_schema, indent=2)
        except Exception:
            pass

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
1. Break the task into sequential steps (approx 4-6 steps).
2. Use ONLY algorithm IDs that appear EXACTLY in the COMPLETE ALGORITHM INDEX.
3. Check INPUT DATA TYPE: raster algorithms need .tif, vector algorithms need .shp.
4. ONLY use files from the AVAILABLE DATA CATALOG.
5. For clipping a raster using a vector mask, use `gdal:cliprasterbymasklayer`.
6. For buffering rivers, use `native:buffer`.
7. Do NOT write code. Output only the logical plan with algorithm IDs.
8. Be concise.

Plan:"""

        # Enable native thinking in Gemini 2.5 Flash
        gen_config = types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(
                thinking_budget=2048,
                include_thoughts=True
            )
        )

        full_text = ""
        try:
            for chunk in self.client.models.generate_content_stream(
                model=self.model,
                contents=prompt,
                config=gen_config
            ):
                # Each chunk may have multiple parts (thought vs output)
                if chunk.candidates and chunk.candidates[0].content and chunk.candidates[0].content.parts:
                    for part in chunk.candidates[0].content.parts:
                        if not part.text:
                            continue
                        if getattr(part, 'thought', False):
                            # This is the model's internal reasoning
                            if thought_callback:
                                thought_callback(part.text)
                        else:
                            # This is the actual plan output
                            full_text += part.text
                            chunk_callback(part.text)
            return full_text
        except Exception as e:
            err = f"\n[ERROR] {e}"
            chunk_callback(err)
            return full_text + err

if __name__ == "__main__":
    agent = Agent1Planner()
    query = "Flood analysis for Kerala."
    def log(c): print(c, end="", flush=True)
    def thought(t): print(f"\n💭 {t}", end="", flush=True)
    agent.generate_plan_stream(query, log, thought)