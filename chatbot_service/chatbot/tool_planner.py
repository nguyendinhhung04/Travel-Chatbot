"""Deterministically map semantic actions to the chatbot tool allowlist."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

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
ENRICHMENT_FORWARD_RESULT_LIMIT = 3
DEFAULT_MAPBOX_CATEGORY_REQUEST_LIMIT = 10
DEFAULT_MAPBOX_MINIMUM_RATING = 0.0
DEFAULT_MAPBOX_RANK_STRATEGY = "relevance"
DEFAULT_MAX_CATEGORIES = 3
MAX_ENRICHMENT_DESTINATIONS = 3
ENRICHMENT_CORE_CATEGORIES = (
    "tourist_attraction",
)
_KILOMETERS_PER_DEGREE = 111.32

_BROAD_ENRICHMENT_INTENTS = frozenset(
    {
        TravelIntent.DESTINATION_DISCOVERY,
        TravelIntent.TRAVEL_QA,
        TravelIntent.ITINERARY_ADVICE,
        TravelIntent.BUDGET_QA,
    }
)
_BROAD_ENRICHMENT_ACTIONS = frozenset(
    {
        SemanticActionType.ANSWER_TRAVEL_QUESTION,
        SemanticActionType.PROVIDE_ITINERARY_ADVICE,
        SemanticActionType.PROVIDE_BUDGET_ADVICE,
    }
)

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
    category_id: str | None = None


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
    if _needs_broad_enrichment(interpretation, action_types):
        return _deduplicate_calls(_plan_broad_enrichment(interpretation))

    calls: list[PlannedToolCall] = []

    if SemanticActionType.FIND_NAMED_PLACE in action_types:
        calls.extend(_plan_named_place_calls(interpretation))

    if (
        SemanticActionType.DISCOVER_PLACES in action_types
        and _needs_destination_lookup(interpretation)
    ):
        calls.extend(_plan_destination_forward_calls(interpretation))

    if (
        interpretation.primary_intent in _RAG_INTENTS
        or action_types.intersection(_RAG_ACTIONS)
    ):
        calls.append(
            PlannedToolCall(
                SEARCH_TRAVEL_KNOWLEDGE_TOOL_NAME,
                {"query": interpretation.normalized_query},
                destination=_primary_destination(interpretation),
                evidence_kind="knowledge",
            )
        )

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


def _needs_destination_lookup(
    interpretation: SemanticInterpretation,
) -> bool:
    return (
        interpretation.location.longitude is None
        and interpretation.location.latitude is None
        and bool(
            interpretation.location.near
            or interpretation.entities.destinations
        )
    )


def _plan_destination_forward_calls(
    interpretation: SemanticInterpretation,
) -> list[PlannedToolCall]:
    destinations = interpretation.entities.destinations
    if not destinations and interpretation.location.near:
        destinations = [interpretation.location.near]
    return [
        PlannedToolCall(
            MAPBOX_FORWARD_SEARCH_TOOL_NAME,
            {
                "q": destination,
                "language": "vi",
                "limit": ENRICHMENT_FORWARD_RESULT_LIMIT,
                "types": "city,place",
                "rank_strategy": DEFAULT_MAPBOX_RANK_STRATEGY,
                "auto_complete": False,
            },
            destination=destination,
            evidence_kind="location",
        )
        for destination in destinations[:MAX_ENRICHMENT_DESTINATIONS]
    ]


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
            destination=_primary_destination(interpretation) or query,
            evidence_kind="location",
        )
        for query in queries
    ]


def _plan_category_calls(
    interpretation: SemanticInterpretation,
    *,
    max_categories: int,
) -> list[PlannedToolCall]:
    categories = ENRICHMENT_CORE_CATEGORIES[:max_categories]
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
            category_id=category,
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
        destination=_primary_destination(interpretation),
        evidence_kind="location",
    )


def _needs_broad_enrichment(
    interpretation: SemanticInterpretation,
    action_types: set[SemanticActionType],
) -> bool:
    if not interpretation.entities.destinations:
        return False
    if interpretation.primary_intent in _BROAD_ENRICHMENT_INTENTS:
        return True
    return (
        interpretation.primary_intent == TravelIntent.CONTEXT_FOLLOW_UP
        and bool(action_types.intersection(_BROAD_ENRICHMENT_ACTIONS))
    )


def _plan_broad_enrichment(
    interpretation: SemanticInterpretation,
) -> list[PlannedToolCall]:
    categories = ENRICHMENT_CORE_CATEGORIES

    minimum_rating = (
        interpretation.constraints.minimum_rating
        if interpretation.constraints.minimum_rating is not None
        else DEFAULT_MAPBOX_MINIMUM_RATING
    )
    calls: list[PlannedToolCall] = []
    destinations = interpretation.entities.destinations[
        :MAX_ENRICHMENT_DESTINATIONS
    ]
    calls.extend(_plan_destination_forward_calls(interpretation))
    for destination in destinations:
        calls.append(
            PlannedToolCall(
                SEARCH_TRAVEL_KNOWLEDGE_TOOL_NAME,
                {"query": f"{destination}: {interpretation.normalized_query}"},
                destination=destination,
                evidence_kind="knowledge",
            )
        )
        for category in categories:
            calls.append(
                PlannedToolCall(
                    MAPBOX_CATEGORY_SEARCH_TOOL_NAME,
                    {
                        "category_id": category,
                        "language": "vi",
                        "limit": DEFAULT_MAPBOX_CATEGORY_REQUEST_LIMIT,
                        "minimum_rating": minimum_rating,
                    },
                    destination=destination,
                    evidence_kind="poi",
                    category_id=category,
                )
            )
    return calls


def _primary_destination(
    interpretation: SemanticInterpretation,
) -> str | None:
    if interpretation.location.near:
        return interpretation.location.near
    if interpretation.entities.destinations:
        return interpretation.entities.destinations[0]
    if (
        interpretation.location.longitude is not None
        and interpretation.location.latitude is not None
    ):
        return "Vị trí hiện tại"
    return None


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
    seen: set[
        tuple[str, str | None, str | None, tuple[tuple[str, str], ...]]
    ] = set()
    for call in calls:
        key = (
            call.name,
            call.destination,
            call.category_id,
            tuple(sorted((name, repr(value)) for name, value in call.arguments.items())),
        )
        if key in seen:
            continue
        seen.add(key)
        unique_calls.append(call)
    return tuple(unique_calls)


__all__ = [
    "DEFAULT_MAPBOX_CATEGORY_REQUEST_LIMIT",
    "ENRICHMENT_CORE_CATEGORIES",
    "ENRICHMENT_FORWARD_RESULT_LIMIT",
    "DEFAULT_MAPBOX_MINIMUM_RATING",
    "DEFAULT_MAPBOX_RANK_STRATEGY",
    "DEFAULT_MAPBOX_RESULT_LIMIT",
    "DEFAULT_MAX_CATEGORIES",
    "MAX_ENRICHMENT_DESTINATIONS",
    "PlannedToolCall",
    "plan_tools",
]
