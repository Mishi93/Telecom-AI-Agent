"""
Loads the Chroma vector store built by ingest_rag.py and exposes a simple
query interface for the agent to use.

Uses Hugging Face's current Inference Providers API (router.huggingface.co)
via langchain_huggingface's HuggingFaceEndpointEmbeddings - NOT the old
api-inference.huggingface.co/pipeline/feature-extraction endpoint. That
endpoint has been deprecated in favor of the new router-based Inference
Providers system and is no longer reliable (may fail to resolve or return
errors even with a valid token).

The vector store must already exist on disk (run ingest_rag.py first) -
this module does not build it, only reads it.
"""
import os
from pathlib import Path

from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEndpointEmbeddings

# Resolve paths relative to THIS file, not the working directory, so it
# works no matter where uvicorn/python is launched from.
_RAG_DIR = Path(__file__).resolve().parent
VECTOR_STORE_DIR = str(_RAG_DIR / "vector_store")

EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

# Lazily initialized singletons so the embedding client and vector store
# connection are only set up once per process, not on every call.
_embeddings = None
_vector_store = None


def _get_hf_token() -> str:
    hf_api_key = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACEHUB_API_TOKEN")
    if not hf_api_key:
        raise ValueError(
            "Missing credentials: HF_TOKEN or HUGGINGFACEHUB_API_TOKEN environment "
            "variable must be defined to query cloud embeddings."
        )
    return hf_api_key


def get_embeddings() -> HuggingFaceEndpointEmbeddings:
    global _embeddings
    if _embeddings is None:
        # HuggingFaceEndpointEmbeddings uses huggingface_hub's InferenceClient
        # under the hood, which routes through the current Inference
        # Providers API (router.huggingface.co) rather than the deprecated
        # api-inference.huggingface.co pipeline endpoint.
        _embeddings = HuggingFaceEndpointEmbeddings(
            model=EMBEDDING_MODEL_NAME,
            task="feature-extraction",
            huggingfacehub_api_token=_get_hf_token(),
        )
    return _embeddings


def get_vector_store() -> Chroma:
    global _vector_store
    if _vector_store is None:
        if not os.path.isdir(VECTOR_STORE_DIR) or not os.listdir(VECTOR_STORE_DIR):
            raise RuntimeError(
                f"No vector store found at '{VECTOR_STORE_DIR}'. "
                "Run the ingestion script (ingest_rag.py) first to build it."
            )
        _vector_store = Chroma(
            persist_directory=VECTOR_STORE_DIR,
            embedding_function=get_embeddings(),
        )
    return _vector_store


def get_retriever(k: int = 4):
    """Returns a LangChain retriever over the persisted vector store."""
    return get_vector_store().as_retriever(search_kwargs={"k": k})


def query_knowledge_base(query: str, k: int = 4) -> str:
    """
    Runs a similarity search against the knowledge base and returns
    formatted, source-tagged context chunks ready to hand to the LLM.
    """
    retriever = get_retriever(k=k)

    try:
        docs = retriever.invoke(query)
    except Exception as e:
        # Most likely a network/auth failure talking to the HF Inference
        # Providers API - surface a clear message rather than a raw
        # requests/urllib3 traceback.
        raise RuntimeError(
            f"Knowledge base query failed - could not reach the embedding "
            f"service. Check your network connection and HF_TOKEN. ({e})"
        )

    if not docs:
        return "No relevant information was found in the knowledge base."

    formatted_chunks = []
    for idx, doc in enumerate(docs, 1):
        source = doc.metadata.get("source", "unknown source")
        page = doc.metadata.get("page")
        source_label = f"{source} (page {page + 1})" if page is not None else source
        formatted_chunks.append(
            f"[Result {idx} - source: {source_label}]\n{doc.page_content.strip()}"
        )

    return "\n\n".join(formatted_chunks)