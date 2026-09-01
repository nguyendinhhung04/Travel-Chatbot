"""Structured candidate generation and deterministic Mapbox place matching."""

from __future__ import annotations

import json
import re
import unicodedata
import logging
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from chatbot.semantic import ConversationMessage, SemanticInterpretation
from chatbot.tool_planner import PlannedToolCall
from chatbot.tools.models import (
    MapboxCandidateMatch,
    MapboxCandidateResolutionData,
    ToolResult,
)
from chatbot.tools.registry import (
    MAPBOX_RESOLVE_CANDIDATES_TOOL_NAME,
    ToolExecution,
    ToolRegistry,
)


def _destination_name_matches(name: Any, destination: str) -> bool:
    if not isinstance(name, str):
        return False
    def normalize(value: str) -> str:
        decomposed = unicodedata.normalize("NFD", value.casefold().replace("đ", "d"))
        without_marks = "".join(
            character for character in decomposed
            if unicodedata.category(character) != "Mn"
        )
        return re.sub(r"[^a-z0-9]+", " ", without_marks).strip()
    return normalize(name) == normalize(destination)

MAX_DESTINATION_CANDIDATES = 5
logger = logging.getLogger(__name__)
_CANDIDATE_RESULT_ADAPTER = TypeAdapter(
    ToolResult[MapboxCandidateResolutionData]
)

CANDIDATE_SYSTEM_PROMPT = """Tạo tối đa 5 ứng viên nổi bật cho điểm đến được cung cấp.
Ưu tiên Knowledge Base, sau đó mới dùng kiến thức ổn định. Chỉ trả name, aliases,
categoryHints và reason ngắn gọn. Không tạo dữ liệu Mapbox hoặc thông tin có thể
thay đổi như địa chỉ, tọa độ, rating, giờ mở cửa, điện thoại và website.
"""


class DiscoveryModel(BaseModel):
    """Strict model for destination-discovery internal data."""

    model_config = ConfigDict(
        extra="forbid",
        allow_inf_nan=False,
        populate_by_name=True,
        str_strip_whitespace=True,
    )


class DestinationCandidate(DiscoveryModel):
    name: str = Field(min_length=1, max_length=200)
    aliases: list[str] = Field(default_factory=list, max_length=5)
    category_hints: list[str] = Field(
        default_factory=list,
        alias="categoryHints",
        max_length=5,
    )
    reason: str = Field(min_length=1, max_length=500)


class DestinationCandidateSet(DiscoveryModel):
    destination: str = Field(min_length=1, max_length=200)
    candidates: list[DestinationCandidate] = Field(
        default_factory=list,
        max_length=MAX_DESTINATION_CANDIDATES,
    )


class DestinationCandidateGenerator:
    """Ask Gemini for a bounded, structured list of famous places."""

    def __init__(self, chat_model: Any) -> None:
        self._structured_model = chat_model.with_structured_output(
            DestinationCandidateSet,
            method="json_schema",
        )

    def generate(
        self,
        question: str,
        *,
        interpretation: SemanticInterpretation,
        history: Sequence[ConversationMessage],
        knowledge_chunks: Sequence[dict[str, str]],
    ) -> DestinationCandidateSet:
        payload = {
            "question": question,
            "history": [message.model_dump(mode="json") for message in history],
            "semanticInterpretation": interpretation.model_dump(
                mode="json",
                exclude_none=True,
            ),
            "knowledgeBase": list(knowledge_chunks),
        }
        messages = [
            SystemMessage(content=CANDIDATE_SYSTEM_PROMPT),
            HumanMessage(
                content=json.dumps(
                    payload,
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
            ),
        ]
        result = self._structured_model.invoke(messages)
        if isinstance(result, DestinationCandidateSet):
            return result
        return DestinationCandidateSet.model_validate(result)


@dataclass(frozen=True)
class DestinationDiscoveryPipelineResult:
    calls: list[PlannedToolCall]
    executions: list[ToolExecution]
    evidence: dict[str, Any]


class DestinationDiscoveryPipeline:
    """Run the candidate, verification, enrichment, and evidence phases."""

    def __init__(
        self,
        chat_model: Any,
        registry: ToolRegistry,
        *,
        max_tool_calls: int,
        candidate_generator: DestinationCandidateGenerator | None = None,
    ) -> None:
        self._chat_model = chat_model
        self._registry = registry
        self._max_tool_calls = max_tool_calls
        self._candidate_generator = candidate_generator

    def execute(
        self,
        question: str,
        *,
        history: Sequence[ConversationMessage],
        interpretation: SemanticInterpretation,
        planned_calls: Sequence[PlannedToolCall],
    ) -> DestinationDiscoveryPipelineResult:
        calls: list[PlannedToolCall] = []
        executions: list[ToolExecution] = []

        rag_call = next(
            (call for call in planned_calls if call.evidence_kind == "knowledge"),
            None,
        )
        rag_execution = self._execute_if_budget(rag_call, calls, executions)
        candidates = self._generate_candidates(
            question,
            history=history,
            interpretation=interpretation,
            rag_execution=rag_execution,
        )

        coordinates = self._semantic_coordinates(interpretation)
        destination_call = next(
            (
                call
                for call in planned_calls
                if call.evidence_kind == "destination_location"
            ),
            None,
        )
        if coordinates is None:
            destination_execution = self._execute_if_budget(
                destination_call,
                calls,
                executions,
            )
            if destination_execution is not None:
                coordinates = self._first_result_coordinates(
                    destination_execution,
                    destination=destination_call.destination if destination_call else None,
                )

        category_call = next(
            (call for call in planned_calls if call.evidence_kind == "poi"),
            None,
        )
        resolution_data: MapboxCandidateResolutionData | None = None
        candidate_by_id = {
            f"candidate-{index}": candidate
            for index, candidate in enumerate(candidates.candidates, start=1)
        }
        if coordinates is not None and self._has_budget(calls):
            resolution_call = self._candidate_resolution_call(
                coordinates,
                candidate_by_id,
                category_call,
            )
            self._print_verification_request(resolution_call)
            resolution_execution = self._registry.execute(
                resolution_call.name,
                resolution_call.arguments,
            )
            self._print_verification_response(resolution_execution)
            calls.append(resolution_call)
            executions.append(resolution_execution)
            resolution_data = self._parse_resolution_data(resolution_execution)

        evidence = self._build_evidence(
            rag_execution=rag_execution,
            candidate_by_id=candidate_by_id,
            resolution_data=resolution_data,
            destination_resolved=coordinates is not None,
        )
        self._print_verification_result(
            destination=candidates.destination,
            destination_resolved=coordinates is not None,
            matches=resolution_data.results if resolution_data is not None else (),
            evidence=evidence,
        )
        return DestinationDiscoveryPipelineResult(calls, executions, evidence)

    def _execute_if_budget(
        self,
        call: PlannedToolCall | None,
        calls: list[PlannedToolCall],
        executions: list[ToolExecution],
    ) -> ToolExecution | None:
        if call is None or not self._has_budget(calls):
            return None
        execution = self._registry.execute(call.name, call.arguments)
        calls.append(call)
        executions.append(execution)
        return execution

    def _generate_candidates(
        self,
        question: str,
        *,
        history: Sequence[ConversationMessage],
        interpretation: SemanticInterpretation,
        rag_execution: ToolExecution | None,
    ) -> DestinationCandidateSet:
        destination = (
            interpretation.location.near
            or next(iter(interpretation.entities.destinations), "")
        )
        try:
            generator = self._candidate_generator or DestinationCandidateGenerator(
                self._chat_model
            )
            return generator.generate(
                question,
                interpretation=interpretation,
                history=history,
                knowledge_chunks=self._knowledge_chunks(rag_execution),
            )
        except Exception as error:
            logger.warning(
                "Destination candidate generation failed (%s)",
                type(error).__name__,
            )
            return DestinationCandidateSet(
                destination=destination or "Không xác định",
                candidates=[],
            )

    def _has_budget(self, calls: Sequence[PlannedToolCall]) -> bool:
        return len(calls) < self._max_tool_calls

    @staticmethod
    def _semantic_coordinates(
        interpretation: SemanticInterpretation,
    ) -> tuple[float, float] | None:
        location = interpretation.location
        if location.longitude is None or location.latitude is None:
            return None
        return location.longitude, location.latitude

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
                return float(result["longitude"]), float(result["latitude"])
        except (KeyError, TypeError, ValueError):
            return None
        return None

    @staticmethod
    def _candidate_resolution_call(
        coordinates: tuple[float, float],
        candidate_by_id: dict[str, DestinationCandidate],
        category_call: PlannedToolCall | None,
    ) -> PlannedToolCall:
        longitude, latitude = coordinates
        arguments: dict[str, Any] = {
            "longitude": longitude,
            "latitude": latitude,
            "candidates": [
                {
                    "candidateId": candidate_id,
                    "name": candidate.name,
                    "aliases": candidate.aliases,
                    "categoryHints": candidate.category_hints,
                }
                for candidate_id, candidate in candidate_by_id.items()
            ],
        }
        if category_call is not None:
            category_id = category_call.arguments.get("category_id")
            if category_id is not None:
                arguments["categoryId"] = category_id
            minimum_rating = category_call.arguments.get("minimum_rating")
            if minimum_rating is not None:
                arguments["minimumRating"] = minimum_rating
        return PlannedToolCall(
            MAPBOX_RESOLVE_CANDIDATES_TOOL_NAME,
            arguments,
            evidence_kind="candidate_resolution",
        )

    @staticmethod
    def _parse_resolution_data(
        execution: ToolExecution,
    ) -> MapboxCandidateResolutionData | None:
        if not execution.success:
            return None
        try:
            result = _CANDIDATE_RESULT_ADAPTER.validate_json(execution.content)
        except (ValidationError, ValueError):
            return None
        return result.data

    @staticmethod
    def _print_verification_request(call: PlannedToolCall) -> None:
        """Print the sanitized batch request used to verify candidates."""
        payload = {
            "method": "POST",
            "path": "/api/chatbot/tools/mapbox-resolve-candidates",
            "body": call.arguments,
            "accessToken": "[server-side omitted]",
        }
        output = "Destination verification Mapbox request:\n" + json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        ) + "\n"
        stdout_buffer = getattr(sys.stdout, "buffer", None)
        if stdout_buffer is not None:
            stdout_buffer.write(output.encode("utf-8"))
            stdout_buffer.flush()
            return
        print(output, end="", flush=True)

    @staticmethod
    def _print_verification_response(execution: ToolExecution) -> None:
        """Print only the normalized candidate-resolution response."""
        try:
            tool_payload = json.loads(execution.content)
        except (TypeError, ValueError):
            response_payload: Any = {
                "success": False,
                "errorCode": "unparseable_tool_response",
                "errorMessage": "Không thể đọc response từ Mapbox tool.",
            }
        else:
            response_payload = tool_payload

        output = "Destination verification Mapbox response:\n" + json.dumps(
            response_payload,
            ensure_ascii=False,
            indent=2,
        ) + "\n"
        stdout_buffer = getattr(sys.stdout, "buffer", None)
        if stdout_buffer is not None:
            stdout_buffer.write(output.encode("utf-8"))
            stdout_buffer.flush()
            return
        print(output, end="", flush=True)

    @staticmethod
    def _successful_payload(
        execution: ToolExecution | None,
    ) -> dict[str, Any] | None:
        if execution is None or not execution.success:
            return None
        try:
            payload = json.loads(execution.content)
        except (TypeError, ValueError):
            return None
        return payload if isinstance(payload, dict) else None

    @staticmethod
    def _knowledge_chunks(
        execution: ToolExecution | None,
    ) -> list[dict[str, str]]:
        """Keep only useful RAG text fields for Gemini prompts."""
        payload = DestinationDiscoveryPipeline._successful_payload(execution)
        data = payload.get("data") if payload is not None else None
        chunks = data.get("chunks") if isinstance(data, dict) else None
        if not isinstance(chunks, list):
            return []

        compact_chunks: list[dict[str, str]] = []
        for chunk in chunks:
            if not isinstance(chunk, dict):
                continue
            content = chunk.get("content")
            title = chunk.get("title")
            if not isinstance(content, str) or not content.strip():
                continue
            compact_chunks.append(
                {
                    "title": title.strip()
                    if isinstance(title, str) and title.strip()
                    else "Không rõ",
                    "content": content.strip(),
                }
            )
        return compact_chunks

    @staticmethod
    def _build_evidence(
        *,
        rag_execution: ToolExecution | None,
        candidate_by_id: dict[str, DestinationCandidate],
        resolution_data: MapboxCandidateResolutionData | None,
        destination_resolved: bool,
    ) -> dict[str, Any]:
        matched_places: list[dict[str, Any]] = []
        if resolution_data is not None:
            for match in resolution_data.results:
                candidate = candidate_by_id.get(match.candidate_id)
                if match.status != "matched" or match.place is None or candidate is None:
                    continue
                matched_places.append(
                    {
                        "name": match.place.name,
                        "mapboxId": match.place.mapbox_id,
                        "fullAddress": match.place.full_address,
                        "categoryHints": candidate.category_hints,
                        "reason": candidate.reason,
                        "poiCategories": match.place.poi_categories,
                        "longitude": match.place.longitude,
                        "latitude": match.place.latitude,
                        "distanceMeters": match.place.distance_meters,
                        "etaMinutes": match.place.eta_minutes,
                        "rating": match.place.rating,
                        "popularity": match.place.popularity,
                    }
                )

        return {
            "knowledgeBase": DestinationDiscoveryPipeline._knowledge_chunks(
                rag_execution
            ),
            "destinationResolved": destination_resolved,
            "matchedCandidates": matched_places,
            "additionalMapboxPlaces": [
                {"place": place.model_dump(mode="json", by_alias=True)}
                for place in (
                    resolution_data.additional_places
                    if resolution_data is not None
                    else ()
                )
            ],
        }

    @staticmethod
    def _print_verification_result(
        *,
        destination: str,
        destination_resolved: bool,
        matches: Sequence[MapboxCandidateMatch],
        evidence: dict[str, Any],
    ) -> None:
        """Print verification outcomes without exposing prompts or raw responses."""
        payload = {
            "destination": destination,
            "destinationResolved": destination_resolved,
            "candidates": [
                {
                    "candidateId": match.candidate_id,
                    "status": match.status,
                    "similarity": match.similarity,
                    "matchedPlace": (
                        {
                            "mapboxId": match.place.mapbox_id,
                            "name": match.place.name,
                            "poiCategories": match.place.poi_categories,
                            "poiCategoryIds": match.place.poi_category_ids,
                            "distanceMeters": match.place.distance_meters,
                        }
                        if match.place is not None
                        else None
                    ),
                }
                for match in matches
            ],
            "additionalMapboxPlaces": [
                item["place"]
                for item in evidence["additionalMapboxPlaces"]
            ],
        }
        output = "Destination verification result:\n" + json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        ) + "\n"
        stdout_buffer = getattr(sys.stdout, "buffer", None)
        if stdout_buffer is not None:
            stdout_buffer.write(output.encode("utf-8"))
            stdout_buffer.flush()
            return
        print(output, end="", flush=True)


__all__ = [
    "CANDIDATE_SYSTEM_PROMPT",
    "MAX_DESTINATION_CANDIDATES",
    "DestinationCandidate",
    "DestinationCandidateGenerator",
    "DestinationCandidateSet",
    "DestinationDiscoveryPipeline",
    "DestinationDiscoveryPipelineResult",
]
