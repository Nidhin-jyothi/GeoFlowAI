"""
Build the Workflow Pattern Vector Store.
Reads workflow_patterns.json and creates a FAISS index
keyed by query descriptions for similarity-based retrieval.
"""
import os
import json
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
import config

def build_workflow_store():
    patterns_path = os.path.join(config.BASE_DIR, "workflow_patterns.json")
    
    with open(patterns_path, "r") as f:
        patterns = json.load(f)
    
    print(f"📦 Loaded {len(patterns)} workflow patterns.")
    
    # Each document = the query text + full workflow JSON as metadata
    documents = []
    for p in patterns:
        # The page_content is what gets embedded (the query)
        # The metadata carries the full workflow JSON for retrieval
        doc = Document(
            page_content=f"[{p['category']}] {p['query']}",
            metadata={
                "query": p["query"],
                "category": p["category"],
                "workflow": json.dumps(p["workflow"], indent=2)
            }
        )
        documents.append(doc)
    
    print("🧠 Generating embeddings (all-MiniLM-L6-v2)...")
    embedding_model = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    
    print("📊 Building FAISS index...")
    vectorstore = FAISS.from_documents(documents, embedding_model)
    
    output_path = os.path.join(config.BASE_DIR, "workflow_patterns_store")
    vectorstore.save_local(output_path)
    print(f"✅ Workflow Pattern Store saved to: {output_path}")
    print(f"   Contains {len(documents)} patterns across categories:")
    
    categories = {}
    for p in patterns:
        cat = p["category"]
        categories[cat] = categories.get(cat, 0) + 1
    for cat, count in categories.items():
        print(f"   - {cat}: {count} patterns")

if __name__ == "__main__":
    build_workflow_store()
