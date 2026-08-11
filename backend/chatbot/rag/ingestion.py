"""Backward-compatible imports for the RAG ingestion pipeline."""

from .chunking import split_documents, split_long_sections
from .preprocessing import (
    load_markdown_documents,
    normalize_metadata,
    parse_document_frontmatter,
    split_by_headers,
)

__all__ = [
    "load_markdown_documents",
    "normalize_metadata",
    "parse_document_frontmatter",
    "split_by_headers",
    "split_documents",
    "split_long_sections",
]
