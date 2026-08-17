"""Load and preprocess Markdown documents before chunking."""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_core.documents import Document
from langchain_text_splitters import MarkdownHeaderTextSplitter
import yaml


REQUIRED_FRONTMATTER_FIELDS = {
    "title",
    "slug",
    "entity_type",
    "tags",
    "related",
    "last_reviewed",
}
_FRONTMATTER_PATTERN = re.compile(
    r"\A---\s*\r?\n(?P<yaml>.*?)\r?\n---\s*(?:\r?\n|\Z)",
    re.DOTALL,
)


def _knowledge_base_path(knowledge_base_dir: str | Path | None = None) -> Path:
    """Return the configured Knowledge Base directory as an absolute path."""
    if knowledge_base_dir is not None:
        return Path(knowledge_base_dir).resolve()

    from django.conf import settings

    return Path(settings.KNOWLEDGE_BASE_DIR).resolve()


def _normalize_metadata_value(value: Any) -> str | int | float | bool:
    """Convert YAML values into Chroma-compatible metadata values."""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (list, tuple, dict)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def normalize_metadata(metadata: dict[str, Any]) -> dict[str, str | int | float | bool]:
    """Normalize YAML metadata into values accepted by Chroma."""
    return {
        key: _normalize_metadata_value(value)
        for key, value in metadata.items()
        if value is not None
    }


def parse_document_frontmatter(document: Document) -> Document:
    """Parse and validate one Document's YAML front matter."""
    source = str(document.metadata.get("source", "unknown"))
    match = _FRONTMATTER_PATTERN.match(document.page_content)
    if match is None:
        raise ValueError(f"Missing YAML front matter in: {source}")

    try:
        raw_metadata = yaml.safe_load(match.group("yaml"))
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML front matter in {source}: {exc}") from exc

    if not isinstance(raw_metadata, dict):
        raise ValueError(f"YAML front matter must be a mapping in: {source}")

    missing_fields = REQUIRED_FRONTMATTER_FIELDS - raw_metadata.keys()
    if missing_fields:
        missing = ", ".join(sorted(missing_fields))
        raise ValueError(f"Missing metadata fields in {source}: {missing}")

    normalized_metadata = normalize_metadata(raw_metadata)
    normalized_metadata["source"] = source
    document.metadata = normalized_metadata
    document.page_content = document.page_content[match.end() :].lstrip("\r\n")
    return document


def load_markdown_documents(
    knowledge_base_dir: str | Path | None = None,
) -> list[Document]:
    """Load Markdown files and return Documents with normalized metadata."""
    root = _knowledge_base_path(knowledge_base_dir)
    if not root.is_dir():
        raise FileNotFoundError(f"Knowledge Base directory does not exist: {root}")

    loader = DirectoryLoader(
        str(root),
        glob="**/*.md",
        loader_cls=TextLoader,
        loader_kwargs={"encoding": "utf-8"},
        recursive=True,
        show_progress=False,
        use_multithreading=False,
    )
    documents = loader.load()

    normalized: list[Document] = []
    for document in documents:
        raw_source = Path(str(document.metadata.get("source", "")))
        try:
            relative_source = raw_source.resolve().relative_to(root).as_posix()
        except ValueError:
            relative_source = raw_source.as_posix()

        document.metadata["source"] = relative_source
        normalized.append(parse_document_frontmatter(document))

    return sorted(normalized, key=lambda document: document.metadata["source"])


def split_by_headers(documents: list[Document]) -> list[Document]:
    """Split Documents by Markdown headings while preserving file metadata."""
    splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=[
            ("#", "header_1"),
            ("##", "header_2"),
            ("###", "header_3"),
        ],
        strip_headers=False,
    )

    sections: list[Document] = []
    for document in documents:
        for section in splitter.split_text(document.page_content):
            content = section.page_content.strip()
            if not content:
                continue

            metadata = {**document.metadata, **section.metadata}
            sections.append(Document(page_content=content, metadata=metadata))

    return sections

