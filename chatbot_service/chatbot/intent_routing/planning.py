"""Small semantic-to-tool planning helpers owned by intent handlers."""

from __future__ import annotations

from typing import Any

from chatbot.category_resolver import resolve_mapbox_categories
from chatbot.semantic import (
    SearchTargetType,
    SemanticActionType,
    SemanticInterpretation,
)
from chatbot.tool_planner import (
    DEFAULT_MAPBOX_CATEGORY_REQUEST_LIMIT,
    DEFAULT_MAPBOX_MINIMUM_RATING,
    DEFAULT_MAPBOX_RANK_STRATEGY,
    DEFAULT_MAPBOX_RESULT_LIMIT,
    DEFAULT_MAX_CATEGORIES,
    DESTINATION_FORWARD_RESULT_LIMIT,
    PlannedToolCall,
)
from chatbot.tools.registry import (
    MAPBOX_CATEGORY_SEARCH_TOOL_NAME,
    MAPBOX_FORWARD_SEARCH_TOOL_NAME,
    MAPBOX_REVERSE_LOOKUP_TOOL_NAME,
)
from chatbot.tools.rag_tool import SEARCH_TRAVEL_KNOWLEDGE_TOOL_NAME


_KILOMETERS_PER_DEGREE = 111.32


def primary_destination(interpretation: SemanticInterpretation) -> str | None:
    if interpretation.location.near:
        return interpretation.location.near
    if interpretation.entities.destinations:
        return interpretation.entities.destinations[0]
    return None


def needs_destination_lookup(interpretation: SemanticInterpretation) -> bool:
    return (
        interpretation.location.longitude is None
        and interpretation.location.latitude is None
        and primary_destination(interpretation) is not None
    )


def plan_rag_search(interpretation: SemanticInterpretation) -> PlannedToolCall:
    destination = primary_destination(interpretation)
    arguments: dict[str, Any] = {"query": interpretation.normalized_query}
    if destination is not None:
        arguments["destination"] = destination
    return PlannedToolCall(
        SEARCH_TRAVEL_KNOWLEDGE_TOOL_NAME,
        arguments,
        destination=destination,
        evidence_kind="knowledge",
    )


def plan_destination_lookup(
    interpretation: SemanticInterpretation,
    *,
    types: str = "poi,address,city,place",
    limit: int = DESTINATION_FORWARD_RESULT_LIMIT,
) -> PlannedToolCall | None:
    destination = primary_destination(interpretation)
    if destination is None:
        return None
    return PlannedToolCall(
        MAPBOX_FORWARD_SEARCH_TOOL_NAME,
        {
            "q": destination,
            "language": "vi",
            "limit": limit,
            "types": types,
            "rank_strategy": DEFAULT_MAPBOX_RANK_STRATEGY,
            "auto_complete": False,
        },
        destination=destination,
        evidence_kind="destination_location",
    )


def plan_named_place_search(
    interpretation: SemanticInterpretation,
) -> tuple[PlannedToolCall, ...]:
    queries = interpretation.entities.places or interpretation.entities.destinations
    if not queries:
        return ()

    common_arguments = mapbox_location_arguments(interpretation)
    target = forward_search_target(interpretation)
    common_arguments["types"] = target.value
    constraints = interpretation.constraints
    common_arguments["rank_strategy"] = (
        constraints.rank_strategy or DEFAULT_MAPBOX_RANK_STRATEGY
    )
    if target == SearchTargetType.POI:
        if constraints.open_now is not None:
            common_arguments["open_now"] = constraints.open_now
        common_arguments["minimum_rating"] = (
            constraints.minimum_rating
            if constraints.minimum_rating is not None
            else DEFAULT_MAPBOX_MINIMUM_RATING
        )

    return tuple(
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
    )


def plan_category_search(
    interpretation: SemanticInterpretation,
    *,
    max_categories: int = DEFAULT_MAX_CATEGORIES,
) -> tuple[PlannedToolCall, ...]:
    categories = resolve_mapbox_categories(
        interpretation,
        max_categories=max_categories,
    )
    common_arguments = mapbox_location_arguments(interpretation)
    if needs_destination_lookup(interpretation):
        common_arguments.pop("near", None)
    constraints = interpretation.constraints
    minimum_rating = (
        constraints.minimum_rating
        if constraints.minimum_rating is not None
        else DEFAULT_MAPBOX_MINIMUM_RATING
    )
    return tuple(
        PlannedToolCall(
            MAPBOX_CATEGORY_SEARCH_TOOL_NAME,
            {
                "category_id": category,
                "language": "vi",
                "limit": DEFAULT_MAPBOX_CATEGORY_REQUEST_LIMIT,
                "minimum_rating": minimum_rating,
                **common_arguments,
            },
            destination=primary_destination(interpretation),
            evidence_kind="poi",
        )
        for category in categories
    )


def plan_reverse_lookup(
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


def mapbox_location_arguments(
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


def forward_search_target(
    interpretation: SemanticInterpretation,
) -> SearchTargetType:
    if interpretation.entities.search_target is not None:
        return interpretation.entities.search_target
    if interpretation.entities.places:
        return SearchTargetType.POI
    return SearchTargetType.PLACE


def deduplicate_calls(calls: list[PlannedToolCall]) -> tuple[PlannedToolCall, ...]:
    unique: list[PlannedToolCall] = []
    seen: set[tuple[str, tuple[tuple[str, str], ...]]] = set()
    for call in calls:
        key = (
            call.name,
            tuple(sorted((name, repr(value)) for name, value in call.arguments.items())),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(call)
    return tuple(unique)


def plan_discovery_calls(
    interpretation: SemanticInterpretation,
    *,
    max_categories: int = DEFAULT_MAX_CATEGORIES,
) -> tuple[PlannedToolCall, ...]:
    """Compose the calls needed by destination discovery and itinerary making."""
    calls = [plan_rag_search(interpretation)]
    destination_call = plan_destination_lookup(
        interpretation,
        types="city,place",
        limit=DESTINATION_FORWARD_RESULT_LIMIT,
    )
    if destination_call is not None:
        calls.append(destination_call)
    if SemanticActionType.DISCOVER_PLACES in {
        action.type for action in interpretation.actions
    }:
        calls.extend(plan_category_search(interpretation, max_categories=max_categories))
    return deduplicate_calls(calls)


def plan_place_search_calls(
    interpretation: SemanticInterpretation,
    *,
    include_rag: bool = False,
    max_categories: int = DEFAULT_MAX_CATEGORIES,
) -> tuple[PlannedToolCall, ...]:
    calls: list[PlannedToolCall] = []
    if include_rag:
        calls.append(plan_rag_search(interpretation))
    action_types = {action.type for action in interpretation.actions}
    if SemanticActionType.DISCOVER_PLACES in action_types:
        destination_call = plan_destination_lookup(interpretation)
        if destination_call is not None:
            calls.append(destination_call)
        calls.extend(plan_category_search(interpretation, max_categories=max_categories))
    if SemanticActionType.FIND_NAMED_PLACE in action_types:
        calls.extend(plan_named_place_search(interpretation))
    if SemanticActionType.REVERSE_GEOCODE in action_types:
        reverse_call = plan_reverse_lookup(interpretation)
        if reverse_call is not None:
            calls.append(reverse_call)
    return deduplicate_calls(calls)


__all__ = [
    "deduplicate_calls",
    "forward_search_target",
    "mapbox_location_arguments",
    "needs_destination_lookup",
    "plan_category_search",
    "plan_destination_lookup",
    "plan_discovery_calls",
    "plan_named_place_search",
    "plan_place_search_calls",
    "plan_rag_search",
    "plan_reverse_lookup",
    "primary_destination",
]
