import os
import requests
from bs4 import BeautifulSoup
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
import config

# List of QGIS Documentation URLs (Vector & Raster Analysis)
URLS = [
    "https://docs.qgis.org/latest/en/docs/user_manual/processing_algs/qgis/vectorgeometry.html",
    "https://docs.qgis.org/latest/en/docs/user_manual/processing_algs/qgis/vectorgeneral.html",
    "https://docs.qgis.org/latest/en/docs/user_manual/processing_algs/qgis/vectoroverlay.html",
    "https://docs.qgis.org/latest/en/docs/user_manual/processing_algs/gdal/rasteranalysis.html",
    "https://docs.qgis.org/latest/en/docs/user_manual/processing_algs/gdal/rasterextraction.html",
    "https://docs.qgis.org/latest/en/docs/user_manual/processing_algs/gdal/rasterprojections.html"
]

def load_documents_from_urls(urls):
    """Scrapes content from a list of URLs."""
    documents = []
    print(f"🌍 Scraping {len(urls)} pages...")
    
    for url in urls:
        try:
            print(f"   Fetching: {url}")
            response = requests.get(url)
            if response.status_code != 200:
                print(f"   ❌ Failed to fetch {url}")
                continue
                
            soup = BeautifulSoup(response.content, "html.parser")
            
            # Extract main content (usually in <section> or <div role="main"> for Sphinx docs)
            main_content = soup.find("div", {"role": "main"}) or soup.find("section") or soup
            text = main_content.get_text(separator="\n", strip=True)
            
            doc = Document(page_content=text, metadata={"source": url})
            documents.append(doc)
            
        except Exception as e:
            print(f"   ❌ Error scraping {url}: {e}")
            
    return documents

def build_knowledge_base():
    """Builds and saves the FAISS vector store."""
    
    # 1. Load Data
    docs = load_documents_from_urls(URLS)
    if not docs:
        print("❌ No documents loaded. Exiting.")
        return

    # 2. Split Text
    print("✂️ Splitting text...")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200
    )
    chunks = text_splitter.split_documents(docs)
    print(f"   Created {len(chunks)} text chunks.")

    # 3. Create Embeddings
    print("🧠 Generating embeddings (all-MiniLM-L6-v2)...")
    embedding_model = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

    # 4. Build Vector Store
    print("store Building FAISS index...")
    vectorstore = FAISS.from_documents(chunks, embedding_model)

    # 5. Save Locally
    output_path = os.path.join(config.BASE_DIR, "qgis_knowledge_base")
    vectorstore.save_local(output_path)
    print(f"✅ Knowledge base saved to: {output_path}")

if __name__ == "__main__":
    build_knowledge_base()
