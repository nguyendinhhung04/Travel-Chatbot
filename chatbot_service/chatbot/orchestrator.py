"""Gemini function-calling loop for the travel chatbot."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from django.conf import settings
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from chatbot.rag.rag_chain import get_chat_model, normalize_answer
from chatbot.tools.mapbox_client import MapboxToolClient
from chatbot.tools.models import ChatSource
from chatbot.tools.registry import ToolExecution, ToolRegistry


SYSTEM_PROMPT = """Bạn là trợ lý du lịch tiếng Việt sử dụng các tool được cung cấp.

Quy tắc bắt buộc:
- Chỉ trả lời trực tiếp mà không gọi tool đối với lời chào, câu hỏi làm rõ hoặc thông báo phạm vi hỗ trợ.
- Mọi khẳng định hoặc tư vấn có nội dung du lịch phải dựa trên ít nhất một tool.
- Dùng search_travel_knowledge cho kiến thức, lịch sử, văn hóa, kinh nghiệm và lịch trình.
- Dùng các Mapbox tool cho địa điểm, địa chỉ, POI, category hoặc tọa độ.
- Khi chưa biết canonical category_id, gọi mapbox_list_categories trước mapbox_category_search.
- Có thể gọi nhiều tool tuần tự khi câu hỏi cần kết hợp Knowledge Base và dữ liệu địa điểm.
- Không tự tạo tên địa điểm, địa chỉ, tọa độ hoặc thông tin không xuất hiện trong tool result.
- Nếu tool báo arguments không hợp lệ, sửa arguments và thử lại khi còn lượt.
- Nếu không tìm thấy dữ liệu, nói rõ là chưa tìm thấy; không suy đoán.
- Khi hiển thị các địa điểm tìm được từ Mapbox, hãy trình bày từng địa điểm riêng và luôn kèm địa chỉ đầy đủ nếu có.
- Với mỗi địa điểm, ưu tiên địa chỉ từ results[].fullAddress. Đọc giờ mở cửa, phone và website từ feature tương ứng trong rawResponse, bao gồm properties và properties.metadata.
- Giờ mở cửa phải được rút gọn, dễ đọc, ví dụ "07:00–22:00" hoặc "T2–CN: 07:00–22:00", nhưng phải giữ đúng dữ liệu tool cung cấp.
- Chỉ hiển thị dòng Giờ mở cửa, Điện thoại hoặc Website khi field tương ứng thực sự có giá trị; không tự suy đoán và không ghi nội dung thay thế như "không có thông tin".
- Trả lời bằng tiếng Việt, tự nhiên, ngắn gọn và plain text; không dùng bảng hoặc Markdown phức tạp.
"""

FINAL_SYNTHESIS_INSTRUCTION = """Hãy trả lời câu hỏi ban đầu ngay bây giờ bằng cách tổng hợp duy nhất từ các tool result đã có. Không gọi thêm tool, không bịa thông tin, tuân thủ quy tắc hiển thị chi tiết địa điểm trong system prompt và dùng plain text tiếng Việt."""

TOOL_BUDGET_ERROR = "tool_budget_exceeded"


class ToolInfrastructureError(RuntimeError):
    """Raised when every requested tool failed for infrastructure reasons."""


@dataclass(frozen=True)
class ChatOrchestratorResult:
    answer: str
    sources: list[ChatSource]


class ChatOrchestrator:
    """Run Gemini tool decisions until it returns text or exhausts the budget."""

    def __init__(
        self,
        chat_model: Any,
        registry: ToolRegistry,
        *,
        max_tool_calls: int | None = None,
    ) -> None:
        resolved_max_calls = (
            settings.CHATBOT_MAX_TOOL_CALLS
            if max_tool_calls is None
            else max_tool_calls
        )
        if isinstance(resolved_max_calls, bool) or not isinstance(
            resolved_max_calls,
            int,
        ):
            raise ValueError("max_tool_calls must be an integer")
        if resolved_max_calls <= 0:
            raise ValueError("max_tool_calls must be greater than zero")

        self._chat_model = chat_model
        self._tool_model = chat_model.bind_tools(registry.langchain_tools)
        self._registry = registry
        self._max_tool_calls = resolved_max_calls

    def answer(self, question: str) -> ChatOrchestratorResult:
        cleaned_question = question.strip()
        if not cleaned_question:
            raise ValueError("question must not be empty")

        messages: list[Any] = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=cleaned_question),
        ]
        executions: list[ToolExecution] = []
        sources: list[ChatSource] = []
        source_keys: set[str] = set()
        executed_calls = 0

        while True:
            response = self._invoke_ai_message(self._tool_model, messages)
            messages.append(response)
            tool_calls = response.tool_calls

            if not tool_calls:
                self._raise_if_all_tools_had_system_failures(executions)
                return ChatOrchestratorResult(
                    answer=self._normalized_response_text(response),
                    sources=sources,
                )

            budget_exhausted = False
            for tool_call in tool_calls:
                call_id = str(
                    tool_call.get("id")
                    or f"tool-call-{executed_calls + 1}"
                )
                name = str(tool_call.get("name") or "")

                if executed_calls >= self._max_tool_calls:
                    messages.append(
                        ToolMessage(
                            content=self._budget_error_content(),
                            tool_call_id=call_id,
                            name=name or None,
                            status="error",
                        )
                    )
                    budget_exhausted = True
                    continue

                executed_calls += 1
                execution = self._registry.execute(name, tool_call.get("args", {}))
                executions.append(execution)
                self._append_unique_sources(
                    execution.sources,
                    sources,
                    source_keys,
                )
                messages.append(
                    ToolMessage(
                        content=execution.content,
                        tool_call_id=call_id,
                        name=name or None,
                        status="success" if execution.success else "error",
                    )
                )

            if executed_calls >= self._max_tool_calls or budget_exhausted:
                self._raise_if_all_tools_had_system_failures(executions)
                final_messages = [
                    *messages,
                    HumanMessage(content=FINAL_SYNTHESIS_INSTRUCTION),
                ]
                final_response = self._invoke_ai_message(
                    self._chat_model,
                    final_messages,
                )
                return ChatOrchestratorResult(
                    answer=self._normalized_response_text(final_response),
                    sources=sources,
                )

    @staticmethod
    def _invoke_ai_message(model: Any, messages: list[Any]) -> AIMessage:
        response = model.invoke(messages)
        if not isinstance(response, AIMessage):
            raise RuntimeError("Gemini returned an unsupported response type")
        return response

    @staticmethod
    def _normalized_response_text(response: AIMessage) -> str:
        answer = response.text.strip()
        if not answer:
            raise RuntimeError("Gemini returned an empty answer")
        normalized = normalize_answer(answer)
        if not normalized:
            raise RuntimeError("Gemini returned an empty answer")
        return normalized

    @staticmethod
    def _append_unique_sources(
        new_sources: tuple[ChatSource, ...],
        sources: list[ChatSource],
        source_keys: set[str],
    ) -> None:
        for source in new_sources:
            source_key = source.model_dump_json()
            if source_key in source_keys:
                continue
            source_keys.add(source_key)
            sources.append(source)

    @staticmethod
    def _raise_if_all_tools_had_system_failures(
        executions: list[ToolExecution],
    ) -> None:
        if (
            executions
            and not any(execution.success for execution in executions)
            and all(execution.system_failure for execution in executions)
        ):
            raise ToolInfrastructureError(
                "All requested tools failed because of infrastructure errors."
            )

    @staticmethod
    def _budget_error_content() -> str:
        return json.dumps(
            {
                "success": False,
                "data": None,
                "errorCode": TOOL_BUDGET_ERROR,
                "errorMessage": "Đã đạt giới hạn số lần gọi tool.",
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )


def orchestrate_chat(
    question: str,
    *,
    chat_model: Any | None = None,
    registry: ToolRegistry | None = None,
    max_tool_calls: int | None = None,
) -> ChatOrchestratorResult:
    """Run one stateless chatbot request and close owned HTTP resources."""
    active_model = chat_model or get_chat_model()
    if registry is not None:
        return ChatOrchestrator(
            active_model,
            registry,
            max_tool_calls=max_tool_calls,
        ).answer(question)

    with MapboxToolClient() as mapbox_client:
        active_registry = ToolRegistry(mapbox_client)
        return ChatOrchestrator(
            active_model,
            active_registry,
            max_tool_calls=max_tool_calls,
        ).answer(question)


__all__ = [
    "ChatOrchestrator",
    "ChatOrchestratorResult",
    "SYSTEM_PROMPT",
    "ToolInfrastructureError",
    "orchestrate_chat",
]
