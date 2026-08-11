"""Ask the travel RAG chain from the command line."""

from __future__ import annotations

import sys

from django.core.management.base import BaseCommand, CommandError
from langchain_core.documents import Document

from chatbot.rag.rag_chain import RAGResult, answer_question


def _console_safe(text: str) -> str:
    """Avoid Windows console encoding errors for Vietnamese text."""
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    return text.encode(encoding, errors="replace").decode(encoding)


class Command(BaseCommand):
    help = "Ask the travel RAG chatbot a question."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "question",
            help="Question to ask the travel chatbot.",
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
            result = answer_question(question, top_k=top_k)
        except Exception as exc:
            raise CommandError(str(exc)) from exc

        if not isinstance(result, RAGResult):
            raise CommandError("RAG chain returned an invalid result")

        self.stdout.write(_console_safe(f"Question: {question}"))
        self.stdout.write(_console_safe(f"\nAnswer:\n{result.answer}"))
        self.stdout.write("\nSources:")

        if not result.documents:
            self.stdout.write("None")
            return

        for index, document in enumerate(result.documents, start=1):
            if not isinstance(document, Document):
                raise CommandError("RAG chain returned an invalid document")

            metadata = document.metadata
            title = metadata.get("title", "unknown")
            source = metadata.get("source", "unknown")
            self.stdout.write(
                _console_safe(f"[{index}] {title} — {source}")
            )
