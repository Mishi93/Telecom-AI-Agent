"""
Builds (or rebuilds) the local vector store used by the RAG pipeline.

Scans data_pipeline/data/ for:
  - *.pdf  -> loaded via PyPDFLoader (one Document per page)
  - *.csv  -> loaded via CSVLoader   (one Document per row)

Splits everything into overlapping chunks, embeds them via Hugging Face's
current Inference Providers API (router.huggingface.co, through
langchain_huggingface's HuggingFaceEndpointEmbeddings), and persists into
backend/rag/vector_store/ via Chroma.

Run manually whenever new documents or CSV data are added or changed:
    cd backend
    python rag/ingest_rag.py

Requires HF_TOKEN or HUGGINGFACEHUB_API_TOKEN to be set in the environment.
"""
import sys
from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader, CSVLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma

# Make backend/ importable so this script can reuse the retriever's
# path/model constants and embeddings config and stay in sync with it
# automatically.
_THIS_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _THIS_DIR.parent
sys.path.insert(0, str(_BACKEND_DIR))

from rag.retriever import VECTOR_STORE_DIR, EMBEDDING_MODEL_NAME, get_embeddings  # noqa: E402

DATA_DIR = _BACKEND_DIR / "data_pipeline" / "data"
CHUNK_SIZE = 800
CHUNK_OVERLAP = 120


def load_documents():
    documents = []

    if not DATA_DIR.exists():
        print(f"WARNING: data directory not found: {DATA_DIR}")
        return documents

    pdf_files = sorted(DATA_DIR.glob("*.pdf"))
    csv_files = sorted(DATA_DIR.glob("*.csv"))

    for pdf_path in pdf_files:
        print(f"Loading PDF: {pdf_path.name}")
        loader = PyPDFLoader(str(pdf_path))
        documents.extend(loader.load())

    for csv_path in csv_files:
        print(f"Loading CSV: {csv_path.name}")
        loader = CSVLoader(file_path=str(csv_path))
        documents.extend(loader.load())

    if not pdf_files and not csv_files:
        print(f"WARNING: no .pdf or .csv files found in {DATA_DIR}")

    return documents


def clear_existing_store(embeddings):
    """
    Clears any existing vector store contents WITHOUT deleting the
    directory on disk.

    A prior version of this script used shutil.rmtree(), which fails on
    Windows with PermissionError/WinError 5 because SQLite keeps a file
    handle open on chroma.sqlite3 - even after the Python process exits,
    the OS may not release the lock immediately. Using Chroma's own
    delete_collection() clears the data through the same client that owns
    the file, avoiding the filesystem lock entirely.
    """
    vector_store_path = Path(VECTOR_STORE_DIR)

    if not vector_store_path.exists() or not any(vector_store_path.iterdir()):
        vector_store_path.mkdir(parents=True, exist_ok=True)
        return

    try:
        existing_store = Chroma(
            persist_directory=VECTOR_STORE_DIR,
            embedding_function=embeddings,
        )
        existing_store.delete_collection()
        print(f"Cleared existing vector store collection at {VECTOR_STORE_DIR}")
    except Exception as e:
        print(
            f"WARNING: could not cleanly clear the existing vector store ({e}). "
            "New documents will be added alongside whatever is already there, "
            "which may result in duplicate chunks."
        )


def build_vector_store():
    documents = load_documents()

    if not documents:
        print("No documents loaded - nothing to embed. Aborting.")
        return

    print(f"Splitting {len(documents)} loaded document(s)/row(s) into chunks...")
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )
    chunks = splitter.split_documents(documents)
    print(f"  -> {len(chunks)} chunks created")

    print(f"Using Hugging Face Inference Providers API for '{EMBEDDING_MODEL_NAME}'...")
    # Reuse the exact same embeddings config/singleton as retriever.py so
    # both scripts hit the same endpoint with the same auth handling.
    embeddings = get_embeddings()

    clear_existing_store(embeddings)

    print(f"Embedding and writing vector store to: {VECTOR_STORE_DIR}")
    try:
        Chroma.from_documents(
            documents=chunks,
            embedding=embeddings,
            persist_directory=VECTOR_STORE_DIR,
        )
    except Exception as e:
        print(f"ERROR: embedding request failed: {e}")
        print(
            "Check that HF_TOKEN/HUGGINGFACEHUB_API_TOKEN is set and valid, "
            "that you have network access to huggingface.co, and that this "
            "model is served by a Hugging Face Inference Provider."
        )
        raise

    print("Vector store build complete.")


if __name__ == "__main__":
    build_vector_store()