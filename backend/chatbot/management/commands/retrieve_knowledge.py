"""Search the travel knowledge base and print the retrieved chunks."""

from __future__ import annotations

import sys

from django.core.management.base import BaseCommand, CommandError
from langchain_core.documents import Document

from chatbot.rag.ingestion import format_chunk_preview
from chatbot.rag.retrieval import retrieve_documents


def _console_safe(text: str) -> str:
    """Avoid Windows console encoding errors for Vietnamese text."""
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    return text.encode(encoding, errors="replace").decode(encoding)


class Command(BaseCommand):
    help = "Search the travel knowledge base with similarity retrieval."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "question",
            help="Question to search for in the travel knowledge base.",
        )
        parser.add_argument(
            "--top-k",
            type=int,
            default=None,
            help="Number of chunks to retrieve (default: configured value).",
        )

    def handle(self, *args, **options) -> None:
        question = options["question"]
        top_k = options["top_k"]

        try:
            documents = retrieve_documents(question, top_k=top_k)
        except Exception as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(_console_safe(f"Question: {question}"))
        self.stdout.write(f"Results: {len(documents)}")

        if not documents:
            self.stdout.write(
                "No documents found. Check that the Knowledge Base has been ingested."
            )
            return

        for index, document in enumerate(documents, start=1):
            if not isinstance(document, Document):
                raise CommandError("Retriever returned an invalid document")

            self.stdout.write(f"\n[{index}]")
            self.stdout.write(
                _console_safe(format_chunk_preview(document, max_chars=500))
            )
