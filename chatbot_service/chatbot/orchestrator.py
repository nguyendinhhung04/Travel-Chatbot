"""Intent-aware orchestration for the travel question-answering chatbot."""

from __future__ import annotations

import base64
import binascii
import json
import logging
import re
import unicodedata
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Callable

from django.conf import settings
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from chatbot.destination_discovery import (
    DestinationCandidateGenerator,
    DestinationDiscoveryPipeline,
)
from chatbot.intent import TravelIntent
from chatbot.itinerary_making import (
    ItineraryCandidateGenerator,
    ItineraryMakingData,
    ItineraryMakingPipeline,
)
from chatbot.itinerary_management import ItineraryManagementPipeline
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
from chatbot.tools.models import (
    ChatPlace,
    ChatSource,
    ItineraryData,
    MapboxPlacesDetailsData,
    MapboxPlacesDetailsInput,
    ToolResult,
)
from chatbot.tools.registry import ToolExecution, ToolRegistry


def _normalized_search_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value.casefold().replace("đ", "d"))
    without_marks = "".join(
        character for character in decomposed
        if unicodedata.category(character) != "Mn"
    )
    return re.sub(r"[^a-z0-9]+", " ", without_marks).strip()


def _is_places_details_poi_id(mapbox_id: str) -> bool:
    """Return whether a Mapbox ID identifies a Places Details POI record."""
    encoded = mapbox_id.strip()
    padding = "=" * ((4 - len(encoded) % 4) % 4)
    try:
        decoded = base64.b64decode(
            encoded + padding,
            altchars=b"-_",
            validate=True,
        ).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return False
    return decoded.startswith("urn:mbxpoi:")


def _destination_name_matches(name: Any, destination: str) -> bool:
    if not isinstance(name, str):
        return False
    return _normalized_search_text(name) == _normalized_search_text(destination)


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



CURRENT_LOCATION_TOOL_NAME = "get_current_location"
logger = logging.getLogger(__name__)

PlaceDetailsLoader = Callable[
    [MapboxPlacesDetailsInput],
    ToolResult[MapboxPlacesDetailsData],
]


class ToolInfrastructureError(RuntimeError):
    """Raised when every planned tool failed for infrastructure reasons."""


@dataclass(frozen=True)
class ChatOrchestratorResult:
    answer: str
    sources: list[ChatSource]
    interpretation: SemanticInterpretation | None = None
    places: list[ChatPlace] = field(default_factory=list)
    client_tool_call: str | None = None
    itinerary: ItineraryMakingData | ItineraryData | None = None
    itinerary_operation: dict[str, Any] | None = None


class ChatOrchestrator:
    """Interpret one question, execute a deterministic tool plan, then answer."""

    def __init__(
        self,
        chat_model: Any,
        registry: ToolRegistry,
        *,
        semantic_interpreter: SemanticInterpreter | None = None,
        candidate_generator: DestinationCandidateGenerator | None = None,
        itinerary_candidate_generator: ItineraryCandidateGenerator | None = None,
        place_details_loader: PlaceDetailsLoader | None = None,
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
        self._itinerary_candidate_generator = itinerary_candidate_generator
        self._place_details_loader = place_details_loader
        self._max_tool_calls = resolved_max_calls

    def answer(
        self,
        question: str,
        *,
        history: Sequence[ConversationMessage] = (),
        current_location: SemanticLocation | None = None,
        active_itinerary_id: str | None = None,
        active_itinerary_version: int | None = None,
    ) -> ChatOrchestratorResult:
        cleaned_question = question.strip()
        if not cleaned_question:
            raise ValueError("question must not be empty")

        interpretation_arguments: dict[str, Any] = {
            "history": history,
            "current_location": current_location,
        }
        if active_itinerary_id is not None:
            interpretation_arguments["active_itinerary_id"] = active_itinerary_id
        interpretation = self._semantic_interpreter.interpret(
            cleaned_question,
            **interpretation_arguments,
        )
        if (
            current_location is None
            and (
                interpretation.location.use_current_location
                or "current_location" in interpretation.missing_information
            )
        ):
            return ChatOrchestratorResult(
                answer="",
                sources=[],
                interpretation=interpretation,
                client_tool_call=CURRENT_LOCATION_TOOL_NAME,
            )
        destination_evidence: dict[str, Any] | None = None
        itinerary_evidence: dict[str, Any] | None = None
        itinerary: ItineraryMakingData | ItineraryData | None = None
        itinerary_operation: dict[str, Any] | None = None
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
        elif (
            interpretation.primary_intent == TravelIntent.ITINERARY_MAKING
            and tool_plan
        ):
            itinerary_run = ItineraryMakingPipeline(
                self._chat_model,
                self._registry,
                itinerary_creator=lambda call: self._registry.execute(
                    call.name,
                    call.arguments,
                ),
                candidate_generator=self._itinerary_candidate_generator,
                max_tool_calls=self._max_tool_calls,
            ).execute(
                cleaned_question,
                history=history,
                interpretation=interpretation,
                planned_calls=tool_plan,
            )
            planned_calls = itinerary_run.calls
            executions = itinerary_run.executions
            itinerary_evidence = itinerary_run.evidence
            itinerary = itinerary_run.itinerary
        elif interpretation.primary_intent == TravelIntent.ITINERARY_MANAGEMENT:
            management_run = ItineraryManagementPipeline(self._registry).execute(
                interpretation=interpretation,
                active_itinerary_id=active_itinerary_id,
                active_itinerary_version=active_itinerary_version,
            )
            planned_calls = management_run.calls
            executions = management_run.executions
            itinerary_evidence = management_run.evidence
            itinerary = management_run.itinerary
            itinerary_operation = {
                "type": management_run.operation,
                "success": management_run.itinerary is not None,
                **(
                    {}
                    if management_run.itinerary is not None
                    else {
                        "errorCode": management_run.evidence.get("errorCode")
                    }
                ),
            }
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
            itinerary_evidence=itinerary_evidence,
        )
        response = self._invoke_ai_message(
            self._chat_model,
            messages,
            sensitive_location=current_location,
        )
        self._print_model_response(response)
        answer = self._normalized_response_text(response)
        places = self._collect_answer_places(
            answer,
            executions,
            destination_evidence,
        )
        return ChatOrchestratorResult(
            answer=answer,
            sources=sources,
            interpretation=interpretation,
            places=self._enrich_answer_places(places),
            itinerary=itinerary,
            itinerary_operation=itinerary_operation,
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
                coordinates = self._first_result_coordinates(
                    execution,
                    destination=call.destination,
                )
                if coordinates is not None:
                    destination_coordinates[call.destination] = coordinates
        return executions

    @staticmethod
    def _first_result_coordinates(
        execution: ToolExecution,
        *,
        destination: str | None = None,
    ) -> tuple[float, float] | None:
        if not execution.success:
            return None
        try:
            payload = json.loads(execution.content)
            results = payload["data"]["results"]
            if not isinstance(results, list):
                return None
            for result in results:
                if not isinstance(result, dict):
                    continue
                result_name = result.get("name")
                if (
                    destination is not None
                    and isinstance(result_name, str)
                    and not _destination_name_matches(result_name, destination)
                ):
                    continue
                longitude = float(result["longitude"])
                latitude = float(result["latitude"])
                return longitude, latitude
        except (KeyError, TypeError, ValueError):
            return None
        return None

    @staticmethod
    def _build_answer_messages(
        question: str,
        *,
        history: Sequence[ConversationMessage],
        interpretation: SemanticInterpretation,
        planned_calls: Sequence[PlannedToolCall],
        executions: Sequence[ToolExecution],
        destination_evidence: dict[str, Any] | None = None,
        itinerary_evidence: dict[str, Any] | None = None,
    ) -> list[Any]:
        if itinerary_evidence is not None:
            evidence_content = json.dumps(
                itinerary_evidence,
                ensure_ascii=False,
                indent=2,
            )
        elif destination_evidence is None:
            evidence_content = ChatOrchestrator._ordinary_evidence_content(
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
            if (
                planned_calls
                or destination_evidence is not None
                or itinerary_evidence is not None
            )
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
    def _ordinary_evidence_content(
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
                chunks = data.get("chunks")
                if not isinstance(chunks, list):
                    continue
                for chunk in chunks:
                    if not isinstance(chunk, dict):
                        continue
                    title = chunk.get("title")
                    content = chunk.get("content")
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
                compact_place = ChatOrchestrator._compact_mapbox_place(
                    place,
                    destination_location=(
                        call.evidence_kind == "destination_location"
                    ),
                )
                if compact_place is not None:
                    target.append(compact_place)

        if errors:
            payload["errors"] = errors
        return json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        )

    @staticmethod
    def _compact_mapbox_place(
        place: Any,
        *,
        destination_location: bool,
    ) -> dict[str, Any] | None:
        if not isinstance(place, dict):
            return None
        required_fields = ("mapboxId", "name", "longitude", "latitude")
        if any(place.get(field) is None for field in required_fields):
            return None

        compact = {field: place[field] for field in required_fields}
        if destination_location:
            return compact

        optional_fields = (
            "fullAddress",
            "poiCategories",
            "operationalStatus",
            "distanceMeters",
            "etaMinutes",
            "rating",
        )
        for field in optional_fields:
            value = place.get(field)
            if value is not None and value != []:
                compact[field] = value
        return compact

    @staticmethod
    def _invoke_ai_message(
        model: Any,
        messages: list[Any],
        *,
        sensitive_location: SemanticLocation | None = None,
    ) -> AIMessage:
        ChatOrchestrator._print_model_request(
            messages,
            sensitive_location=sensitive_location,
        )
        response = model.invoke(messages)
        if not isinstance(response, AIMessage):
            raise RuntimeError("Gemini returned an unsupported response type")
        return response

    @staticmethod
    def _print_model_request(
        messages: Sequence[Any],
        *,
        sensitive_location: SemanticLocation | None = None,
    ) -> None:
        """Print message roles and content without LangChain metadata escaping."""
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
    def _normalize_place_text(value: str) -> str:
        return " ".join(
            unicodedata.normalize("NFKC", value).casefold().split()
        )

    @classmethod
    def _collect_answer_places(
        cls,
        answer: str,
        executions: Sequence[ToolExecution],
        destination_evidence: dict[str, Any] | None,
    ) -> list[ChatPlace]:
        """Return only verified places whose names occur in the final answer."""
        candidates: dict[str, dict[str, Any]] = {}

        def add_candidate(value: Any) -> None:
            if not isinstance(value, dict):
                return
            mapbox_id = value.get("mapboxId")
            name = value.get("name")
            if not isinstance(mapbox_id, str) or not mapbox_id.strip():
                return
            if not isinstance(name, str) or not name.strip():
                return
            try:
                longitude = float(value["longitude"])
                latitude = float(value["latitude"])
            except (KeyError, TypeError, ValueError):
                return
            if not (-180 <= longitude <= 180 and -90 <= latitude <= 90):
                return

            item = candidates.setdefault(
                mapbox_id.strip(),
                {
                    "mapboxId": mapbox_id.strip(),
                    "names": [],
                    "longitude": longitude,
                    "latitude": latitude,
                    "fullAddress": value.get("fullAddress"),
                    "categories": value.get("poiCategories") or [],
                    "operationalStatus": value.get("operationalStatus"),
                    "rating": value.get("rating"),
                },
            )
            clean_name = name.strip()
            if clean_name not in item["names"]:
                item["names"].append(clean_name)

        if destination_evidence is not None:
            for candidate in destination_evidence.get("matchedCandidates", []):
                add_candidate(candidate)
            for item in destination_evidence.get("additionalMapboxPlaces", []):
                if isinstance(item, dict):
                    add_candidate(item.get("place"))

        for execution in executions:
            if not execution.success:
                continue
            try:
                payload = json.loads(execution.content)
            except (TypeError, ValueError):
                continue
            data = payload.get("data") if isinstance(payload, dict) else None
            if not isinstance(data, dict):
                continue
            for result in data.get("results", []):
                if not isinstance(result, dict):
                    continue
                add_candidate(result.get("place", result))
            for place in data.get("additionalPlaces", []):
                add_candidate(place)

        normalized_answer = cls._normalize_place_text(answer)
        name_to_ids: dict[str, set[str]] = {}
        for mapbox_id, candidate in candidates.items():
            for name in candidate["names"]:
                name_to_ids.setdefault(cls._normalize_place_text(name), set()).add(
                    mapbox_id
                )

        places: list[ChatPlace] = []
        for mapbox_id, candidate in candidates.items():
            matching_names = [
                name
                for name in candidate["names"]
                if name_to_ids.get(cls._normalize_place_text(name)) == {mapbox_id}
                and cls._normalize_place_text(name) in normalized_answer
            ]
            if not matching_names:
                continue
            display_name = max(matching_names, key=len)
            places.append(
                ChatPlace(
                    mapboxId=mapbox_id,
                    name=display_name,
                    longitude=candidate["longitude"],
                    latitude=candidate["latitude"],
                    fullAddress=candidate["fullAddress"],
                    categories=candidate["categories"],
                    operationalStatus=candidate["operationalStatus"],
                    rating=candidate["rating"],
                )
            )
        return places

    def _enrich_answer_places(self, places: list[ChatPlace]) -> list[ChatPlace]:
        if not places or self._place_details_loader is None:
            return places

        eligible_places = [
            place
            for place in places
            if _is_places_details_poi_id(place.mapbox_id)
        ]
        skipped_count = len(places) - len(eligible_places)
        if skipped_count:
            logger.info(
                "Skipped Mapbox Places enrichment for %d non-POI place(s)",
                skipped_count,
            )
        if not eligible_places:
            return places

        try:
            result = self._place_details_loader(
                MapboxPlacesDetailsInput(
                    ids=[place.mapbox_id for place in eligible_places]
                )
            )
        except Exception as error:
            logger.warning(
                "Mapbox Places enrichment failed (%s)",
                type(error).__name__,
            )
            return places
        if not result.success or result.data is None:
            return places

        details_by_id = {
            detail.mapbox_id: detail for detail in result.data.results
        }
        enriched: list[ChatPlace] = []
        for place in places:
            detail = details_by_id.get(place.mapbox_id)
            if detail is None:
                enriched.append(place)
                continue
            enriched.append(
                place.model_copy(
                    update={
                        "full_address": detail.full_address or place.full_address,
                        "brand": detail.brand,
                        "primary_category": detail.primary_category,
                        "categories": detail.categories or place.categories,
                        "opening_hours": detail.opening_hours,
                        "permanently_closed": detail.permanently_closed,
                        "phone": detail.phone,
                        "website": detail.website,
                        "operational_status": detail.status or place.operational_status,
                        "popularity": detail.popularity,
                        "photos": detail.photos,
                    }
                )
            )
        return enriched

    @staticmethod
    def _collect_unique_sources(
        executions: Sequence[ToolExecution],
    ) -> list[ChatSource]:
        sources: list[ChatSource] = []
        source_keys: set[tuple[str, str, str]] = set()
        for execution in executions:
            for source in execution.sources:
                # Attribution can vary between Mapbox tool responses while the
                # provider/source identity remains the same. Deduplicate on the
                # fields exposed in the public source contract so the API does
                # not send duplicate provider entries to the frontend.
                source_key = (
                    source.type,
                    source.title,
                    source.source,
                )
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
    active_itinerary_id: str | None = None,
    active_itinerary_version: int | None = None,
    chat_model: Any | None = None,
    registry: ToolRegistry | None = None,
    semantic_interpreter: SemanticInterpreter | None = None,
    candidate_generator: DestinationCandidateGenerator | None = None,
    itinerary_candidate_generator: ItineraryCandidateGenerator | None = None,
    max_tool_calls: int | None = None,
) -> ChatOrchestratorResult:
    """Run one stateless request and close owned HTTP resources."""
    active_model = chat_model or get_chat_model(thinking_level="medium")
    active_interpreter = semantic_interpreter
    active_candidate_generator = candidate_generator
    active_itinerary_candidate_generator = itinerary_candidate_generator

    if chat_model is None and (
        active_interpreter is None
        or active_candidate_generator is None
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
            itinerary_candidate_generator=active_itinerary_candidate_generator,
            max_tool_calls=max_tool_calls,
        ).answer(
            question,
            history=history,
            current_location=current_location,
            active_itinerary_id=active_itinerary_id,
            active_itinerary_version=active_itinerary_version,
        )

    with MapboxToolClient() as mapbox_client:
        active_registry = ToolRegistry(mapbox_client)
        return ChatOrchestrator(
            active_model,
            active_registry,
            semantic_interpreter=active_interpreter,
            candidate_generator=active_candidate_generator,
            itinerary_candidate_generator=active_itinerary_candidate_generator,
            place_details_loader=mapbox_client.retrieve_place_details,
            max_tool_calls=max_tool_calls,
        ).answer(
            question,
            history=history,
            current_location=current_location,
            active_itinerary_id=active_itinerary_id,
            active_itinerary_version=active_itinerary_version,
        )


__all__ = [
    "ChatOrchestrator",
    "ChatOrchestratorResult",
    "CURRENT_LOCATION_TOOL_NAME",
    "NO_TOOL_CONTEXT",
    "SYSTEM_PROMPT",
    "ToolInfrastructureError",
    "orchestrate_chat",
]
