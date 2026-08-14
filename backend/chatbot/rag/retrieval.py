"""Create a LangChain Retriever for the travel knowledge base."""

from __future__ import annotations

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.vectorstores import VectorStoreRetriever

from .vector_store import get_vector_store


def _resolve_top_k(top_k: int | None) -> int:
    """Return and validate the configured number of search results."""
    if top_k is None:
        from django.conf import settings

        top_k = settings.RAG_RETRIEVAL_TOP_K

    if isinstance(top_k, bool) or not isinstance(top_k, int):
        raise ValueError("top_k must be an integer")
    if top_k <= 0:
        raise ValueError("top_k must be greater than zero")
    return top_k


def get_retriever(
    *,
    vector_store: Chroma | None = None,
    top_k: int | None = None,
) -> VectorStoreRetriever:
    """Create a similarity Retriever backed by the persistent Chroma store.

    ``vector_store`` can be supplied by tests or by another caller. When it is
    omitted, the configured travel knowledge collection is opened automatically.
    """
    from django.conf import settings

    resolved_top_k = _resolve_top_k(top_k)
    store = vector_store if vector_store is not None else get_vector_store()
    return store.as_retriever(
        search_type="similarity_score_threshold",
        search_kwargs={
            "k": resolved_top_k,
            "score_threshold": settings.RAG_RELEVANCE_THRESHOLD,
        },
    )


def retrieve_documents(
    question: str,
    *,
    retriever: VectorStoreRetriever | None = None,
    top_k: int | None = None,
) -> list[Document]:
    """Search the knowledge base and return the most relevant documents."""
    cleaned_question = question.strip()
    if not cleaned_question:
        raise ValueError("question must not be empty")

    active_retriever = (
        retriever if retriever is not None else get_retriever(top_k=top_k)
    )
    return active_retriever.invoke(cleaned_question)


__all__ = ["get_retriever", "retrieve_documents"]
