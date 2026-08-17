"""Gemini embedding model factory for the RAG pipeline."""

from __future__ import annotations

from collections.abc import Sequence

from langchain_google_genai import GoogleGenerativeAIEmbeddings


def get_embedding_model(
    *,
    api_key: str | None = None,
    model: str | None = None,
) -> GoogleGenerativeAIEmbeddings:
    """Create the configured LangChain Gemini embedding model.

    Values default to Django settings but can be overridden in tests or
    standalone scripts. This function only initializes the client; the first
    network request happens when ``embed_query`` or ``embed_documents`` runs.
    """
    from django.conf import settings

    resolved_api_key = api_key or settings.GEMINI_API_KEY
    if not resolved_api_key:
        raise ValueError(
            "GEMINI_API_KEY is missing. Set it in the .env file or environment."
        )

    resolved_model = model or settings.GEMINI_EMBEDDING_MODEL
    if not resolved_model:
        raise ValueError("GEMINI_EMBEDDING_MODEL must not be empty")

    return GoogleGenerativeAIEmbeddings(
        model=resolved_model,
        api_key=resolved_api_key,
    )


def verify_embedding(
    embedding_model: GoogleGenerativeAIEmbeddings | None = None,
    sample_text: str = "Phố cổ Hội An có những trải nghiệm du lịch nào?",
) -> int:
    """Embed one sample and return the vector dimension.

    This performs one real API request and fails early if credentials,
    connectivity or the configured embedding model is unavailable.
    """
    model = embedding_model or get_embedding_model()
    vector: Sequence[object] = model.embed_query(sample_text)
    if not vector:
        raise RuntimeError("Gemini returned an empty embedding vector")
    if not all(isinstance(value, (int, float)) for value in vector):
        raise RuntimeError("Gemini returned a non-numeric embedding vector")
    return len(vector)
