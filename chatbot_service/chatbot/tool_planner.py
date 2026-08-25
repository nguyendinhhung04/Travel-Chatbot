"""Deterministically map semantic actions to the chatbot tool allowlist."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from chatbot.category_resolver import resolve_mapbox_categories
from chatbot.intent import TravelIntent
from chatbot.semantic import (
    InterpretationStatus,
    SearchTargetType,
    SemanticActionType,
    SemanticInterpretation,
)
from chatbot.tools.registry import (
    MAPBOX_CATEGORY_SEARCH_TOOL_NAME,
    MAPBOX_FORWARD_SEARCH_TOOL_NAME,
    MAPBOX_REVERSE_LOOKUP_TOOL_NAME,
)
from chatbot.tools.rag_tool import SEARCH_TRAVEL_KNOWLEDGE_TOOL_NAME


DEFAULT_MAPBOX_RESULT_LIMIT = 5
DESTINATION_FORWARD_RESULT_LIMIT = 3
DEFAULT_MAPBOX_CATEGORY_REQUEST_LIMIT = 10
DEFAULT_MAPBOX_MINIMUM_RATING = 0.0
DEFAULT_MAPBOX_RANK_STRATEGY = "relevance"
DEFAULT_MAX_CATEGORIES = 3
_KILOMETERS_PER_DEGREE = 111.32

_RAG_INTENTS = frozenset(
    {
        TravelIntent.DESTINATION_DISCOVERY,
        TravelIntent.PLACE_DETAILS,
        TravelIntent.TRAVEL_QA,
        TravelIntent.ITINERARY_ADVICE,
        TravelIntent.TRANSPORTATION_QA,
        TravelIntent.BUDGET_QA,
    }
)
_RAG_ACTIONS = frozenset(
    {
        SemanticActionType.ANSWER_TRAVEL_QUESTION,
        SemanticActionType.PROVIDE_ITINERARY_ADVICE,
        SemanticActionType.PROVIDE_TRANSPORTATION_ADVICE,
        SemanticActionType.PROVIDE_BUDGET_ADVICE,
    }
)


@dataclass(frozen=True)
class PlannedToolCall:
    """One validated tool request selected by backend semantics."""

    name: str
    arguments: dict[str, Any]
    destination: str | None = None
    evidence_kind: str | None = None


def plan_tools(
    interpretation: SemanticInterpretation,
    *,
    max_categories: int = DEFAULT_MAX_CATEGORIES,
) -> tuple[PlannedToolCall, ...]:
    """Create an ordered read-only tool plan for one interpreted question."""
    if interpretation.status in {
        InterpretationStatus.NEEDS_CLARIFICATION,
        InterpretationStatus.UNSUPPORTED,
    } or interpretation.primary_intent in {
        TravelIntent.GENERAL_CHAT,
        TravelIntent.UNSUPPORTED_CAPABILITY,
    }:
        return ()

    action_types = {action.type for action in interpretation.actions}
    calls: list[PlannedToolCall] = []

    if (
        SemanticActionType.DISCOVER_PLACES in action_types
        and _needs_destination_lookup(interpretation)
        and interpretation.primary_intent != TravelIntent.DESTINATION_DISCOVERY
    ):
        destination_call = _plan_destination_forward_call(interpretation)
        if destination_call is not None:
            calls.append(destination_call)

    if (
        interpretation.primary_intent in _RAG_INTENTS
        or action_types.intersection(_RAG_ACTIONS)
    ):
        rag_arguments: dict[str, Any] = {
            "query": interpretation.normalized_query,
        }
        rag_destination = _primary_destination(interpretation)
        if rag_destination is not None:
            rag_arguments["destination"] = rag_destination
        calls.append(
            PlannedToolCall(
                SEARCH_TRAVEL_KNOWLEDGE_TOOL_NAME,
                rag_arguments,
                destination=rag_destination,
                evidence_kind="knowledge",
            )
        )

    if (
        interpretation.primary_intent == TravelIntent.DESTINATION_DISCOVERY
        and SemanticActionType.DISCOVER_PLACES in action_types
        and _needs_destination_lookup(interpretation)
    ):
        destination_call = _plan_destination_forward_call(interpretation)
        if destination_call is not None:
            calls.append(destination_call)

    if SemanticActionType.FIND_NAMED_PLACE in action_types:
        calls.extend(_plan_named_place_calls(interpretation))

    if SemanticActionType.DISCOVER_PLACES in action_types:
        calls.extend(
            _plan_category_calls(
                interpretation,
                max_categories=max_categories,
            )
        )

    if SemanticActionType.REVERSE_GEOCODE in action_types:
        reverse_call = _plan_reverse_call(interpretation)
        if reverse_call is not None:
            calls.append(reverse_call)

    return _deduplicate_calls(calls)


def _primary_destination(
    interpretation: SemanticInterpretation,
) -> str | None:
    if interpretation.location.near:
        return interpretation.location.near
    if interpretation.entities.destinations:
        return interpretation.entities.destinations[0]
    return None


def _needs_destination_lookup(
    interpretation: SemanticInterpretation,
) -> bool:
    return (
        interpretation.location.longitude is None
        and interpretation.location.latitude is None
        and _primary_destination(interpretation) is not None
    )


def _plan_destination_forward_call(
    interpretation: SemanticInterpretation,
) -> PlannedToolCall | None:
    destination = _primary_destination(interpretation)
    if destination is None:
        return None
    destination_types = (
        "city,place"
        if interpretation.primary_intent == TravelIntent.DESTINATION_DISCOVERY
        else "poi,address,city,place"
    )
    return PlannedToolCall(
        MAPBOX_FORWARD_SEARCH_TOOL_NAME,
        {
            "q": destination,
            "language": "vi",
            "limit": DESTINATION_FORWARD_RESULT_LIMIT,
            "types": destination_types,
            "rank_strategy": DEFAULT_MAPBOX_RANK_STRATEGY,
            "auto_complete": False,
        },
        destination=destination,
        evidence_kind="destination_location",
    )


def _plan_named_place_calls(
    interpretation: SemanticInterpretation,
) -> list[PlannedToolCall]:
    queries = interpretation.entities.places or interpretation.entities.destinations
    if not queries:
        return []

    common_arguments = _mapbox_location_arguments(interpretation)
    constraints = interpretation.constraints
    search_target = _forward_search_target(interpretation)
    common_arguments["types"] = search_target.value
    common_arguments["rank_strategy"] = (
        constraints.rank_strategy or DEFAULT_MAPBOX_RANK_STRATEGY
    )
    if search_target == SearchTargetType.POI:
        if constraints.open_now is not None:
            common_arguments["open_now"] = constraints.open_now
        common_arguments["minimum_rating"] = (
            constraints.minimum_rating
            if constraints.minimum_rating is not None
            else DEFAULT_MAPBOX_MINIMUM_RATING
        )

    return [
        PlannedToolCall(
            MAPBOX_FORWARD_SEARCH_TOOL_NAME,
            {
                "q": query,
                "language": "vi",
                "limit": DEFAULT_MAPBOX_RESULT_LIMIT,
                **common_arguments,
            },
        )
        for query in queries
    ]


def _plan_category_calls(
    interpretation: SemanticInterpretation,
    *,
    max_categories: int,
) -> list[PlannedToolCall]:
    categories = resolve_mapbox_categories(
        interpretation,
        max_categories=max_categories,
    )
    common_arguments = _mapbox_location_arguments(interpretation)
    if _needs_destination_lookup(interpretation):
        common_arguments.pop("near", None)
    constraints = interpretation.constraints
    minimum_rating = (
        constraints.minimum_rating
        if constraints.minimum_rating is not None
        else DEFAULT_MAPBOX_MINIMUM_RATING
    )
    return [
        PlannedToolCall(
            MAPBOX_CATEGORY_SEARCH_TOOL_NAME,
            {
                "category_id": category,
                "language": "vi",
                "limit": DEFAULT_MAPBOX_CATEGORY_REQUEST_LIMIT,
                "minimum_rating": minimum_rating,
                **common_arguments,
            },
            destination=_primary_destination(interpretation),
            evidence_kind="poi",
        )
        for category in categories
    ]


def _forward_search_target(
    interpretation: SemanticInterpretation,
) -> SearchTargetType:
    if interpretation.entities.search_target is not None:
        return interpretation.entities.search_target
    if interpretation.entities.places:
        return SearchTargetType.POI
    return SearchTargetType.PLACE


def _plan_reverse_call(
    interpretation: SemanticInterpretation,
) -> PlannedToolCall | None:
    location = interpretation.location
    if location.longitude is None or location.latitude is None:
        return None
    return PlannedToolCall(
        MAPBOX_REVERSE_LOOKUP_TOOL_NAME,
        {
            "longitude": location.longitude,
            "latitude": location.latitude,
            "language": "vi",
            "limit": DEFAULT_MAPBOX_RESULT_LIMIT,
        },
    )


def _mapbox_location_arguments(
    interpretation: SemanticInterpretation,
) -> dict[str, Any]:
    location = interpretation.location
    arguments: dict[str, Any] = {}
    near = location.near
    if near is None and interpretation.entities.destinations:
        near = interpretation.entities.destinations[0]
    if near:
        arguments["near"] = near
    if location.longitude is not None and location.latitude is not None:
        arguments["proximity"] = f"{location.longitude},{location.latitude}"
        if location.radius_km is not None:
            arguments["radius"] = round(
                location.radius_km / _KILOMETERS_PER_DEGREE,
                6,
            )
    return arguments


def _deduplicate_calls(
    calls: list[PlannedToolCall],
) -> tuple[PlannedToolCall, ...]:
    unique_calls: list[PlannedToolCall] = []
    seen: set[tuple[str, tuple[tuple[str, str], ...]]] = set()
    for call in calls:
        key = (
            call.name,
            tuple(sorted((name, repr(value)) for name, value in call.arguments.items())),
        )
        if key in seen:
            continue
        seen.add(key)
        unique_calls.append(call)
    return tuple(unique_calls)


__all__ = [
    "DEFAULT_MAPBOX_CATEGORY_REQUEST_LIMIT",
    "DEFAULT_MAPBOX_MINIMUM_RATING",
    "DEFAULT_MAPBOX_RANK_STRATEGY",
    "DEFAULT_MAPBOX_RESULT_LIMIT",
    "DEFAULT_MAX_CATEGORIES",
    "DESTINATION_FORWARD_RESULT_LIMIT",
    "PlannedToolCall",
    "plan_tools",
]
