"""Persistent LangChain Chroma vector-store access for the RAG pipeline."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from .chunking import build_chunk_id
from .embeddings import get_embedding_model


@dataclass(frozen=True)
class SyncStats:
    """Summary of one Chroma synchronization run."""

    total: int
    added: int
    unchanged: int
    deleted: int


def get_vector_store(
    *,
    embedding_model: Embeddings | None = None,
    persist_directory: str | Path | None = None,
    collection_name: str | None = None,
) -> Chroma:
    """Open the configured persistent Chroma collection.

    Chroma creates the directory and collection when they do not exist. The
    embedding model is attached for later ``add_documents`` and similarity
    search calls; opening the store itself does not call the Gemini API.
    """
    from django.conf import settings

    directory = Path(persist_directory or settings.CHROMA_DB_DIR).resolve()
    name = collection_name or settings.CHROMA_COLLECTION_NAME
    if not name.strip():
        raise ValueError("Chroma collection_name must not be empty")

    directory.mkdir(parents=True, exist_ok=True)
    return Chroma(
        collection_name=name,
        embedding_function=embedding_model or get_embedding_model(),
        persist_directory=str(directory),
    )


def _get_existing_ids(vector_store: Chroma) -> set[str]:
    """Read existing document IDs from Chroma without fetching payloads."""
    result = vector_store.get(include=[])
    ids = result.get("ids", [])
    return {str(item) for item in ids}


def sync_vector_store(
    vector_store: Chroma,
    chunks: list[Document],
    *,
    batch_size: int = 50,
    batch_pause_seconds: float = 0,
) -> SyncStats:
    """Synchronize the Chroma collection with the current chunk list.

    Chunk IDs are deterministic, so unchanged chunks are skipped. New or changed
    chunks are added first; stale IDs are deleted only after add succeeds.
    """
    if not chunks:
        raise ValueError("Cannot sync an empty chunk list into Chroma")
    if batch_size <= 0:
        raise ValueError("batch_size must be greater than zero")
    if batch_pause_seconds < 0:
        raise ValueError("batch_pause_seconds must not be negative")

    desired_by_id: dict[str, Document] = {}
    duplicate_ids: list[str] = []
    for chunk in chunks:
        chunk_id = build_chunk_id(chunk)
        if chunk_id in desired_by_id:
            duplicate_ids.append(chunk_id)
        desired_by_id[chunk_id] = chunk

    if duplicate_ids:
        preview = ", ".join(sorted(set(duplicate_ids))[:5])
        raise ValueError(f"Duplicate chunk IDs found: {preview}")

    desired_ids = set(desired_by_id)
    existing_ids = _get_existing_ids(vector_store)
    unchanged_ids = desired_ids & existing_ids
    ids_to_add = sorted(desired_ids - existing_ids)
    ids_to_delete = sorted(existing_ids - desired_ids)

    for start in range(0, len(ids_to_add), batch_size):
        batch_ids = ids_to_add[start : start + batch_size]
        vector_store.add_documents(
            documents=[desired_by_id[item_id] for item_id in batch_ids],
            ids=batch_ids,
        )
        has_more_batches = start + batch_size < len(ids_to_add)
        if has_more_batches and batch_pause_seconds:
            time.sleep(batch_pause_seconds)

    if ids_to_delete:
        vector_store.delete(ids=ids_to_delete)

    return SyncStats(
        total=len(chunks),
        added=len(ids_to_add),
        unchanged=len(unchanged_ids),
        deleted=len(ids_to_delete),
    )


def verify_vector_store(
    expected_ids: set[str],
    *,
    persist_directory: str | Path | None = None,
    collection_name: str | None = None,
    embedding_model: Embeddings | None = None,
) -> None:
    """Reload Chroma from disk and verify the persisted IDs exactly match.

    A fresh Chroma instance is opened against the same persist directory to
    prove that data survives process restart. The function raises ``RuntimeError``
    with a concrete mismatch summary when the persisted collection differs from
    the expected chunk set.
    """
    if not expected_ids:
        raise ValueError("expected_ids must not be empty")

    reloaded_store = get_vector_store(
        embedding_model=embedding_model,
        persist_directory=persist_directory,
        collection_name=collection_name,
    )
    actual_ids = _get_existing_ids(reloaded_store)

    missing_ids = sorted(expected_ids - actual_ids)
    extra_ids = sorted(actual_ids - expected_ids)
    if missing_ids or extra_ids:
        details: list[str] = []
        if missing_ids:
            details.append(
                f"missing {len(missing_ids)} chunk(s), for example: "
                f"{', '.join(missing_ids[:5])}"
            )
        if extra_ids:
            details.append(
                f"unexpected {len(extra_ids)} chunk(s), for example: "
                f"{', '.join(extra_ids[:5])}"
            )
        raise RuntimeError(
            "Persisted Chroma collection does not match expected chunks: "
            + "; ".join(details)
        )

    actual_count = len(actual_ids)
    expected_count = len(expected_ids)
    if actual_count != expected_count:
        raise RuntimeError(
            "Persisted Chroma collection count mismatch: "
            f"expected {expected_count}, got {actual_count}"
        )
