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


SYSTEM_PROMPT = """Bạn là trợ lý tư vấn du lịch tiếng Việt.

Dùng đúng phân tích, chính sách nguồn, dữ liệu backend và lịch sử được cung cấp.
- Không nhắc tool, RAG, schema hay JSON trong câu trả lời.
- Không tự tạo dữ liệu có thể thay đổi như địa chỉ, tọa độ, rating, giờ mở cửa,
  điện thoại, website hoặc giá. Bỏ qua trường không có giá trị; không loại một địa
  điểm chỉ vì thiếu rating.
- Với needs_clarification, chỉ hỏi thông tin còn thiếu. Với unsupported, nói rõ
  giới hạn; không giả vờ đã chỉ đường, đọc giao thông thời gian thực hoặc lưu dữ liệu.
- Lịch trình chỉ là tư vấn văn bản, không tuyên bố đã lưu hay tối ưu tuyến đường.
- Trả lời tự nhiên, có nhận định và đủ giúp người dùng quyết định. Dùng plain text,
  không dùng bảng hoặc Markdown phức tạp.
- Chọn bố cục phù hợp câu hỏi. Khi có nhiều nơi, tách từng nơi/nhóm bằng dòng trống;
  tránh khuôn lặp, nhãn thừa, câu sáo rỗng và lặp lại dữ liệu.
"""

NO_TOOL_CONTEXT = "Không có dữ liệu tool cho yêu cầu này."



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
        if destination_evidence is None:
            evidence_content = ChatOrchestrator._tool_context_content(
                planned_calls,
                executions,
            )
        else:
            evidence_content = json.dumps(
                destination_evidence,
                ensure_ascii=False,
                indent=2,
            )
        response_policy = (
            response_policy_for(interpretation.primary_intent)
            if planned_calls or destination_evidence is not None
            else None
        )
        prompt_sections = [f"=== HƯỚNG DẪN ===\n{SYSTEM_PROMPT.strip()}"]
        if response_policy is not None:
            prompt_sections.append(
                f"=== CHÍNH SÁCH NGUỒN ===\n{response_policy.strip()}"
            )
        prompt_sections.extend(
            (
                f"=== CÂU HỎI ===\n{interpretation.normalized_query}",
                f"=== DỮ LIỆU BACKEND ===\n{evidence_content}",
            )
        )
        messages: list[Any] = [
            SystemMessage(content="\n\n".join(prompt_sections))
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
        payload = [
            {
                "tool": call.name,
                "result": json.loads(execution.content),
            }
            for call, execution in zip(calls, executions, strict=True)
        ]
        return json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        )

    @staticmethod
    def _invoke_ai_message(model: Any, messages: list[Any]) -> AIMessage:
        ChatOrchestrator._print_model_request(messages)
        response = model.invoke(messages)
        if not isinstance(response, AIMessage):
            raise RuntimeError("Gemini returned an unsupported response type")
        return response

    @staticmethod
    def _print_model_request(messages: Sequence[Any]) -> None:
        """Print message roles and content without LangChain metadata escaping."""
        sections: list[str] = []
        for index, message in enumerate(messages, start=1):
            content = message.content
            if not isinstance(content, str):
                content = json.dumps(content, ensure_ascii=False, indent=2)
            sections.append(
                f"--- MESSAGE {index}: {message.type.upper()} ---\n{content}"
            )
        output = "Gemini request messages:\n" + "\n\n".join(sections) + "\n"
        ChatOrchestrator._print_terminal(output)

    @staticmethod
    def _print_model_response(response: AIMessage) -> None:
        """Print Gemini's answer without empty LangChain metadata."""
        content = response.content
        if not isinstance(content, str):
            content = json.dumps(content, ensure_ascii=False, indent=2)
        output = f"Gemini response:\n--- MESSAGE: AI ---\n{content}\n"
        ChatOrchestrator._print_terminal(output)

    @staticmethod
    def _print_terminal(output: str) -> None:
        """Prefer the terminal text encoding and fall back to UTF-8 bytes."""
        try:
            print(output, end="", flush=True)
        except UnicodeEncodeError:
            stdout_buffer = getattr(sys.stdout, "buffer", None)
            if stdout_buffer is None:
                raise
            stdout_buffer.write(output.encode("utf-8"))
            stdout_buffer.flush()

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
    active_model = chat_model or get_chat_model(thinking_level="medium")
    active_interpreter = semantic_interpreter
    active_candidate_generator = candidate_generator

    if chat_model is None and (
        active_interpreter is None or active_candidate_generator is None
    ):
        planning_model = get_chat_model(thinking_level="low")
        active_interpreter = active_interpreter or SemanticInterpreter(planning_model)
        active_candidate_generator = (
            active_candidate_generator
            or DestinationCandidateGenerator(planning_model)
        )

    if registry is not None:
        return ChatOrchestrator(
            active_model,
            registry,
            semantic_interpreter=active_interpreter,
            candidate_generator=active_candidate_generator,
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
            semantic_interpreter=active_interpreter,
            candidate_generator=active_candidate_generator,
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
    "SYSTEM_PROMPT",
    "ToolInfrastructureError",
    "orchestrate_chat",
]
