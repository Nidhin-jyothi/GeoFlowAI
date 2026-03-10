import os
import json
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import SentenceTransformerEmbeddings
from langchain_community.document_loaders import UnstructuredFileLoader
from langchain.text_splitter import CharacterTextSplitter
from langchain.schema import Document

def load_all_txt_documents(folder_path: str):
    all_docs = []
    for file_name in os.listdir(folder_path):
        if file_name.endswith(".txt"):
            file_path = os.path.join(folder_path, file_name)
            loader = UnstructuredFileLoader(file_path)
            docs = loader.load()
            for doc in docs:
                doc.metadata["source"] = file_name
            all_docs.extend(docs)
            print(f"📄 Loaded: {file_name} ({len(docs)} docs)")
    return all_docs

# Step 1: Load all docs
all_documents = load_all_txt_documents("PyGQIS Knowledge Base")

# Step 2: Chunk docs
text_splitter = CharacterTextSplitter(chunk_size=800, chunk_overlap=150)
split_docs = []
for doc in all_documents:
    chunks = text_splitter.split_text(doc.page_content)
    for chunk in chunks:
        split_docs.append(Document(
            page_content=chunk,
            metadata={"source": doc.metadata["source"]}
        ))

# Step 3: Embeddings
embedding_model = SentenceTransformerEmbeddings(model_name="all-MiniLM-L6-v2")

# Step 4: Store vector index
vectorstore = FAISS.from_documents(split_docs, embedding_model)
vectorstore.save_local("qgis_knowledge_base")

print("✅ Vectorstore created and saved to: qgis_knowledge_base")
