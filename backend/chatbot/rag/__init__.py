"""Reusable components for the travel chatbot RAG pipeline."""

from .chunking import build_chunk_id, split_documents, split_long_sections
from .embeddings import get_embedding_model, verify_embedding
from .preprocessing import (
    load_markdown_documents,
    normalize_metadata,
    parse_document_frontmatter,
    split_by_headers,
)
from .rag_chain import (
    INSUFFICIENT_CONTEXT_MESSAGE,
    RAGResult,
    answer_question,
    build_prompt_template,
    build_rag_chain,
    format_context,
    get_chat_model,
)
from .vector_store import (
    SyncStats,
    get_vector_store,
    sync_vector_store,
    verify_vector_store,
)

__all__ = [
    "load_markdown_documents",
    "build_chunk_id",
    "get_embedding_model",
    "verify_embedding",
    "normalize_metadata",
    "parse_document_frontmatter",
    "split_documents",
    "split_by_headers",
    "split_long_sections",
    "INSUFFICIENT_CONTEXT_MESSAGE",
    "RAGResult",
    "answer_question",
    "build_prompt_template",
    "build_rag_chain",
    "format_context",
    "get_chat_model",
    "get_vector_store",
    "sync_vector_store",
    "verify_vector_store",
    "SyncStats",
]
