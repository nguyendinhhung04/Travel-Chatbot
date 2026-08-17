"""Split preprocessed Markdown sections into embedding-sized chunks."""

from __future__ import annotations

import hashlib
import json

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from .preprocessing import split_by_headers

#build chunk ID
def build_chunk_id(document: Document) -> str:
    """Build a deterministic ID from a chunk's content and metadata."""
    payload = json.dumps(
        {
            "content": document.page_content,
            "metadata": document.metadata,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    return f"chunk_{digest}"


def _chunk_settings(
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> tuple[int, int]:
    """Resolve and validate chunk settings from arguments or Django settings."""
    if chunk_size is None or chunk_overlap is None:
        from django.conf import settings

        chunk_size = settings.RAG_CHUNK_SIZE if chunk_size is None else chunk_size
        chunk_overlap = (
            settings.RAG_CHUNK_OVERLAP
            if chunk_overlap is None
            else chunk_overlap
        )

    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero")
    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be between 0 and chunk_size - 1")
    return chunk_size, chunk_overlap

#Called by split_documents(), not splitter.split_documents()
def split_long_sections(
    sections: list[Document],
    *,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[Document]:
    """Split long sections into overlapping character-based chunks."""
    chunk_size, chunk_overlap = _chunk_settings(chunk_size, chunk_overlap)
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
        keep_separator=True,
    )

    chunks = splitter.split_documents(sections)
    return [
        Document(
            page_content=chunk.page_content.strip(),
            metadata=dict(chunk.metadata),
        )
        for chunk in chunks
        if chunk.page_content.strip()
    ]


def split_documents(
    documents: list[Document],
    *,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[Document]:
    """Run preprocessing heading split followed by long-section chunking."""
    sections = split_by_headers(documents)
    return split_long_sections(
        sections,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
