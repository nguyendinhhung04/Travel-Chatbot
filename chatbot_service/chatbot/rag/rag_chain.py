"""Prompt and Gemini Chat helpers for the travel RAG pipeline."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from django.conf import settings
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

from .retrieval import retrieve_documents


INSUFFICIENT_CONTEXT_MESSAGE = "Knowledge Base hiện chưa có đủ thông tin."

RAG_PROMPT = """Bạn là tư vấn viên du lịch tiếng Việt, thân thiện và thực tế.

Ưu tiên Context và không mâu thuẫn với nó. Có thể bổ sung kiến thức ổn định, đáng
tin cậy nhưng không suy đoán. Nếu Context không có dữ liệu có thể thay đổi như giá,
giờ mở cửa, thời tiết, sự kiện hoặc quy định, nhắc người dùng kiểm tra lại.

Trả lời thẳng, tự nhiên, sáng tạo và đủ giúp người dùng quyết định. Không nhắc
Context, tài liệu, Knowledge Base, RAG, nguồn dữ liệu hoặc tự nhận đã trải nghiệm.
Nếu cả Context và kiến thức đáng tin cậy đều không đủ, trả lời chính xác:
Knowledge Base hiện chưa có đủ thông tin.

Dùng plain text, không dùng bảng hay Markdown. Khi cần danh sách, dùng ký hiệu •,
không lồng nhiều cấp và để dòng trống giữa các nhóm.

Context:
{context}

Question:
{question}
"""


@dataclass(frozen=True)
class RAGResult:
    """Answer together with the chunks used to create it."""

    answer: str
    documents: list[Document]


def get_chat_model(
    *,
    api_key: str | None = None,
    model: str | None = None,
) -> ChatGoogleGenerativeAI:
    """Create the configured Gemini Chat model without making an API call."""
    resolved_api_key = api_key or settings.GEMINI_API_KEY
    if not resolved_api_key:
        raise ValueError(
            "GEMINI_API_KEY is missing. Set it in the .env file or environment."
        )

    resolved_model = model or settings.GEMINI_CHAT_MODEL
    if not resolved_model:
        raise ValueError("GEMINI_CHAT_MODEL must not be empty")

    return ChatGoogleGenerativeAI(
        model=resolved_model,
        api_key=resolved_api_key,
        temperature=0.8,
    )


def format_context(documents: list[Document]) -> str:
    """Format retrieved chunks so the model can identify their sources."""
    sections: list[str] = []
    for index, document in enumerate(documents, start=1):
        metadata = document.metadata
        heading = (
            metadata.get("header_3")
            or metadata.get("header_2")
            or metadata.get("header_1")
            or "(không có heading)"
        )
        sections.append(
            "\n".join(
                [
                    f"[Tài liệu {index}]",
                    f"Title: {metadata.get('title', 'unknown')}",
                    f"Source: {metadata.get('source', 'unknown')}",
                    f"Heading: {heading}",
                    f"Nội dung:\n{document.page_content}",
                ]
            )
        )
    return "\n\n---\n\n".join(sections)


def build_prompt_template() -> PromptTemplate:
    """Create the simple grounded-answer prompt used by the RAG chain."""
    return PromptTemplate.from_template(RAG_PROMPT)


def normalize_answer(answer: str) -> str:
    """Make model output readable in the frontend's plain-text message bubble."""
    normalized_lines: list[str] = []
    previous_line_was_blank = False

    for raw_line in answer.strip().splitlines():
        line = raw_line.strip()

        if not line:
            if normalized_lines and not previous_line_was_blank:
                normalized_lines.append("")
            previous_line_was_blank = True
            continue

        line = re.sub(r"^#{1,6}\s+", "", line)
        line = re.sub(r"^[-*+]\s+", "• ", line)
        line = re.sub(r"\*\*(.+?)\*\*", r"\1", line)
        line = re.sub(r"__(.+?)__", r"\1", line)
        line = re.sub(r"(?<!\w)\*([^*\n]+)\*(?!\w)", r"\1", line)
        line = re.sub(r"(?<!\w)_([^_\n]+)_(?!\w)", r"\1", line)

        normalized_lines.append(line)
        previous_line_was_blank = False

    return "\n".join(normalized_lines).strip()


def build_rag_chain(*, chat_model: Any | None = None) -> Any:
    """Build the prompt -> Gemini -> text parser chain."""
    prompt = build_prompt_template()
    model = chat_model or get_chat_model()
    return prompt | model | StrOutputParser()

#Main function
def answer_question(
    question: str,
    *,
    retriever: Any | None = None,
    chain: Any | None = None,
    top_k: int | None = None,
) -> RAGResult:
    """Retrieve context and generate one grounded answer."""
    cleaned_question = question.strip()
    if not cleaned_question:
        raise ValueError("question must not be empty")

    #Get the K documents from KB that most similar to the question
    documents = retrieve_documents(
        cleaned_question,
        retriever=retriever,
        top_k=top_k,
    )
    if not documents:
        return RAGResult(
            answer=INSUFFICIENT_CONTEXT_MESSAGE,
            documents=[],
        )

    active_chain = chain if chain is not None else build_rag_chain()
    answer = active_chain.invoke(
        {
            "context": format_context(documents),
            "question": cleaned_question,
        }
    )
    if not isinstance(answer, str) or not answer.strip():
        raise RuntimeError("Gemini returned an empty answer")

    normalized_answer = normalize_answer(answer)
    if not normalized_answer:
        raise RuntimeError("Gemini returned an empty answer")

    return RAGResult(answer=normalized_answer, documents=documents)


__all__ = [
    "INSUFFICIENT_CONTEXT_MESSAGE",
    "RAGResult",
    "RAG_PROMPT",
    "answer_question",
    "build_rag_chain",
    "build_prompt_template",
    "format_context",
    "get_chat_model",
    "normalize_answer",
]
