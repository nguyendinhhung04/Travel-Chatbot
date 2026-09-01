"""Composition root for the complete intent handler registry."""

from __future__ import annotations

from typing import Any

from chatbot.destination_discovery import DestinationCandidateGenerator
from chatbot.itinerary_making import ItineraryCandidateGenerator
from chatbot.tools.registry import ToolRegistry

from .handlers import (
    BudgetQAHandler,
    ContextFollowUpHandler,
    DestinationDiscoveryHandler,
    GeneralChatHandler,
    ItineraryAdviceHandler,
    ItineraryManagementHandler,
    ItineraryMakingHandler,
    PlaceDetailsHandler,
    PlaceSearchHandler,
    TravelQAHandler,
    TransportationQAHandler,
    UnsupportedCapabilityHandler,
)
from .router import IntentRouter


def build_intent_router(
    chat_model: Any,
    registry: ToolRegistry,
    *,
    max_tool_calls: int,
    candidate_generator: DestinationCandidateGenerator | None = None,
    itinerary_candidate_generator: ItineraryCandidateGenerator | None = None,
) -> IntentRouter:
    common = {"registry": registry, "max_tool_calls": max_tool_calls}
    handlers = [
        DestinationDiscoveryHandler(
            chat_model,
            **common,
            candidate_generator=candidate_generator,
        ),
        PlaceSearchHandler(**common),
        PlaceDetailsHandler(**common),
        TravelQAHandler(**common),
        ItineraryMakingHandler(
            chat_model,
            **common,
            candidate_generator=itinerary_candidate_generator,
        ),
        ItineraryManagementHandler(**common),
        ItineraryAdviceHandler(**common),
        TransportationQAHandler(**common),
        BudgetQAHandler(**common),
        ContextFollowUpHandler(**common),
        GeneralChatHandler(**common),
        UnsupportedCapabilityHandler(**common),
    ]
    return IntentRouter(handlers)


__all__ = ["build_intent_router"]
