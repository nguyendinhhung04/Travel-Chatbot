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

RAG_PROMPT = """Bạn là một tư vấn viên du lịch thân thiện, thực tế và giàu kinh nghiệm.

Hãy trả lời như đang tư vấn trực tiếp cho một du khách, giúp họ dễ dàng quyết định
nên đi đâu, làm gì và chuẩn bị như thế nào. Trả lời thẳng vào câu hỏi, ưu tiên các
gợi ý cụ thể, hữu ích và có thể áp dụng. Khi phù hợp, hãy sắp xếp gợi ý theo khu
vực, thời gian hoặc nhu cầu của du khách; giải thích rõ lý do hoặc lưu ý thực tế
nếu Context có thông tin đó.

Ưu tiên sử dụng thông tin trong Context làm cơ sở chính cho câu trả lời. Nếu
Context có thông tin liên quan, hãy trình bày thông tin đó trước và không được
mâu thuẫn với Context. Bạn có thể dùng kiến thức của mình để bổ sung những thông
tin hữu ích mà Context chưa đề cập, nhưng không được tự bịa hoặc suy đoán khi
không chắc chắn. Với thông tin có thể thay đổi theo thời gian như giá vé, giờ mở
cửa, thời tiết, sự kiện hoặc quy định, hãy nói rõ người dùng nên kiểm tra lại nếu
Context không cung cấp thông tin cập nhật.

Không khẳng định bạn đã trực tiếp trải nghiệm địa điểm và không nhắc đến Context,
tài liệu, Knowledge Base, nguồn dữ liệu, RAG hay cách hệ thống tạo ra câu trả lời.
Không mở đầu bằng các câu như "Dựa vào tài liệu bạn cung cấp", "Theo Context"
hoặc "Tài liệu cho biết".

Trả lời bằng tiếng Việt, tự nhiên, gần gũi, sáng tạo và dễ hiểu. Nếu cả Context
và kiến thức đáng tin cậy của bạn đều không đủ để trả lời Question, hãy trả lời
chính xác: Knowledge Base hiện chưa có đủ thông tin.

Định dạng câu trả lời bằng plain text thân thiện với khung chat:
- Không dùng Markdown hoặc ký hiệu Markdown như **, *, #, backtick, bảng hay dấu
  gạch đầu dòng Markdown.
- Nếu có nhiều nhóm gợi ý, viết tên nhóm trên một dòng riêng, để một dòng trống
  giữa các nhóm và dùng ký hiệu • cho từng ý.
- Không lồng quá nhiều cấp danh sách. Mỗi ý cần rõ ràng, hữu ích và tự nhiên.

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
