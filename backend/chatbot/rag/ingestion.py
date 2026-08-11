"""Helpers for the RAG ingestion pipeline."""

from __future__ import annotations

from langchain_core.documents import Document

from .chunking import build_chunk_id, split_documents, split_long_sections
from .preprocessing import (
    load_markdown_documents,
    normalize_metadata,
    parse_document_frontmatter,
    split_by_headers,
)


def collect_chunk_ids(chunks: list[Document]) -> set[str]:
    """Build the expected deterministic ID set for a chunk list."""
    return {build_chunk_id(chunk) for chunk in chunks}


def format_chunk_preview(chunk: Document, *, max_chars: int = 200) -> str:
    """Render one chunk preview for command-line inspection."""
    if max_chars <= 0:
        raise ValueError("max_chars must be greater than zero")

    metadata = chunk.metadata
    heading = (
        metadata.get("header_3")
        or metadata.get("header_2")
        or metadata.get("header_1")
        or "(no heading)"
    )
    excerpt = " ".join(chunk.page_content.split())
    if len(excerpt) > max_chars:
        excerpt = f"{excerpt[: max_chars - 3].rstrip()}..."

    return "\n".join(
        [
            f"Source: {metadata.get('source', 'unknown')}",
            f"Title: {metadata.get('title', 'unknown')}",
            f"Heading: {heading}",
            f"Length: {len(chunk.page_content)}",
            f"Excerpt: {excerpt}",
        ]
    )


__all__ = [
    "collect_chunk_ids",
    "format_chunk_preview",
    "load_markdown_documents",
    "normalize_metadata",
    "parse_document_frontmatter",
    "split_by_headers",
    "split_documents",
    "split_long_sections",
]
