"""HTTP views and response helpers for the travel chatbot API."""

import logging
from collections.abc import Iterable

from langchain_core.documents import Document
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .rag.rag_chain import answer_question
from .serializers import ChatRequestSerializer


logger = logging.getLogger(__name__)

CHAT_SERVICE_ERROR = "Chatbot hiện không thể trả lời. Vui lòng thử lại sau."


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


class ChatAPIView(APIView):
    """Answer one travel question with the existing RAG pipeline."""

    def post(self, request):
        serializer = ChatRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        message = serializer.validated_data["message"]
        try:
            result = answer_question(message)
        except Exception:
            logger.exception("Travel chatbot request failed")
            return Response(
                {"error": CHAT_SERVICE_ERROR},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(
            {
                "answer": result.answer,
                "sources": build_sources(result.documents),
            },
            status=status.HTTP_200_OK,
        )


__all__ = ["CHAT_SERVICE_ERROR", "ChatAPIView", "build_sources"]
