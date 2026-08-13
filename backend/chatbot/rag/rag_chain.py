"""Prompt and Gemini Chat helpers for the travel RAG pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.conf import settings
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

from .retrieval import retrieve_documents


INSUFFICIENT_CONTEXT_MESSAGE = "Knowledge Base hiện chưa có đủ thông tin."

RAG_PROMPT = """Bạn là trợ lý du lịch.

Chỉ trả lời dựa trên Context được cung cấp. Không tự bịa hoặc bổ sung thông tin
từ bên ngoài Context. Nếu Context không có đủ thông tin để trả lời Question,
hãy trả lời chính xác: Knowledge Base hiện chưa có đủ thông tin.

Trả lời bằng tiếng Việt, ngắn gọn và dễ hiểu.

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
        temperature=0,
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

    return RAGResult(answer=answer.strip(), documents=documents)


__all__ = [
    "INSUFFICIENT_CONTEXT_MESSAGE",
    "RAGResult",
    "RAG_PROMPT",
    "answer_question",
    "build_rag_chain",
    "build_prompt_template",
    "format_context",
    "get_chat_model",
]
