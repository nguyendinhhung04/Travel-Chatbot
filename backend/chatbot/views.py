"""HTTP views and response helpers for the travel chatbot API."""

from collections.abc import Iterable

from langchain_core.documents import Document


def build_sources(documents: Iterable[Document]) -> list[dict[str, str]]:
    """Create an ordered, de-duplicated source list for an API response."""
    sources: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for document in documents:
        metadata = document.metadata
        title = str(metadata.get("title") or "Không rõ")
        source = str(metadata.get("source") or "unknown")
        source_key = (title, source)

        if source_key in seen:
            continue

        seen.add(source_key)
        sources.append({"title": title, "source": source})

    return sources


__all__ = ["build_sources"]
