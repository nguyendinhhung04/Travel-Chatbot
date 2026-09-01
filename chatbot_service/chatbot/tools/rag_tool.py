"""Local retrieval tool for the travel knowledge base."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any

from langchain_core.documents import Document

from chatbot.rag.retrieval import retrieve_documents

from .models import (
    KnowledgeBaseSource,
    RagChunk,
    RagToolData,
    SearchTravelKnowledgeInput,
    ToolResult,
)


logger = logging.getLogger(__name__)

SEARCH_TRAVEL_KNOWLEDGE_TOOL_NAME = "search_travel_knowledge"
RAG_UNAVAILABLE_ERROR = "rag_unavailable"


def search_travel_knowledge(
    request: SearchTravelKnowledgeInput,
    *,
    retriever: Any | None = None,
    top_k: int | None = None,
) -> ToolResult[RagToolData]:
    """Retrieve relevant chunks without invoking a language model."""
    try:
        documents = retrieve_documents(
            request.query,
            retriever=retriever,
            top_k=top_k,
            destination=request.destination,
        )
    except Exception as error:
        logger.warning(
            "Travel knowledge retrieval failed (%s)",
            type(error).__name__,
        )
        return ToolResult[RagToolData](
            success=False,
            error_code=RAG_UNAVAILABLE_ERROR,
            error_message="Không thể truy xuất kho kiến thức du lịch.",
        )

    return ToolResult[RagToolData](
        success=True,
        data=build_rag_tool_data(documents),
    )


def build_rag_tool_data(documents: Iterable[Document]) -> RagToolData:
    """Convert retrieved documents into chunks and ordered unique sources."""
    chunks: list[RagChunk] = []
    sources: list[KnowledgeBaseSource] = []
    seen_sources: set[tuple[str, str]] = set()

    for document in documents:
        content = document.page_content.strip()
        if not content:
            continue

        metadata = document.metadata
        title = str(metadata.get("title") or "").strip() or "Không rõ"
        source = str(metadata.get("source") or "").strip() or "unknown"
        heading_value = (
            metadata.get("header_3")
            or metadata.get("header_2")
            or metadata.get("header_1")
        )
        heading = (str(heading_value).strip() or None) if heading_value else None

        chunks.append(
            RagChunk(
                content=content,
                title=title,
                source=source,
                heading=heading,
            )
        )

        source_key = (title, source)
        if source_key not in seen_sources:
            seen_sources.add(source_key)
            sources.append(
                KnowledgeBaseSource(
                    title=title,
                    source=source,
                )
            )

    return RagToolData(chunks=chunks, sources=sources)


__all__ = [
    "RAG_UNAVAILABLE_ERROR",
    "SEARCH_TRAVEL_KNOWLEDGE_TOOL_NAME",
    "build_rag_tool_data",
    "search_travel_knowledge",
]
