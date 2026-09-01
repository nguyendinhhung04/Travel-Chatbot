"""Compatibility contracts for planned tool calls.

Runtime planning lives in ``chatbot.intent_routing.planning`` and is owned by
the concrete intent handlers. ``plan_tools`` remains as a small compatibility
facade for existing callers while they migrate to the router.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from chatbot.intent import TravelIntent
from chatbot.semantic import (
    InterpretationStatus,
    SemanticActionType,
    SemanticInterpretation,
)


DEFAULT_MAPBOX_RESULT_LIMIT = 5
DESTINATION_FORWARD_RESULT_LIMIT = 3
DEFAULT_MAPBOX_CATEGORY_REQUEST_LIMIT = 10
DEFAULT_MAPBOX_MINIMUM_RATING = 0.0
DEFAULT_MAPBOX_RANK_STRATEGY = "relevance"
DEFAULT_MAX_CATEGORIES = 3


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
    """Deprecated compatibility planner for callers outside the application flow.

    Runtime requests are planned by the concrete handler selected by
    ``IntentRouter``. This function remains temporarily to preserve the public
    helper used by existing tests and integrations.
    """
    from chatbot.intent_routing.planning import (
        deduplicate_calls,
        forward_search_target,
        needs_destination_lookup,
        plan_category_search,
        plan_destination_lookup,
        plan_named_place_search,
        plan_rag_search,
        plan_reverse_lookup,
    )

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
        (
            SemanticActionType.DISCOVER_PLACES in action_types
            or interpretation.primary_intent == TravelIntent.ITINERARY_MAKING
        )
        and needs_destination_lookup(interpretation)
        and interpretation.primary_intent != TravelIntent.DESTINATION_DISCOVERY
    ):
        destination_types = (
            "city,place"
            if interpretation.primary_intent
            in {TravelIntent.DESTINATION_DISCOVERY, TravelIntent.ITINERARY_MAKING}
            else "poi,address,city,place"
        )
        destination_call = plan_destination_lookup(
            interpretation,
            types=destination_types,
            limit=DESTINATION_FORWARD_RESULT_LIMIT,
        )
        if destination_call is not None:
            calls.append(destination_call)

    rag_intents = {
        TravelIntent.DESTINATION_DISCOVERY,
        TravelIntent.PLACE_DETAILS,
        TravelIntent.TRAVEL_QA,
        TravelIntent.ITINERARY_MAKING,
        TravelIntent.ITINERARY_ADVICE,
        TravelIntent.TRANSPORTATION_QA,
        TravelIntent.BUDGET_QA,
    }
    rag_actions = {
        SemanticActionType.ANSWER_TRAVEL_QUESTION,
        SemanticActionType.PROVIDE_ITINERARY_ADVICE,
        SemanticActionType.PROVIDE_TRANSPORTATION_ADVICE,
        SemanticActionType.PROVIDE_BUDGET_ADVICE,
    }
    if (
        interpretation.primary_intent in rag_intents
        or action_types.intersection(rag_actions)
    ):
        calls.append(plan_rag_search(interpretation))

    # A place-details question can arrive with only the generic answer action.
    # The named destination is still an explicit Mapbox lookup target, so do
    # not let a missing LLM action silently turn it into RAG-only answering.
    if (
        interpretation.primary_intent == TravelIntent.PLACE_DETAILS
        and SemanticActionType.FIND_NAMED_PLACE not in action_types
        and needs_destination_lookup(interpretation)
    ):
        target = forward_search_target(interpretation)
        target_types = (
            target.value
            if target.value in {"country", "city", "address", "place"}
            else "city,place"
        )
        destination_call = plan_destination_lookup(
            interpretation,
            types=target_types,
            limit=DEFAULT_MAPBOX_RESULT_LIMIT,
        )
        if destination_call is not None:
            calls.append(destination_call)

    if (
        interpretation.primary_intent == TravelIntent.DESTINATION_DISCOVERY
        and SemanticActionType.DISCOVER_PLACES in action_types
        and needs_destination_lookup(interpretation)
    ):
        destination_call = plan_destination_lookup(
            interpretation,
            types="city,place",
            limit=DESTINATION_FORWARD_RESULT_LIMIT,
        )
        if destination_call is not None:
            calls.append(destination_call)

    if SemanticActionType.FIND_NAMED_PLACE in action_types:
        calls.extend(plan_named_place_search(interpretation))

    if SemanticActionType.DISCOVER_PLACES in action_types:
        calls.extend(
            plan_category_search(
                interpretation,
                max_categories=max_categories,
            )
        )

    if SemanticActionType.REVERSE_GEOCODE in action_types:
        reverse_call = plan_reverse_lookup(interpretation)
        if reverse_call is not None:
            calls.append(reverse_call)

    return deduplicate_calls(calls)


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
