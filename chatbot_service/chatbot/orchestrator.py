"""Intent-aware orchestration for the travel question-answering chatbot."""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from django.conf import settings
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from chatbot.evidence_context import build_evidence_context
from chatbot.gemini_diagnostics import print_gemini_request
from chatbot.rag.rag_chain import get_chat_model, normalize_answer
from chatbot.semantic import (
    ConversationMessage,
    SemanticInterpretation,
    SemanticInterpreter,
    SemanticLocation,
)
from chatbot.tool_planner import PlannedToolCall, plan_tools
from chatbot.tools.mapbox_client import MapboxToolClient
from chatbot.tools.models import ChatSource
from chatbot.tools.registry import (
    MAPBOX_CATEGORY_SEARCH_TOOL_NAME,
    MAPBOX_FORWARD_SEARCH_TOOL_NAME,
    ToolExecution,
    ToolRegistry,
)


SYSTEM_PROMPT = """Bạn là trợ lý hỏi đáp du lịch tiếng Việt.

Backend đã phân tích intent, semantic action và tự thực thi các tool đọc dữ liệu phù hợp.
Hãy trả lời dựa trên semantic interpretation, lịch sử hội thoại và tool results được cung cấp.

Quy tắc bắt buộc:
- Dữ liệu địa điểm có thể thay đổi như địa chỉ, tọa độ, rating, giờ mở cửa, điện thoại và website chỉ được lấy từ evidence context; không tự tạo.
- Khi hiển thị địa điểm, trình bày từng nơi riêng và kèm fullAddress nếu có. Chỉ hiển thị rating, giờ mở cửa, điện thoại hoặc website khi field tương ứng thực sự có giá trị.
- Không loại bỏ địa điểm chỉ vì Mapbox không cung cấp rating và không tự tạo rating.
- Chỉ được đề xuất địa điểm có mapboxId xuất hiện trong evidence context đã được backend tinh chỉnh.
- Phân biệt status available, empty và failed: empty là không tìm thấy dữ liệu, failed là provider gặp lỗi. Vẫn dùng evidence còn lại khi một nhóm bị lỗi.
- Nếu status là needs_clarification, chỉ hỏi ngắn gọn thông tin còn thiếu.
- Nếu status là unsupported, giải thích rõ giới hạn hiện tại; không giả vờ đã chỉ đường, đọc giao thông thời gian thực, lưu lịch trình hay lưu dữ liệu người dùng.
- Itinerary chỉ là tư vấn dạng văn bản; không tuyên bố đã lưu hoặc tối ưu tuyến đường.
- Không nhắc tên tool, RAG, chunk, semantic schema hoặc JSON trong câu trả lời.
- Trả lời tự nhiên, sáng tạo và plain text tiếng Việt; không dùng bảng hoặc Markdown phức tạp.
"""

SEMANTIC_CONTEXT_TEMPLATE = """Phân tích đã được backend xác thực:
{semantic_json}
"""

TOOL_CONTEXT_TEMPLATE = """Evidence context đã được backend nhóm và tinh chỉnh:
{tool_json}
"""

NO_TOOL_CONTEXT = """Backend không cần gọi tool cho yêu cầu này. Hãy trả lời theo semantic interpretation và lịch sử hội thoại."""


class ToolInfrastructureError(RuntimeError):
    """Raised when every planned tool failed for infrastructure reasons."""


@dataclass(frozen=True)
class ChatOrchestratorResult:
    answer: str
    sources: list[ChatSource]
    interpretation: SemanticInterpretation | None = None


class ChatOrchestrator:
    """Interpret one question, execute a deterministic tool plan, then answer."""

    def __init__(
        self,
        chat_model: Any,
        registry: ToolRegistry,
        *,
        semantic_interpreter: SemanticInterpreter | None = None,
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
        self._registry = registry
        self._semantic_interpreter = (
            semantic_interpreter or SemanticInterpreter(chat_model)
        )
        self._max_tool_calls = resolved_max_calls

    def answer(
        self,
        question: str,
        *,
        history: Sequence[ConversationMessage] = (),
        current_location: SemanticLocation | None = None,
    ) -> ChatOrchestratorResult:
        cleaned_question = question.strip()
        if not cleaned_question:
            raise ValueError("question must not be empty")

        interpretation = self._semantic_interpreter.interpret(
            cleaned_question,
            history=history,
            current_location=current_location,
        )
        self._print_semantic_interpretation(interpretation)
        planned_calls = plan_tools(interpretation)[: self._max_tool_calls]
        executions = self._execute_plan(planned_calls)
        self._raise_if_all_tools_had_system_failures(executions)

        sources = self._collect_unique_sources(executions)
        messages = self._build_answer_messages(
            cleaned_question,
            history=history,
            interpretation=interpretation,
            planned_calls=planned_calls,
            executions=executions,
        )
        response = self._invoke_ai_message(self._chat_model, messages)
        self._print_model_response(response)
        return ChatOrchestratorResult(
            answer=self._normalized_response_text(response),
            sources=sources,
            interpretation=interpretation,
        )

    def _execute_plan(
        self,
        calls: Sequence[PlannedToolCall],
    ) -> list[ToolExecution]:
        executions: list[ToolExecution] = []
        coordinates: dict[str, tuple[float, float]] = {}
        destination_lookups: dict[str, ToolExecution] = {}

        for call in calls:
            arguments = dict(call.arguments)
            if (
                call.name == MAPBOX_CATEGORY_SEARCH_TOOL_NAME
                and "proximity" not in arguments
                and call.destination is not None
            ):
                destination_coordinates = coordinates.get(call.destination)
                if destination_coordinates is None:
                    executions.append(
                        self._category_without_coordinates(
                            destination_lookups.get(call.destination)
                        )
                    )
                    continue
                longitude, latitude = destination_coordinates
                arguments.pop("near", None)
                arguments["proximity"] = f"{longitude},{latitude}"

            execution = self._registry.execute(call.name, arguments)
            executions.append(execution)
            if (
                call.name == MAPBOX_FORWARD_SEARCH_TOOL_NAME
                and call.destination is not None
            ):
                destination_lookups[call.destination] = execution
                destination_coordinates = self._coordinates_from_execution(execution)
                if destination_coordinates is not None:
                    coordinates[call.destination] = destination_coordinates

        return executions

    @staticmethod
    def _coordinates_from_execution(
        execution: ToolExecution,
    ) -> tuple[float, float] | None:
        if not execution.success:
            return None
        try:
            payload = json.loads(execution.content)
        except (json.JSONDecodeError, TypeError):
            return None
        data = payload.get("data") if isinstance(payload, dict) else None
        results = data.get("results") if isinstance(data, dict) else None
        if not isinstance(results, list):
            return None
        for result in results:
            if not isinstance(result, dict):
                continue
            longitude = result.get("longitude")
            latitude = result.get("latitude")
            if (
                isinstance(longitude, (int, float))
                and not isinstance(longitude, bool)
                and isinstance(latitude, (int, float))
                and not isinstance(latitude, bool)
            ):
                return float(longitude), float(latitude)
        return None

    @staticmethod
    def _category_without_coordinates(
        lookup: ToolExecution | None,
    ) -> ToolExecution:
        if lookup is not None and not lookup.success:
            content = json.dumps(
                {
                    "success": False,
                    "data": None,
                    "errorCode": "destination_lookup_failed",
                    "errorMessage": (
                        "Không thể tìm tọa độ điểm đến trước khi tìm category."
                    ),
                },
                ensure_ascii=False,
                separators=(",", ":"),
            )
            return ToolExecution(
                content=content,
                sources=(),
                success=False,
                system_failure=lookup.system_failure,
                error_code="destination_lookup_failed",
            )

        return ToolExecution(
            content=(
                '{"success":true,"data":{"results":[],"rawResponse":{}}}'
            ),
            sources=(),
            success=True,
            system_failure=False,
        )

    @staticmethod
    def _build_answer_messages(
        question: str,
        *,
        history: Sequence[ConversationMessage],
        interpretation: SemanticInterpretation,
        planned_calls: Sequence[PlannedToolCall],
        executions: Sequence[ToolExecution],
    ) -> list[Any]:
        semantic_content = SEMANTIC_CONTEXT_TEMPLATE.format(
            semantic_json=interpretation.model_dump_json(exclude_none=True),
        )
        tool_content = ChatOrchestrator._tool_context_content(
            planned_calls,
            executions,
        )
        messages: list[Any] = [
            SystemMessage(content=SYSTEM_PROMPT),
            SystemMessage(content=semantic_content),
            SystemMessage(content=tool_content),
        ]
        for message in history:
            if message.role == "user":
                messages.append(HumanMessage(content=message.content))
            else:
                messages.append(AIMessage(content=message.content))
        messages.append(HumanMessage(content=question))
        return messages

    @staticmethod
    def _tool_context_content(
        calls: Sequence[PlannedToolCall],
        executions: Sequence[ToolExecution],
    ) -> str:
        if not calls:
            return NO_TOOL_CONTEXT
        payload = build_evidence_context(calls, executions)
        return TOOL_CONTEXT_TEMPLATE.format(
            tool_json=json.dumps(
                payload,
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )

    @staticmethod
    def _invoke_ai_message(model: Any, messages: list[Any]) -> AIMessage:
        print_gemini_request("final_synthesis", messages)
        response = model.invoke(messages)
        if not isinstance(response, AIMessage):
            raise RuntimeError("Gemini returned an unsupported response type")
        return response

    @staticmethod
    def _print_semantic_interpretation(
        interpretation: SemanticInterpretation,
    ) -> None:
        """Print only Gemini's validated semantic result, never its request."""
        interpretation_json = json.dumps(
            interpretation.model_dump(mode="json", exclude_none=True),
            ensure_ascii=False,
            indent=2,
        )
        output = f"SemanticInterpretation result:\n{interpretation_json}\n"
        stdout_buffer = getattr(sys.stdout, "buffer", None)
        if stdout_buffer is not None:
            stdout_buffer.write(output.encode("utf-8"))
            stdout_buffer.flush()
            return
        print(output, end="", flush=True)

    @staticmethod
    def _print_model_response(response: AIMessage) -> None:
        """Print only Gemini's response, never the request or tool payloads."""
        response_json = json.dumps(
            response.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
        )
        output = f"Gemini response:\n{response_json}\n"
        stdout_buffer = getattr(sys.stdout, "buffer", None)
        if stdout_buffer is not None:
            stdout_buffer.write(output.encode("utf-8"))
            stdout_buffer.flush()
            return
        print(output, end="", flush=True)

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
    def _collect_unique_sources(
        executions: Sequence[ToolExecution],
    ) -> list[ChatSource]:
        sources: list[ChatSource] = []
        source_keys: set[str] = set()
        for execution in executions:
            for source in execution.sources:
                source_key = source.model_dump_json()
                if source_key in source_keys:
                    continue
                source_keys.add(source_key)
                sources.append(source)
        return sources

    @staticmethod
    def _raise_if_all_tools_had_system_failures(
        executions: Sequence[ToolExecution],
    ) -> None:
        if (
            executions
            and not any(execution.success for execution in executions)
            and all(execution.system_failure for execution in executions)
        ):
            raise ToolInfrastructureError(
                "All planned tools failed because of infrastructure errors."
            )


def orchestrate_chat(
    question: str,
    *,
    history: Sequence[ConversationMessage] = (),
    current_location: SemanticLocation | None = None,
    chat_model: Any | None = None,
    registry: ToolRegistry | None = None,
    semantic_interpreter: SemanticInterpreter | None = None,
    max_tool_calls: int | None = None,
) -> ChatOrchestratorResult:
    """Run one stateless request and close owned HTTP resources."""
    active_model = chat_model or get_chat_model()
    if registry is not None:
        return ChatOrchestrator(
            active_model,
            registry,
            semantic_interpreter=semantic_interpreter,
            max_tool_calls=max_tool_calls,
        ).answer(
            question,
            history=history,
            current_location=current_location,
        )

    with MapboxToolClient() as mapbox_client:
        active_registry = ToolRegistry(mapbox_client)
        return ChatOrchestrator(
            active_model,
            active_registry,
            semantic_interpreter=semantic_interpreter,
            max_tool_calls=max_tool_calls,
        ).answer(
            question,
            history=history,
            current_location=current_location,
        )


__all__ = [
    "ChatOrchestrator",
    "ChatOrchestratorResult",
    "NO_TOOL_CONTEXT",
    "SEMANTIC_CONTEXT_TEMPLATE",
    "SYSTEM_PROMPT",
    "TOOL_CONTEXT_TEMPLATE",
    "ToolInfrastructureError",
    "orchestrate_chat",
]
