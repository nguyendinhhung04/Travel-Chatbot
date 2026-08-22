"""Deterministically map semantic actions to the chatbot tool allowlist."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from chatbot.category_resolver import resolve_mapbox_categories
from chatbot.intent import TravelIntent
from chatbot.semantic import (
    InterpretationStatus,
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
        interpretation.primary_intent in _RAG_INTENTS
        or action_types.intersection(_RAG_ACTIONS)
    ):
        calls.append(
            PlannedToolCall(
                SEARCH_TRAVEL_KNOWLEDGE_TOOL_NAME,
                {"query": interpretation.normalized_query},
            )
        )

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


def _plan_named_place_calls(
    interpretation: SemanticInterpretation,
) -> list[PlannedToolCall]:
    queries = interpretation.entities.places or interpretation.entities.destinations
    if not queries:
        return []

    common_arguments = _mapbox_location_arguments(interpretation)
    constraints = interpretation.constraints
    if constraints.open_now is not None:
        common_arguments["open_now"] = constraints.open_now
    if constraints.minimum_rating is not None:
        common_arguments["minimum_rating"] = constraints.minimum_rating

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
    return [
        PlannedToolCall(
            MAPBOX_CATEGORY_SEARCH_TOOL_NAME,
            {
                "category_id": category,
                "language": "vi",
                "limit": DEFAULT_MAPBOX_RESULT_LIMIT,
                **common_arguments,
            },
        )
        for category in categories
    ]


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
    "DEFAULT_MAPBOX_RESULT_LIMIT",
    "DEFAULT_MAX_CATEGORIES",
    "PlannedToolCall",
    "plan_tools",
]
