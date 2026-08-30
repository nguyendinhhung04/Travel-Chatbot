"""Compose the final Gemini answer from handler-owned evidence."""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from chatbot.semantic import ConversationMessage, SemanticInterpretation, SemanticLocation
from chatbot.tool_planner import PlannedToolCall
from chatbot.tools.registry import ToolExecution
from chatbot.rag.rag_chain import normalize_answer

from .intent_routing.contracts import IntentExecutionResult


SYSTEM_PROMPT = """Bạn là trợ lý tư vấn du lịch tiếng Việt.

Dùng đúng phân tích, chính sách nguồn, dữ liệu backend và lịch sử được cung cấp.
- Không nhắc tool, RAG, schema hay JSON trong câu trả lời.
- Không tự tạo dữ liệu có thể thay đổi như địa chỉ, tọa độ, rating, giờ mở cửa,
  điện thoại, website hoặc giá. Bỏ qua trường không có giá trị; không loại một địa
  điểm chỉ vì thiếu rating.
- Với needs_clarification, chỉ hỏi thông tin còn thiếu. Với unsupported, nói rõ
  giới hạn; không giả vờ đã chỉ đường, đọc giao thông thời gian thực hoặc lưu dữ liệu.
- Không tự tạo trạng thái lưu; với itinerary_advice không tuyên bố đã lưu.
  Với itinerary_making,
  chỉ nói lịch trình đã được tạo và lưu khi backend trả success=true cùng itinerary hợp lệ;
  nếu thất bại, không tự tạo route hoặc tuyên bố đã lưu.
  Với itinerary_advice,
  lịch trình chỉ là tư vấn văn bản.
  Với itinerary_making,
  chỉ nói tuyến đã được tối ưu khi backend trả success=true và itinerary hợp lệ;
  nếu thất bại, không tự tạo thứ tự, khoảng cách hoặc hình học tuyến đường.
  Với itinerary_management, chỉ nói đã thay đổi/lưu khi backend trả success=true
  và itinerary có phiên bản mới; nếu thất bại phải giải thích theo errorCode.
- Trả lời tự nhiên, có nhận định và đủ giúp người dùng quyết định. Dùng plain text,
  không dùng bảng hoặc Markdown phức tạp.
- Khi nhắc địa điểm có trong dữ liệu Mapbox, phải giữ nguyên trường `name` của
  địa điểm đó; không đổi tên, dịch tên hoặc tự rút gọn tên.
- Chọn bố cục phù hợp câu hỏi. Khi có nhiều nơi, tách từng nơi/nhóm bằng dòng trống;
  tránh khuôn lặp, nhãn thừa, câu sáo rỗng và lặp lại dữ liệu.
"""

NO_TOOL_CONTEXT = "Không có dữ liệu tool cho yêu cầu này."


class AnswerComposer:
    def __init__(self, model: Any) -> None:
        self._model = model

    def compose(
        self,
        question: str,
        *,
        history: Sequence[ConversationMessage],
        interpretation: SemanticInterpretation,
        execution_result: IntentExecutionResult,
        sensitive_location: SemanticLocation | None = None,
    ) -> str:
        messages = self.build_messages(
            question,
            history=history,
            interpretation=interpretation,
            execution_result=execution_result,
        )
        response = self.invoke_ai_message(
            self._model,
            messages,
            sensitive_location=sensitive_location,
        )
        self.print_model_response(response)
        return self.normalized_response_text(response)

    @staticmethod
    def build_messages(
        question: str,
        *,
        history: Sequence[ConversationMessage],
        interpretation: SemanticInterpretation,
        execution_result: IntentExecutionResult,
    ) -> list[Any]:
        if execution_result.itinerary_evidence is not None:
            evidence_content = json.dumps(
                execution_result.itinerary_evidence,
                ensure_ascii=False,
                indent=2,
            )
        elif execution_result.destination_evidence is None:
            evidence_content = AnswerComposer.ordinary_evidence_content(
                execution_result.planned_calls,
                execution_result.executions,
            )
        else:
            evidence_content = json.dumps(
                execution_result.destination_evidence,
                ensure_ascii=False,
                indent=2,
            )

        sections = [f"=== HƯỚNG DẪN ===\n{SYSTEM_PROMPT.strip()}"]
        if execution_result.response_policy is not None:
            sections.append(
                "=== CHÍNH SÁCH NGUỒN ===\n"
                + execution_result.response_policy.strip()
            )
        sections.extend(
            (
                f"=== CÂU HỎI ===\n{interpretation.normalized_query}",
                f"=== DỮ LIỆU BACKEND ===\n{evidence_content}",
            )
        )
        messages: list[Any] = [SystemMessage(content="\n\n".join(sections))]
        for message in history:
            messages.append(
                HumanMessage(content=message.content)
                if message.role == "user"
                else AIMessage(content=message.content)
            )
        messages.append(HumanMessage(content=question))
        return messages

    @staticmethod
    def ordinary_evidence_content(
        calls: Sequence[PlannedToolCall],
        executions: Sequence[ToolExecution],
    ) -> str:
        if not calls:
            return NO_TOOL_CONTEXT
        payload: dict[str, Any] = {"knowledgeBase": []}
        mapbox_calls = [
            (call, execution)
            for call, execution in zip(calls, executions, strict=True)
            if call.name.startswith("mapbox_")
        ]
        if mapbox_calls:
            payload["mapbox"] = {
                "success": all(execution.success for _, execution in mapbox_calls),
                "destinationLocations": [],
                "places": [],
            }

        errors: list[dict[str, str]] = []
        for call, execution in zip(calls, executions, strict=True):
            try:
                result = json.loads(execution.content)
            except (TypeError, json.JSONDecodeError):
                result = {}
            if not isinstance(result, dict):
                result = {}
            if not execution.success:
                error_code = execution.error_code or result.get("errorCode")
                error: dict[str, str] = {"tool": call.name}
                if isinstance(error_code, str) and error_code:
                    error["errorCode"] = error_code
                errors.append(error)
                continue
            data = result.get("data")
            if not isinstance(data, dict):
                continue
            if call.name == "search_travel_knowledge":
                for chunk in data.get("chunks", []):
                    if not isinstance(chunk, dict):
                        continue
                    title, content = chunk.get("title"), chunk.get("content")
                    if isinstance(title, str) and isinstance(content, str):
                        payload["knowledgeBase"].append(
                            {"title": title, "content": content}
                        )
                continue
            if not call.name.startswith("mapbox_"):
                continue
            results = data.get("results")
            if not isinstance(results, list):
                continue
            target = (
                payload["mapbox"]["destinationLocations"]
                if call.evidence_kind == "destination_location"
                else payload["mapbox"]["places"]
            )
            for place in results:
                compact = AnswerComposer.compact_mapbox_place(
                    place,
                    destination_location=call.evidence_kind == "destination_location",
                )
                if compact is not None:
                    target.append(compact)
        if errors:
            payload["errors"] = errors
        return json.dumps(payload, ensure_ascii=False, indent=2)

    @staticmethod
    def compact_mapbox_place(
        place: Any,
        *,
        destination_location: bool,
    ) -> dict[str, Any] | None:
        if not isinstance(place, dict):
            return None
        required = ("mapboxId", "name", "longitude", "latitude")
        if any(place.get(field) is None for field in required):
            return None
        compact = {field: place[field] for field in required}
        if destination_location:
            return compact
        for field in (
            "fullAddress", "poiCategories", "operationalStatus",
            "distanceMeters", "etaMinutes", "rating",
        ):
            value = place.get(field)
            if value is not None and value != []:
                compact[field] = value
        return compact

    @staticmethod
    def invoke_ai_message(
        model: Any,
        messages: list[Any],
        *,
        sensitive_location: SemanticLocation | None = None,
    ) -> AIMessage:
        AnswerComposer.print_model_request(
            messages,
            sensitive_location=sensitive_location,
        )
        response = model.invoke(messages)
        if not isinstance(response, AIMessage):
            raise RuntimeError("Gemini returned an unsupported response type")
        return response

    @staticmethod
    def print_model_request(
        messages: Sequence[Any],
        *,
        sensitive_location: SemanticLocation | None = None,
    ) -> None:
        sections: list[str] = []
        for index, message in enumerate(messages, start=1):
            content = message.content
            if not isinstance(content, str):
                content = json.dumps(content, ensure_ascii=False, indent=2)
            if sensitive_location is not None:
                for coordinate in (
                    sensitive_location.longitude,
                    sensitive_location.latitude,
                ):
                    if coordinate is not None:
                        content = content.replace(str(coordinate), "[location-redacted]")
            sections.append(f"--- MESSAGE {index}: {message.type.upper()} ---\n{content}")
        AnswerComposer.print_terminal(
            "Gemini request messages:\n" + "\n\n".join(sections) + "\n"
        )

    @staticmethod
    def print_model_response(response: AIMessage) -> None:
        content = response.content
        if not isinstance(content, str):
            content = json.dumps(content, ensure_ascii=False, indent=2)
        AnswerComposer.print_terminal(f"Gemini response:\n--- MESSAGE: AI ---\n{content}\n")

    @staticmethod
    def print_terminal(output: str) -> None:
        try:
            print(output, end="", flush=True)
        except UnicodeEncodeError:
            stdout_buffer = getattr(sys.stdout, "buffer", None)
            if stdout_buffer is None:
                raise
            stdout_buffer.write(output.encode("utf-8"))
            stdout_buffer.flush()

    @staticmethod
    def normalized_response_text(response: AIMessage) -> str:
        answer = response.text.strip()
        if not answer:
            raise RuntimeError("Gemini returned an empty answer")
        normalized = normalize_answer(answer)
        if not normalized:
            raise RuntimeError("Gemini returned an empty answer")
        return normalized


__all__ = ["AnswerComposer", "NO_TOOL_CONTEXT", "SYSTEM_PROMPT"]
