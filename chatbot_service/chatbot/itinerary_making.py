"""Build a verified itinerary candidate set and request an optimized route."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from chatbot.destination_discovery import _destination_name_matches
from chatbot.intent import TravelIntent
from chatbot.semantic import (
    ConversationMessage,
    SemanticActionType,
    SemanticInterpretation,
)
from chatbot.tool_planner import PlannedToolCall
from chatbot.tools.models import (
    MapboxCandidateResolutionData,
    MapboxOptimizedRouteData,
    MapboxRouteGeometry,
    RagToolData,
    ItineraryData,
    ToolResult,
)
from chatbot.tools.registry import (
    CREATE_ITINERARY_TOOL_NAME,
    MAPBOX_OPTIMIZE_ROUTE_TOOL_NAME,
    MAPBOX_RESOLVE_CANDIDATES_TOOL_NAME,
    ToolExecution,
)


logger = logging.getLogger(__name__)

MAX_ITINERARY_STOPS = 12
MAX_GENERATED_CANDIDATES = 24
MAX_CANDIDATE_BATCH_SIZE = 5
DEFAULT_ROUTE_PROFILE = "driving"
DEFAULT_MAX_ITINERARY_TOOL_CALLS = 6
_RAG_ADAPTER = TypeAdapter(ToolResult[RagToolData])
_RESOLUTION_ADAPTER = TypeAdapter(ToolResult[MapboxCandidateResolutionData])


ITINERARY_CANDIDATE_PROMPT = """Tạo danh sách ứng viên cho một lịch trình du lịch cụ thể.
Chỉ trả dữ liệu theo schema. Ưu tiên Knowledge Base, sau đó dùng kiến thức ổn định.
Không tạo địa chỉ, tọa độ, Mapbox ID, rating, giờ mở cửa hoặc route geometry.
Sắp ứng viên tốt nhất lên trước. Chọn các địa điểm phù hợp với điểm đến, thời lượng và
ràng buộc của người dùng. Không chia ngày và không tự tối ưu thứ tự di chuyển.
"""


class ItineraryModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        allow_inf_nan=False,
        populate_by_name=True,
        str_strip_whitespace=True,
    )


class ItineraryCandidate(ItineraryModel):
    name: str = Field(min_length=1, max_length=200)
    aliases: list[str] = Field(default_factory=list, max_length=5)
    category_hints: list[str] = Field(
        default_factory=list,
        alias="categoryHints",
        max_length=5,
    )
    reason: str = Field(min_length=1, max_length=500)


class ItineraryCandidatePlan(ItineraryModel):
    title: str = Field(min_length=1, max_length=200)
    destination: str = Field(min_length=1, max_length=200)
    candidates: list[ItineraryCandidate] = Field(
        min_length=2,
        max_length=MAX_GENERATED_CANDIDATES,
    )


class ItineraryPlaceReference(ItineraryModel):
    """A place selected from the immediately preceding chatbot answer."""

    mapbox_id: str = Field(alias="mapboxId", min_length=1, max_length=256)
    name: str = Field(min_length=1, max_length=200)
    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(ge=-90, le=90)


class ItineraryCandidateGenerator:
    """Ask Gemini for bounded place names without provider-owned fields."""

    def __init__(self, chat_model: Any) -> None:
        self._structured_model = chat_model.with_structured_output(
            ItineraryCandidatePlan,
            method="json_schema",
        )

    def generate(
        self,
        question: str,
        *,
        interpretation: SemanticInterpretation,
        history: Sequence[ConversationMessage],
        knowledge_chunks: Sequence[dict[str, str]],
    ) -> ItineraryCandidatePlan:
        payload = {
            "question": question,
            "history": [message.model_dump(mode="json") for message in history],
            "semanticInterpretation": interpretation.model_dump(
                mode="json",
                exclude_none=True,
            ),
            "knowledgeBase": list(knowledge_chunks),
        }
        result = self._structured_model.invoke(
            [
                SystemMessage(content=ITINERARY_CANDIDATE_PROMPT),
                HumanMessage(
                    content=json.dumps(
                        payload,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                ),
            ]
        )
        if isinstance(result, ItineraryCandidatePlan):
            return result
        return ItineraryCandidatePlan.model_validate(result)


class VerifiedItineraryStop(ItineraryModel):
    mapbox_id: str = Field(alias="mapboxId", min_length=1)
    name: str = Field(min_length=1, max_length=200)
    full_address: str | None = Field(default=None, alias="fullAddress")
    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(ge=-90, le=90)
    reason: str | None = Field(default=None, max_length=500)


class OptimizedItineraryStop(VerifiedItineraryStop):
    order: int = Field(ge=1)
    input_index: int = Field(alias="inputIndex", ge=0)


RouteGeometry = MapboxRouteGeometry
ItineraryOptimizationData = MapboxOptimizedRouteData


_OPTIMIZATION_ADAPTER = TypeAdapter(ToolResult[ItineraryOptimizationData])
_ITINERARY_ADAPTER = TypeAdapter(ToolResult[ItineraryData])


class ItineraryMakingData(ItineraryModel):
    title: str = Field(min_length=1, max_length=200)
    destination: str = Field(min_length=1, max_length=200)
    duration_days: int = Field(alias="durationDays", ge=1, le=365)
    duration_nights: int = Field(alias="durationNights", ge=0, le=365)
    profile: Literal["driving", "walking", "cycling"]
    stops: list[OptimizedItineraryStop] = Field(
        min_length=2,
        max_length=MAX_ITINERARY_STOPS,
    )
    route: RouteGeometry
    distance_meters: float = Field(alias="distanceMeters", ge=0)
    duration_seconds: float = Field(alias="durationSeconds", ge=0)


class ToolExecutor(Protocol):
    def execute(self, name: str, arguments: Any) -> ToolExecution: ...


RouteOptimizer = Callable[[PlannedToolCall], ToolExecution]
ItineraryCreator = Callable[[PlannedToolCall], ToolExecution]


@dataclass(frozen=True)
class ItineraryMakingPipelineResult:
    calls: list[PlannedToolCall]
    executions: list[ToolExecution]
    evidence: dict[str, Any]
    itinerary: ItineraryMakingData | ItineraryData | None


class ItineraryMakingPipeline:
    """Generate, verify, deduplicate and optimize one itinerary."""

    def __init__(
        self,
        chat_model: Any,
        registry: ToolExecutor,
        *,
        route_optimizer: RouteOptimizer | None = None,
        itinerary_creator: ItineraryCreator | None = None,
        candidate_generator: ItineraryCandidateGenerator | None = None,
        max_tool_calls: int = DEFAULT_MAX_ITINERARY_TOOL_CALLS,
    ) -> None:
        if max_tool_calls < 1:
            raise ValueError("max_tool_calls must be positive")
        self._chat_model = chat_model
        self._registry = registry
        self._route_optimizer = route_optimizer
        self._itinerary_creator = itinerary_creator
        self._candidate_generator = candidate_generator
        self._max_tool_calls = max_tool_calls

    def execute(
        self,
        question: str,
        *,
        history: Sequence[ConversationMessage],
        interpretation: SemanticInterpretation,
        planned_calls: Sequence[PlannedToolCall],
        route_profile: Literal["driving", "walking", "cycling"] = DEFAULT_ROUTE_PROFILE,
        prior_places: Sequence[ItineraryPlaceReference] = (),
    ) -> ItineraryMakingPipelineResult:
        calls: list[PlannedToolCall] = []
        executions: list[ToolExecution] = []
        if route_profile not in {"driving", "walking", "cycling"}:
            return self._failure(calls, executions, "invalid_route_profile")
        action_types = {action.type for action in interpretation.actions}
        if (
            interpretation.primary_intent != TravelIntent.ITINERARY_MAKING
            or SemanticActionType.MAKE_ITINERARY not in action_types
        ):
            return self._failure(calls, executions, "invalid_itinerary_intent")

        destination = (
            interpretation.location.near
            or next(iter(interpretation.entities.destinations), "")
        )
        if not destination:
            return self._failure(calls, executions, "missing_destination")

        rag_call = next(
            (call for call in planned_calls if call.evidence_kind == "knowledge"),
            None,
        )
        rag_execution = self._run_registry(rag_call, calls, executions)

        coordinates = self._semantic_coordinates(interpretation)
        if coordinates is None:
            destination_call = next(
                (
                    call
                    for call in planned_calls
                    if call.evidence_kind == "destination_location"
                ),
                None,
            )
            destination_execution = self._run_registry(
                destination_call,
                calls,
                executions,
            )
            coordinates = self._first_result_coordinates(
                destination_execution,
                destination=destination,
            )
        if coordinates is None:
            return self._failure(
                calls,
                executions,
                "destination_not_resolved",
                knowledge_chunks=self._knowledge_chunks(rag_execution),
            )

        verified_stops: list[VerifiedItineraryStop] = []
        if prior_places:
            prior_by_id: dict[str, ItineraryPlaceReference] = {}
            for place in prior_places:
                prior_by_id.setdefault(place.mapbox_id, place)
            selected_prior_places = list(prior_by_id.values())[:MAX_ITINERARY_STOPS]
            if len(selected_prior_places) < 2:
                return self._failure(
                    calls,
                    executions,
                    "insufficient_verified_stops",
                    knowledge_chunks=self._knowledge_chunks(rag_execution),
                )
            proposal = ItineraryCandidatePlan(
                title=f"Lịch trình khám phá {destination}",
                destination=destination,
                candidates=[
                    ItineraryCandidate(
                        name=place.name,
                        reason="Địa điểm đã được chọn từ gợi ý trước đó.",
                    )
                    for place in selected_prior_places
                ],
            )
            verified_stops = [
                VerifiedItineraryStop(
                    mapboxId=place.mapbox_id,
                    name=place.name,
                    longitude=place.longitude,
                    latitude=place.latitude,
                )
                for place in selected_prior_places
            ]
        else:
            try:
                generator = self._candidate_generator or ItineraryCandidateGenerator(
                    self._chat_model
                )
                proposal = generator.generate(
                    question,
                    interpretation=interpretation,
                    history=history,
                    knowledge_chunks=self._knowledge_chunks(rag_execution),
                )
            except Exception as error:
                logger.warning(
                    "Itinerary candidate generation failed (%s)",
                    type(error).__name__,
                )
                return self._failure(
                    calls,
                    executions,
                    "candidate_generation_failed",
                    knowledge_chunks=self._knowledge_chunks(rag_execution),
                )
        if not prior_places and not _destination_name_matches(proposal.destination, destination):
            return self._failure(
                calls,
                executions,
                "candidate_destination_mismatch",
                knowledge_chunks=self._knowledge_chunks(rag_execution),
            )

        selected_candidates = proposal.candidates[:MAX_ITINERARY_STOPS]
        candidate_by_id = {
            f"candidate-{index}": candidate
            for index, candidate in enumerate(selected_candidates, start=1)
        }
        if not prior_places:
            for offset in range(0, len(selected_candidates), MAX_CANDIDATE_BATCH_SIZE):
                batch_items = list(candidate_by_id.items())[
                    offset : offset + MAX_CANDIDATE_BATCH_SIZE
                ]
                resolution_call = self._candidate_resolution_call(
                    coordinates,
                    batch_items,
                )
                resolution_execution = self._run_registry(
                    resolution_call,
                    calls,
                    executions,
                )
                if resolution_execution is None:
                    return self._failure(
                        calls,
                        executions,
                        "tool_call_budget_exceeded",
                        knowledge_chunks=self._knowledge_chunks(rag_execution),
                    )
                verified_stops.extend(
                    self._matched_stops(resolution_execution, candidate_by_id)
                )

        unique_stops = self._deduplicate_stops(verified_stops)
        if len(unique_stops) < 2:
            return self._failure(
                calls,
                executions,
                "insufficient_verified_stops",
                knowledge_chunks=self._knowledge_chunks(rag_execution),
                verified_stops=unique_stops,
            )
        if self._itinerary_creator is not None:
            return self._create_persisted_itinerary(
                calls,
                executions,
                unique_stops=unique_stops,
                title=proposal.title,
                destination=destination,
                days=interpretation.time_context.duration_days or 1,
                nights=(
                    interpretation.time_context.duration_nights
                    if interpretation.time_context.duration_nights is not None
                    else max(interpretation.time_context.duration_days or 1, 1) - 1
                ),
                route_profile=route_profile,
                knowledge_chunks=self._knowledge_chunks(rag_execution),
            )
        if self._route_optimizer is None:
            return self._failure(
                calls,
                executions,
                "route_optimizer_unavailable",
                knowledge_chunks=self._knowledge_chunks(rag_execution),
                verified_stops=unique_stops,
            )
        if not self._has_budget(calls):
            return self._failure(
                calls,
                executions,
                "tool_call_budget_exceeded",
                knowledge_chunks=self._knowledge_chunks(rag_execution),
                verified_stops=unique_stops,
            )

        optimization_call = PlannedToolCall(
            MAPBOX_OPTIMIZE_ROUTE_TOOL_NAME,
            {
                "profile": route_profile,
                "stops": [
                    stop.model_dump(
                        mode="json",
                        by_alias=True,
                        exclude_none=True,
                        exclude={"full_address", "reason"},
                    )
                    for stop in unique_stops
                ],
            },
            evidence_kind="itinerary_route",
        )
        calls.append(optimization_call)
        try:
            optimization_execution = self._route_optimizer(optimization_call)
        except Exception as error:
            logger.warning(
                "Itinerary route optimization failed (%s)",
                type(error).__name__,
            )
            return self._failure(
                calls,
                executions,
                "route_optimizer_failed",
                knowledge_chunks=self._knowledge_chunks(rag_execution),
                verified_stops=unique_stops,
            )
        executions.append(optimization_execution)
        optimization = self._parse_optimization(optimization_execution)
        if optimization is None:
            return self._failure(
                calls,
                executions,
                optimization_execution.error_code or "invalid_optimization_result",
                knowledge_chunks=self._knowledge_chunks(rag_execution),
                verified_stops=unique_stops,
            )
        if not self._optimization_matches_inputs(
            optimization,
            unique_stops,
            expected_profile=route_profile,
        ):
            return self._failure(
                calls,
                executions,
                "invalid_optimization_result",
                knowledge_chunks=self._knowledge_chunks(rag_execution),
                verified_stops=unique_stops,
            )

        days = interpretation.time_context.duration_days or 1
        nights = interpretation.time_context.duration_nights
        if nights is None:
            nights = max(days - 1, 0)
        ordered_stops = [
            OptimizedItineraryStop(
                **unique_stops[optimized_stop.input_index].model_dump(
                    mode="python"
                ),
                order=optimized_stop.order,
                inputIndex=optimized_stop.input_index,
            )
            for optimized_stop in optimization.ordered_stops
        ]
        itinerary = ItineraryMakingData(
            title=proposal.title,
            destination=destination,
            durationDays=days,
            durationNights=nights,
            profile=optimization.profile,
            stops=ordered_stops,
            route=optimization.geometry,
            distanceMeters=optimization.distance_meters,
            durationSeconds=optimization.duration_seconds,
        )
        evidence = {
            "success": True,
            "knowledgeBase": self._knowledge_chunks(rag_execution),
            "itinerary": itinerary.model_dump(
                mode="json",
                by_alias=True,
                exclude_none=True,
            ),
        }
        return ItineraryMakingPipelineResult(calls, executions, evidence, itinerary)

    def _create_persisted_itinerary(
        self,
        calls: list[PlannedToolCall],
        executions: list[ToolExecution],
        *,
        unique_stops: Sequence[VerifiedItineraryStop],
        title: str,
        destination: str,
        days: int,
        nights: int,
        route_profile: Literal["driving", "walking", "cycling"],
        knowledge_chunks: Sequence[dict[str, str]],
    ) -> ItineraryMakingPipelineResult:
        if not self._has_budget(calls):
            return self._failure(
                calls,
                executions,
                "tool_call_budget_exceeded",
                knowledge_chunks=knowledge_chunks,
                verified_stops=unique_stops,
            )

        create_call = PlannedToolCall(
            CREATE_ITINERARY_TOOL_NAME,
            {
                "title": title,
                "destination": destination,
                "durationDays": days,
                "durationNights": nights,
                "profile": route_profile,
                "stops": [
                    stop.model_dump(
                        mode="json",
                        by_alias=True,
                        exclude_none=True,
                        exclude={"full_address", "reason"},
                    )
                    for stop in unique_stops
                ],
            },
            evidence_kind="itinerary_persistence",
        )
        calls.append(create_call)
        try:
            execution = self._itinerary_creator(create_call)
        except Exception as error:
            logger.warning(
                "Itinerary persistence failed (%s)",
                type(error).__name__,
            )
            return self._failure(
                calls,
                executions,
                "itinerary_create_failed",
                knowledge_chunks=knowledge_chunks,
                verified_stops=unique_stops,
            )
        executions.append(execution)
        if not execution.success:
            return self._failure(
                calls,
                executions,
                execution.error_code or "itinerary_create_failed",
                knowledge_chunks=knowledge_chunks,
                verified_stops=unique_stops,
            )
        try:
            result = _ITINERARY_ADAPTER.validate_json(execution.content)
        except (ValidationError, ValueError):
            return self._failure(
                calls,
                executions,
                "invalid_itinerary_result",
                knowledge_chunks=knowledge_chunks,
                verified_stops=unique_stops,
            )
        if not result.success or result.data is None:
            return self._failure(
                calls,
                executions,
                result.error_code or "itinerary_create_failed",
                knowledge_chunks=knowledge_chunks,
                verified_stops=unique_stops,
            )
        itinerary = result.data
        evidence = {
            "success": True,
            "knowledgeBase": list(knowledge_chunks),
            "itinerary": itinerary.model_dump(
                mode="json",
                by_alias=True,
                exclude_none=True,
            ),
        }
        return ItineraryMakingPipelineResult(calls, executions, evidence, itinerary)

    def _run_registry(
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
        execution: ToolExecution | None,
        *,
        destination: str,
    ) -> tuple[float, float] | None:
        if execution is None or not execution.success:
            return None
        try:
            payload = json.loads(execution.content)
            results = payload["data"]["results"]
            if not isinstance(results, list):
                return None
            for result in results:
                if not isinstance(result, dict):
                    continue
                if not _destination_name_matches(result.get("name"), destination):
                    continue
                return float(result["longitude"]), float(result["latitude"])
        except (KeyError, TypeError, ValueError):
            return None
        return None

    @staticmethod
    def _candidate_resolution_call(
        coordinates: tuple[float, float],
        batch_items: Sequence[tuple[str, ItineraryCandidate]],
    ) -> PlannedToolCall:
        longitude, latitude = coordinates
        return PlannedToolCall(
            MAPBOX_RESOLVE_CANDIDATES_TOOL_NAME,
            {
                "longitude": longitude,
                "latitude": latitude,
                "candidates": [
                    {
                        "candidateId": candidate_id,
                        "name": candidate.name,
                        "aliases": candidate.aliases,
                        "categoryHints": candidate.category_hints,
                    }
                    for candidate_id, candidate in batch_items
                ],
            },
            evidence_kind="candidate_resolution",
        )

    @staticmethod
    def _parse_tool_result(
        adapter: TypeAdapter[Any],
        execution: ToolExecution | None,
    ) -> Any | None:
        if execution is None or not execution.success:
            return None
        try:
            result = adapter.validate_json(execution.content)
        except (ValidationError, ValueError):
            return None
        return result.data

    @classmethod
    def _knowledge_chunks(
        cls,
        execution: ToolExecution | None,
    ) -> list[dict[str, str]]:
        data = cls._parse_tool_result(_RAG_ADAPTER, execution)
        if data is None:
            return []
        return [
            {"title": chunk.title, "content": chunk.content}
            for chunk in data.chunks
        ]

    @classmethod
    def _matched_stops(
        cls,
        execution: ToolExecution,
        candidate_by_id: dict[str, ItineraryCandidate],
    ) -> list[VerifiedItineraryStop]:
        data = cls._parse_tool_result(_RESOLUTION_ADAPTER, execution)
        if data is None:
            return []
        stops: list[VerifiedItineraryStop] = []
        for match in data.results:
            candidate = candidate_by_id.get(match.candidate_id)
            place = match.place
            if (
                match.status != "matched"
                or place is None
                or candidate is None
                or place.feature_type.casefold() != "poi"
            ):
                continue
            stops.append(
                VerifiedItineraryStop(
                    mapboxId=place.mapbox_id,
                    name=place.name,
                    fullAddress=place.full_address,
                    longitude=place.longitude,
                    latitude=place.latitude,
                    reason=candidate.reason,
                )
            )
        return stops

    @staticmethod
    def _deduplicate_stops(
        stops: Sequence[VerifiedItineraryStop],
    ) -> list[VerifiedItineraryStop]:
        unique: list[VerifiedItineraryStop] = []
        seen: set[str] = set()
        for stop in stops:
            if stop.mapbox_id in seen:
                continue
            seen.add(stop.mapbox_id)
            unique.append(stop)
        return unique

    @staticmethod
    def _parse_optimization(
        execution: ToolExecution,
    ) -> ItineraryOptimizationData | None:
        if not execution.success:
            return None
        try:
            result = _OPTIMIZATION_ADAPTER.validate_json(execution.content)
        except (ValidationError, ValueError):
            return None
        return result.data

    @staticmethod
    def _optimization_matches_inputs(
        optimization: ItineraryOptimizationData,
        inputs: Sequence[VerifiedItineraryStop],
        *,
        expected_profile: str,
    ) -> bool:
        input_ids = [stop.mapbox_id for stop in inputs]
        output_ids = [stop.mapbox_id for stop in optimization.ordered_stops]
        return (
            optimization.profile == expected_profile
            and len(output_ids) == len(input_ids)
            and set(output_ids) == set(input_ids)
            and all(
                stop.mapbox_id == input_ids[stop.input_index]
                for stop in optimization.ordered_stops
            )
        )

    @staticmethod
    def _failure(
        calls: list[PlannedToolCall],
        executions: list[ToolExecution],
        error_code: str,
        *,
        knowledge_chunks: Sequence[dict[str, str]] = (),
        verified_stops: Sequence[VerifiedItineraryStop] = (),
    ) -> ItineraryMakingPipelineResult:
        evidence = {
            "success": False,
            "errorCode": error_code,
            "knowledgeBase": list(knowledge_chunks),
            "verifiedStops": [
                stop.model_dump(mode="json", by_alias=True, exclude_none=True)
                for stop in verified_stops
            ],
        }
        return ItineraryMakingPipelineResult(calls, executions, evidence, None)


__all__ = [
    "DEFAULT_MAX_ITINERARY_TOOL_CALLS",
    "DEFAULT_ROUTE_PROFILE",
    "ITINERARY_CANDIDATE_PROMPT",
    "ItineraryCandidate",
    "ItineraryCandidateGenerator",
    "ItineraryCandidatePlan",
    "ItineraryPlaceReference",
    "ItineraryMakingData",
    "ItineraryMakingPipeline",
    "ItineraryMakingPipelineResult",
    "ItineraryOptimizationData",
    "MAPBOX_OPTIMIZE_ROUTE_TOOL_NAME",
    "MAX_GENERATED_CANDIDATES",
    "MAX_ITINERARY_STOPS",
    "OptimizedItineraryStop",
    "RouteGeometry",
    "VerifiedItineraryStop",
]
