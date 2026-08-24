"""Structured candidate generation and deterministic Mapbox place matching."""

from __future__ import annotations

import json
import logging
import re
import sys
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from difflib import SequenceMatcher
from enum import Enum
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from chatbot.semantic import ConversationMessage, SemanticInterpretation
from chatbot.tool_planner import PlannedToolCall
from chatbot.tools.models import (
    MapboxPlaceItem,
    MapboxPlaceToolData,
    ToolResult,
)
from chatbot.tools.registry import (
    MAPBOX_FORWARD_SEARCH_TOOL_NAME,
    ToolExecution,
    ToolRegistry,
)


MAX_DESTINATION_CANDIDATES = 5
MINIMUM_NAME_SIMILARITY = 0.88
AMBIGUOUS_SCORE_GAP = 0.05
MINIMUM_DISTANCE_GAP_METERS = 100.0
logger = logging.getLogger(__name__)
_PLACE_RESULT_ADAPTER = TypeAdapter(ToolResult[MapboxPlaceToolData])

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


class CandidateMatchStatus(str, Enum):
    MATCHED = "matched"
    AMBIGUOUS = "ambiguous"
    NOT_FOUND = "not_found"
    LOOKUP_FAILED = "lookup_failed"


class CandidateMatch(DiscoveryModel):
    candidate: DestinationCandidate
    status: CandidateMatchStatus
    similarity: float | None = Field(default=None, ge=0, le=1)
    place: MapboxPlaceItem | None = None


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
        knowledge_result: dict[str, Any] | None,
    ) -> DestinationCandidateSet:
        payload = {
            "question": question,
            "history": [message.model_dump(mode="json") for message in history],
            "semanticInterpretation": interpretation.model_dump(
                mode="json",
                exclude_none=True,
            ),
            "knowledgeBaseResult": knowledge_result,
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
                coordinates = self._first_result_coordinates(destination_execution)

        matches: list[CandidateMatch] = []
        matched_data: list[tuple[CandidateMatch, MapboxPlaceToolData]] = []
        category_data: MapboxPlaceToolData | None = None
        category_call = next(
            (call for call in planned_calls if call.evidence_kind == "poi"),
            None,
        )

        if coordinates is not None:
            reserved_category_calls = 1 if category_call is not None else 0
            candidate_budget = max(
                0,
                self._max_tool_calls - len(calls) - reserved_category_calls,
            )
            for candidate in candidates.candidates[:candidate_budget]:
                candidate_call = self._candidate_forward_call(
                    candidate.name,
                    coordinates,
                )
                self._print_verification_request(candidate_call)
                candidate_execution = self._registry.execute(
                    candidate_call.name,
                    candidate_call.arguments,
                )
                self._print_verification_response(candidate_execution)
                calls.append(candidate_call)
                executions.append(candidate_execution)
                place_data = self._parse_place_data(candidate_execution)
                match = (
                    match_candidate(candidate, place_data.results)
                    if place_data is not None
                    else failed_candidate_match(candidate)
                )
                matches.append(match)
                if match.status == CandidateMatchStatus.MATCHED:
                    matched_data.append((match, place_data))

            if category_call is not None and self._has_budget(calls):
                resolved_category_call = self._with_proximity(
                    category_call,
                    coordinates,
                )
                category_execution = self._registry.execute(
                    resolved_category_call.name,
                    resolved_category_call.arguments,
                )
                calls.append(resolved_category_call)
                executions.append(category_execution)
                category_data = self._parse_place_data(category_execution)

        evidence = self._build_evidence(
            rag_execution=rag_execution,
            matched_data=matched_data,
            category_data=category_data,
            destination_resolved=coordinates is not None,
        )
        self._print_verification_result(
            destination=candidates.destination,
            destination_resolved=coordinates is not None,
            matches=matches,
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
                knowledge_result=self._successful_payload(rag_execution),
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
    ) -> tuple[float, float] | None:
        if not execution.success:
            return None
        try:
            payload = json.loads(execution.content)
            result = payload["data"]["results"][0]
            return float(result["longitude"]), float(result["latitude"])
        except (KeyError, IndexError, TypeError, ValueError):
            return None

    @staticmethod
    def _candidate_forward_call(
        candidate_name: str,
        coordinates: tuple[float, float],
    ) -> PlannedToolCall:
        longitude, latitude = coordinates
        return PlannedToolCall(
            MAPBOX_FORWARD_SEARCH_TOOL_NAME,
            {
                "q": candidate_name,
                "language": "vi",
                "limit": 2,
                "proximity": f"{longitude},{latitude}",
                "types": "poi",
                "rank_strategy": "relevance",
                "auto_complete": False,
            },
            evidence_kind="candidate_lookup",
        )

    @staticmethod
    def _with_proximity(
        call: PlannedToolCall,
        coordinates: tuple[float, float],
    ) -> PlannedToolCall:
        longitude, latitude = coordinates
        arguments = dict(call.arguments)
        arguments.pop("near", None)
        arguments["proximity"] = f"{longitude},{latitude}"
        return PlannedToolCall(
            call.name,
            arguments,
            destination=call.destination,
            evidence_kind=call.evidence_kind,
        )

    @staticmethod
    def _parse_place_data(
        execution: ToolExecution,
    ) -> MapboxPlaceToolData | None:
        if not execution.success:
            return None
        try:
            result = _PLACE_RESULT_ADAPTER.validate_json(execution.content)
        except (ValidationError, ValueError):
            return None
        return result.data

    @staticmethod
    def _print_verification_request(call: PlannedToolCall) -> None:
        """Print the sanitized Mapbox request used to verify one candidate."""
        payload = {
            "method": "GET",
            "path": "/search/searchbox/v1/forward",
            "query": call.arguments,
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
        """Print the raw Mapbox response returned for candidate verification."""
        try:
            tool_payload = json.loads(execution.content)
        except (TypeError, ValueError):
            response_payload: Any = {
                "success": False,
                "errorCode": "unparseable_tool_response",
                "errorMessage": "Không thể đọc response từ Mapbox tool.",
            }
        else:
            data = tool_payload.get("data") if isinstance(tool_payload, dict) else None
            raw_response = data.get("rawResponse") if isinstance(data, dict) else None
            response_payload = (
                raw_response
                if raw_response is not None
                else {
                    "success": tool_payload.get("success"),
                    "errorCode": tool_payload.get("errorCode"),
                    "errorMessage": tool_payload.get("errorMessage"),
                }
            )

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
    def _build_evidence(
        *,
        rag_execution: ToolExecution | None,
        matched_data: Sequence[tuple[CandidateMatch, MapboxPlaceToolData]],
        category_data: MapboxPlaceToolData | None,
        destination_resolved: bool,
    ) -> dict[str, Any]:
        matched_places: list[dict[str, Any]] = []
        seen_mapbox_ids: set[str] = set()
        for match, _data in matched_data:
            if match.place is None or match.place.mapbox_id in seen_mapbox_ids:
                continue
            seen_mapbox_ids.add(match.place.mapbox_id)
            matched_places.append(
                {
                    "name": match.candidate.name,
                    "categoryHints": match.candidate.category_hints,
                    "reason": match.candidate.reason,
                    "poiCategories": match.place.poi_categories,
                }
            )

        additional_places: list[dict[str, Any]] = []
        if category_data is not None:
            for place in category_data.results:
                if place.mapbox_id in seen_mapbox_ids:
                    continue
                seen_mapbox_ids.add(place.mapbox_id)
                additional_places.append(
                    DestinationDiscoveryPipeline._safe_place(place, category_data)
                )

        return {
            "knowledgeBase": DestinationDiscoveryPipeline._successful_payload(
                rag_execution
            ),
            "destinationResolved": destination_resolved,
            "matchedCandidates": matched_places,
            "additionalMapboxPlaces": additional_places,
        }

    @staticmethod
    def _safe_place(
        place: MapboxPlaceItem,
        data: MapboxPlaceToolData,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "place": place.model_dump(mode="json", by_alias=True),
        }
        provider_details = DestinationDiscoveryPipeline._provider_details_for(
            place.mapbox_id,
            data.raw_response,
        )
        if provider_details is not None:
            payload["providerDetails"] = provider_details
        return payload

    @staticmethod
    def _provider_details_for(
        mapbox_id: str,
        raw_response: dict[str, Any],
    ) -> dict[str, Any] | None:
        features = raw_response.get("features")
        if not isinstance(features, list):
            return None
        for feature in features:
            if not isinstance(feature, dict):
                continue
            properties = feature.get("properties")
            if (
                isinstance(properties, dict)
                and properties.get("mapbox_id") == mapbox_id
            ):
                return properties
        return None

    @staticmethod
    def _print_verification_result(
        *,
        destination: str,
        destination_resolved: bool,
        matches: Sequence[CandidateMatch],
        evidence: dict[str, Any],
    ) -> None:
        """Print verification outcomes without exposing prompts or raw responses."""
        payload = {
            "destination": destination,
            "destinationResolved": destination_resolved,
            "candidates": [
                {
                    "name": match.candidate.name,
                    "status": match.status.value,
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


def normalize_place_name(value: str) -> str:
    """Normalize Vietnamese and international place names for comparison."""
    value = value.lower().replace("đ", "d")
    decomposed = unicodedata.normalize("NFD", value)
    without_marks = "".join(
        character
        for character in decomposed
        if unicodedata.category(character) != "Mn"
    )
    words = re.findall(r"[a-z0-9]+", without_marks)
    return " ".join(words)


def place_name_similarity(left: str, right: str) -> float:
    """Return the best ordered or token-sorted name similarity."""
    normalized_left = normalize_place_name(left)
    normalized_right = normalize_place_name(right)
    if not normalized_left or not normalized_right:
        return 0.0
    if normalized_left == normalized_right:
        return 1.0
    ordered_score = SequenceMatcher(
        None,
        normalized_left,
        normalized_right,
    ).ratio()
    token_score = SequenceMatcher(
        None,
        " ".join(sorted(normalized_left.split())),
        " ".join(sorted(normalized_right.split())),
    ).ratio()
    return max(ordered_score, token_score)


def match_candidate(
    candidate: DestinationCandidate,
    places: Sequence[MapboxPlaceItem],
) -> CandidateMatch:
    """Match one Gemini candidate to at most one Mapbox result."""
    names = [candidate.name, *candidate.aliases]
    scored = [
        (
            max(place_name_similarity(name, place.name) for name in names),
            _category_matches(candidate.category_hints, place),
            place,
        )
        for place in places
    ]
    eligible = [item for item in scored if item[0] >= MINIMUM_NAME_SIMILARITY]
    if not eligible:
        return CandidateMatch(
            candidate=candidate,
            status=CandidateMatchStatus.NOT_FOUND,
        )

    category_matches = [item for item in eligible if item[1]]
    ranked = sorted(
        category_matches or eligible,
        key=lambda item: (
            -item[0],
            item[2].distance_meters
            if item[2].distance_meters is not None
            else float("inf"),
        ),
    )

    exact_matches = [item for item in ranked if item[0] == 1.0]
    if len(exact_matches) == 1:
        best_score, _, best_place = exact_matches[0]
        return CandidateMatch(
            candidate=candidate,
            status=CandidateMatchStatus.MATCHED,
            similarity=best_score,
            place=best_place,
        )
    if len(exact_matches) > 1:
        best_score, _, best_place = exact_matches[0]
        first_distance = best_place.distance_meters
        second_distance = exact_matches[1][2].distance_meters
        if (
            first_distance is not None
            and second_distance is not None
            and second_distance - first_distance >= MINIMUM_DISTANCE_GAP_METERS
        ):
            return CandidateMatch(
                candidate=candidate,
                status=CandidateMatchStatus.MATCHED,
                similarity=best_score,
                place=best_place,
            )
        return CandidateMatch(
            candidate=candidate,
            status=CandidateMatchStatus.AMBIGUOUS,
            similarity=best_score,
        )

    best_score, _, best_place = ranked[0]
    if (
        len(ranked) > 1
        and best_score - ranked[1][0] < AMBIGUOUS_SCORE_GAP
    ):
        return CandidateMatch(
            candidate=candidate,
            status=CandidateMatchStatus.AMBIGUOUS,
            similarity=best_score,
        )
    return CandidateMatch(
        candidate=candidate,
        status=CandidateMatchStatus.MATCHED,
        similarity=best_score,
        place=best_place,
    )


def failed_candidate_match(
    candidate: DestinationCandidate,
) -> CandidateMatch:
    return CandidateMatch(
        candidate=candidate,
        status=CandidateMatchStatus.LOOKUP_FAILED,
    )


def _category_matches(
    category_hints: Sequence[str],
    place: MapboxPlaceItem,
) -> bool:
    normalized_hints = {
        normalize_place_name(value)
        for value in category_hints
        if normalize_place_name(value)
    }
    if not normalized_hints:
        return False
    categories = {
        normalize_place_name(value)
        for value in [*place.poi_categories, *place.poi_category_ids]
        if normalize_place_name(value)
    }
    return bool(normalized_hints.intersection(categories))


__all__ = [
    "AMBIGUOUS_SCORE_GAP",
    "MINIMUM_DISTANCE_GAP_METERS",
    "CANDIDATE_SYSTEM_PROMPT",
    "MAX_DESTINATION_CANDIDATES",
    "MINIMUM_NAME_SIMILARITY",
    "CandidateMatch",
    "CandidateMatchStatus",
    "DestinationCandidate",
    "DestinationCandidateGenerator",
    "DestinationCandidateSet",
    "DestinationDiscoveryPipeline",
    "DestinationDiscoveryPipelineResult",
    "failed_candidate_match",
    "match_candidate",
    "normalize_place_name",
    "place_name_similarity",
]
