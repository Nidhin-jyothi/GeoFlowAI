import os
import json
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
import config


def load_documents(folder_path: str):
    """Loads all .txt and .pdf files from the specified folder."""
    all_docs = []
    if not os.path.exists(folder_path):
        print(f"Error: Folder not found -> {folder_path}")
        return []

    print(f"Loading documents from: {folder_path}")
    for file_name in os.listdir(folder_path):
        file_path = os.path.join(folder_path, file_name)
        try:
            if file_name.endswith(".txt"):
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                doc = Document(page_content=content, metadata={"source": file_name})
                all_docs.append(doc)
                print(f"   Loaded TXT: {file_name}")
            elif file_name.endswith(".pdf"):
                print(f"   Loading PDF: {file_name}...")
                loader = PyPDFLoader(file_path)
                pdf_docs = loader.load()
                all_docs.extend(pdf_docs)
                print(f"   Loaded {len(pdf_docs)} pages from PDF.")
        except Exception as e:
            print(f"   Error loading {file_name}: {e}")

    return all_docs


def load_qgis_schema(file_path: str):
    """
    Loads the enriched QGIS algorithm JSON and converts each algorithm
    into a RICH, self-contained document.

    Each document contains everything an LLM needs to correctly use
    the algorithm: ID, data type, all parameters with types, defaults,
    and Enum options with their integer indices.
    """
    docs = []
    if not os.path.exists(file_path):
        print(f"Warning: Schema file not found at {file_path}")
        return []

    print(f"Loading enriched schema from: {file_path}")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            algos = json.load(f)

        for algo in algos:
            # --- Build a rich, structured document for each algorithm ---
            lines = []
            lines.append(f"ALGORITHM ID: {algo['id']}")
            lines.append(f"DISPLAY NAME: {algo['name']}")
            lines.append(f"GROUP: {algo['group']}")
            lines.append(f"INPUT DATA TYPE: {algo.get('input_type', 'unknown')}")

            desc = algo.get('short_description', '')
            if desc:
                lines.append(f"DESCRIPTION: {desc}")

            tags = algo.get('tags', [])
            if tags:
                lines.append(f"TAGS: {', '.join(tags)}")

            lines.append("PARAMETERS:")

            for p in algo.get('parameters', []):
                optional_str = " (Optional)" if p.get('is_optional') else " (MANDATORY)"
                dest_str = " -> [OUTPUT]" if p.get('is_destination') else ""

                param_line = f"  - {p['name']}: {p['description']}"
                param_line += f" | Type: {p['type_class']}{optional_str}{dest_str}"

                # Default value
                default = p.get('default')
                if default is not None:
                    param_line += f" | Default: {default}"

                # Enum options with integer indices
                options = p.get('options')
                if options:
                    if isinstance(options, dict):
                        opts_str = ", ".join(f"{k}={v}" for k, v in options.items())
                    elif isinstance(options, list):
                        opts_str = ", ".join(f"{i}={v}" for i, v in enumerate(options))
                    else:
                        opts_str = str(options)
                    param_line += f" | Options: [{opts_str}]"

                lines.append(param_line)

            content = "\n".join(lines)

            doc = Document(
                page_content=content,
                metadata={
                    "source": "qgis_local_schema",
                    "id": algo['id'],
                    "group": algo['group'],
                    "input_type": algo.get('input_type', 'unknown'),
                }
            )
            docs.append(doc)

        print(f"   Processed {len(docs)} algorithm documents from local schema.")
    except Exception as e:
        print(f"   Error loading schema: {e}")

    return docs


def build_knowledge_base():
    """
    Builds the unified FAISS vector store.

    IMPORTANT: Algorithm schema documents are NOT split by the text splitter.
    Each algorithm stays as one atomic document to prevent losing parameter
    context across chunk boundaries.
    """

    # 1. Load PDF/TXT documentation
    source_folder = "PyGQIS Knowledge Base"
    doc_documents = load_documents(source_folder)

    # 2. Split documentation (these are long and benefit from chunking)
    print("Splitting documentation into chunks...")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=150
    )
    split_doc_docs = text_splitter.split_documents(doc_documents) if doc_documents else []
    print(f"   Created {len(split_doc_docs)} documentation chunks.")

    # 3. Load enriched QGIS schema (DO NOT SPLIT — each algo = 1 document)
    schema_file = "qgis_algorithms_detailed.json"
    schema_docs = load_qgis_schema(schema_file)
    print(f"   Loaded {len(schema_docs)} algorithm documents (unsplit).")

    # 4. Combine
    all_documents = split_doc_docs + schema_docs

    if not all_documents:
        print("No documents found. Exiting.")
        return

    print(f"Total documents for indexing: {len(all_documents)}")

    # 5. Create embeddings
    print("Generating embeddings (all-MiniLM-L6-v2)...")
    embedding_model = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

    # 6. Build and save FAISS index
    print("Building FAISS index...")
    vectorstore = FAISS.from_documents(all_documents, embedding_model)

    output_path = os.path.join(config.BASE_DIR, "agent2_knowledge_base")
    vectorstore.save_local(output_path)

    print(f"Knowledge base saved to: {output_path}")
    print(f"   {len(split_doc_docs)} doc chunks + {len(schema_docs)} algo docs = {len(all_documents)} total")


if __name__ == "__main__":
    build_knowledge_base()
