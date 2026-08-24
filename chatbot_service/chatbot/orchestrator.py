"""Intent-aware orchestration for the travel question-answering chatbot."""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from django.conf import settings
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from chatbot.destination_discovery import (
    DestinationCandidateGenerator,
    DestinationDiscoveryPipeline,
)
from chatbot.intent import TravelIntent
from chatbot.rag.rag_chain import get_chat_model, normalize_answer
from chatbot.response_policy import response_policy_for
from chatbot.semantic import (
    ConversationMessage,
    SemanticInterpretation,
    SemanticInterpreter,
    SemanticLocation,
)
from chatbot.tool_planner import PlannedToolCall, plan_tools
from chatbot.tools.mapbox_client import MapboxToolClient
from chatbot.tools.models import ChatSource
from chatbot.tools.registry import ToolExecution, ToolRegistry


SYSTEM_PROMPT = """Bạn là trợ lý hỏi đáp du lịch tiếng Việt.

Backend đã phân tích intent, semantic action và tự thực thi các tool đọc dữ liệu phù hợp.
Hãy trả lời dựa trên semantic interpretation, lịch sử hội thoại và tool results được cung cấp.

Quy tắc bắt buộc:
- Tuân thủ chính sách evidence theo primary_intent được cung cấp trong system message riêng; không tự thay đổi thứ tự ưu tiên nguồn.
- Dữ liệu địa điểm có thể thay đổi như địa chỉ, tọa độ, giờ mở cửa, điện thoại và website chỉ được lấy từ Mapbox tool result; không tự tạo.
- Khi hiển thị địa điểm, trình bày từng nơi riêng và kèm fullAddress nếu có. Chỉ hiển thị giờ mở cửa, điện thoại, website hoặc rating khi rawResponse thực sự có giá trị.
- Không loại bỏ địa điểm chỉ vì Mapbox không cung cấp rating và không tự tạo rating.
- rawResponse chỉ dùng để bổ sung metadata cho đúng địa điểm trong data.results, không dùng để đưa thêm địa điểm đã bị backend loại.
- Nếu status là needs_clarification, chỉ hỏi ngắn gọn thông tin còn thiếu.
- Nếu status là unsupported, giải thích rõ giới hạn hiện tại; không giả vờ đã chỉ đường, đọc giao thông thời gian thực, lưu lịch trình hay lưu dữ liệu người dùng.
- Itinerary chỉ là tư vấn dạng văn bản; không tuyên bố đã lưu hoặc tối ưu tuyến đường.
- Không nhắc tên tool, RAG, chunk, semantic schema hoặc JSON trong câu trả lời.
- Trả lời tự nhiên, sáng tạo và plain text tiếng Việt; không dùng bảng hoặc Markdown phức tạp.
- Không đặt giới hạn trả lời ngắn. Độ dài phải đủ để phân tích, đưa nhận xét và giúp người dùng ra quyết định; không kéo dài bằng câu sáo rỗng hoặc lặp lại dữ liệu.
- Không dùng một khuôn cố định cho mọi câu trả lời. Tự chọn cách trình bày theo câu hỏi, số lượng địa điểm và loại trải nghiệm: đoạn tư vấn, danh sách đánh số, gạch đầu dòng hoặc nhóm theo chủ đề/buổi trong ngày.
- Khi có nhiều địa điểm, vẫn phải dễ quét: tách từng địa điểm hoặc từng nhóm bằng dòng trống. Có thể dùng "Địa chỉ:" và "Liên hệ:" cho dữ liệu thực tế, nhưng phần review và khuyến nghị phải viết thành câu tự nhiên.
- Không lặp các nhãn như "Điểm nổi bật:", "Đánh giá tư vấn:" hoặc "Có nên đi:" cho mọi địa điểm. Chỉ đưa kết luận trực tiếp khi người dùng hỏi hoặc khi nó thực sự giúp phân biệt lựa chọn; ưu tiên cách nói tự nhiên như "rất đáng ghé nếu..." hoặc "có thể bỏ qua nếu...".
- Bỏ hoàn toàn nhãn không có dữ liệu. Không dồn tên, địa chỉ và mô tả của nhiều địa điểm vào cùng một đoạn văn.
- Kết thúc bằng gợi ý lựa chọn, cách kết hợp các điểm hoặc một câu hỏi tiếp nối có ích để cá nhân hóa tư vấn; tránh câu kết sáo rỗng như chúc chuyến đi đáng nhớ.
"""

SEMANTIC_CONTEXT_TEMPLATE = """Phân tích đã được backend xác thực:
{semantic_json}
"""

TOOL_CONTEXT_TEMPLATE = """Kết quả các tool đọc dữ liệu do backend đã chọn:
{tool_json}
"""

DESTINATION_DISCOVERY_CONTEXT_TEMPLATE = """Evidence đã được backend đối chiếu cho destination_discovery:
{evidence_json}
Chỉ các địa điểm trong matchedCandidates và additionalMapboxPlaces được phép xuất hiện trong danh sách đề xuất cuối.
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
        candidate_generator: DestinationCandidateGenerator | None = None,
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
        self._candidate_generator = candidate_generator
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
        destination_evidence: dict[str, Any] | None = None
        tool_plan = plan_tools(interpretation)
        if (
            interpretation.primary_intent == TravelIntent.DESTINATION_DISCOVERY
            and tool_plan
        ):
            discovery_run = DestinationDiscoveryPipeline(
                self._chat_model,
                self._registry,
                max_tool_calls=self._max_tool_calls,
                candidate_generator=self._candidate_generator,
            ).execute(
                cleaned_question,
                history=history,
                interpretation=interpretation,
                planned_calls=tool_plan,
            )
            planned_calls = discovery_run.calls
            executions = discovery_run.executions
            destination_evidence = discovery_run.evidence
        else:
            planned_calls = list(tool_plan[: self._max_tool_calls])
            executions = self._execute_plan(planned_calls)
        self._raise_if_all_tools_had_system_failures(executions)

        sources = self._collect_unique_sources(executions)
        messages = self._build_answer_messages(
            cleaned_question,
            history=history,
            interpretation=interpretation,
            planned_calls=planned_calls,
            executions=executions,
            destination_evidence=destination_evidence,
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
        destination_coordinates: dict[str, tuple[float, float]] = {}
        for call in calls:
            arguments = dict(call.arguments)
            if (
                call.name == "mapbox_category_search"
                and call.destination is not None
                and "proximity" not in arguments
            ):
                coordinates = destination_coordinates.get(call.destination)
                if coordinates is None:
                    arguments["near"] = call.destination
                else:
                    longitude, latitude = coordinates
                    arguments.pop("near", None)
                    arguments["proximity"] = f"{longitude},{latitude}"

            execution = self._registry.execute(call.name, arguments)
            executions.append(execution)
            if (
                call.evidence_kind == "destination_location"
                and call.destination is not None
            ):
                coordinates = self._first_result_coordinates(execution)
                if coordinates is not None:
                    destination_coordinates[call.destination] = coordinates
        return executions

    @staticmethod
    def _first_result_coordinates(
        execution: ToolExecution,
    ) -> tuple[float, float] | None:
        if not execution.success:
            return None
        try:
            payload = json.loads(execution.content)
            result = payload["data"]["results"][0]
            longitude = float(result["longitude"])
            latitude = float(result["latitude"])
        except (KeyError, IndexError, TypeError, ValueError):
            return None
        return longitude, latitude

    @staticmethod
    def _build_answer_messages(
        question: str,
        *,
        history: Sequence[ConversationMessage],
        interpretation: SemanticInterpretation,
        planned_calls: Sequence[PlannedToolCall],
        executions: Sequence[ToolExecution],
        destination_evidence: dict[str, Any] | None = None,
    ) -> list[Any]:
        semantic_content = SEMANTIC_CONTEXT_TEMPLATE.format(
            semantic_json=interpretation.model_dump_json(exclude_none=True),
        )
        if destination_evidence is None:
            tool_content = ChatOrchestrator._tool_context_content(
                planned_calls,
                executions,
            )
        else:
            tool_content = DESTINATION_DISCOVERY_CONTEXT_TEMPLATE.format(
                evidence_json=json.dumps(
                    destination_evidence,
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
            )
        messages: list[Any] = [SystemMessage(content=SYSTEM_PROMPT)]
        response_policy = (
            response_policy_for(interpretation.primary_intent)
            if planned_calls or destination_evidence is not None
            else None
        )
        if response_policy is not None:
            messages.append(SystemMessage(content=response_policy))
        messages.extend(
            [
                SystemMessage(content=semantic_content),
                SystemMessage(content=tool_content),
            ]
        )
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
        payload = [
            {
                "request": {
                    "name": call.name,
                    "arguments": call.arguments,
                },
                "result": json.loads(execution.content),
            }
            for call, execution in zip(calls, executions, strict=True)
        ]
        return TOOL_CONTEXT_TEMPLATE.format(
            tool_json=json.dumps(
                payload,
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )

    @staticmethod
    def _invoke_ai_message(model: Any, messages: list[Any]) -> AIMessage:
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
    candidate_generator: DestinationCandidateGenerator | None = None,
    max_tool_calls: int | None = None,
) -> ChatOrchestratorResult:
    """Run one stateless request and close owned HTTP resources."""
    active_model = chat_model or get_chat_model()
    if registry is not None:
        return ChatOrchestrator(
            active_model,
            registry,
            semantic_interpreter=semantic_interpreter,
            candidate_generator=candidate_generator,
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
            candidate_generator=candidate_generator,
            max_tool_calls=max_tool_calls,
        ).answer(
            question,
            history=history,
            current_location=current_location,
        )


__all__ = [
    "ChatOrchestrator",
    "ChatOrchestratorResult",
    "DESTINATION_DISCOVERY_CONTEXT_TEMPLATE",
    "NO_TOOL_CONTEXT",
    "SEMANTIC_CONTEXT_TEMPLATE",
    "SYSTEM_PROMPT",
    "TOOL_CONTEXT_TEMPLATE",
    "ToolInfrastructureError",
    "orchestrate_chat",
]
