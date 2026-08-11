"""Ingest the Markdown knowledge base into the persistent Chroma store."""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from chatbot.rag.embeddings import get_embedding_model, verify_embedding
from chatbot.rag.ingestion import (
    collect_chunk_ids,
    format_chunk_preview,
    load_markdown_documents,
    split_documents,
)
from chatbot.rag.vector_store import (
    get_vector_store,
    sync_vector_store,
    verify_vector_store,
)


def _console_safe(text: str) -> str:
    """Avoid Windows console encoding failures when previewing Vietnamese text."""
    import sys

    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    return text.encode(encoding, errors="replace").decode(encoding)


class Command(BaseCommand):
    help = "Load the travel knowledge base, chunk it, and sync it into Chroma."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Load, validate and chunk documents without calling Gemini or Chroma.",
        )

    def handle(self, *args, **options) -> None:
        dry_run = options["dry_run"]

        try:
            documents = load_markdown_documents()
            chunks = split_documents(documents)
        except Exception as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(f"Loaded documents: {len(documents)}")
        self.stdout.write(f"Created chunks: {len(chunks)}")

        sample_chunks = chunks[:3]
        if sample_chunks:
            self.stdout.write("Sample chunks:")
            for index, chunk in enumerate(sample_chunks, start=1):
                self.stdout.write(f"[{index}]")
                self.stdout.write(_console_safe(format_chunk_preview(chunk)))
        else:
            self.stdout.write("Sample chunks: none")

        if dry_run:
            self.stdout.write("Dry run completed successfully")
            return

        try:
            embedding_model = get_embedding_model()
            dimension = verify_embedding(embedding_model)
            vector_store = get_vector_store(embedding_model=embedding_model)
            stats = sync_vector_store(vector_store, chunks)
            expected_ids = collect_chunk_ids(chunks)
            verify_vector_store(expected_ids, embedding_model=embedding_model)
        except Exception as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(f"Embedding dimension: {dimension}")
        self.stdout.write(f"Added: {stats.added}")
        self.stdout.write(f"Unchanged: {stats.unchanged}")
        self.stdout.write(f"Deleted: {stats.deleted}")
        self.stdout.write(f"Persisted chunks: {len(expected_ids)}")
        self.stdout.write("Ingestion completed successfully")
