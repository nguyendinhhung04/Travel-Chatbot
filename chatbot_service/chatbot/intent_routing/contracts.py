"""Small contracts shared by the intent router and its handlers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from chatbot.intent import TravelIntent
from chatbot.itinerary_making import ItineraryMakingData
from chatbot.semantic import ConversationMessage, SemanticInterpretation, SemanticLocation
from chatbot.tool_planner import PlannedToolCall
from chatbot.tools.models import ItineraryData
from chatbot.tools.registry import ToolExecution


@dataclass(frozen=True)
class IntentContext:
    """Immutable request data passed to exactly one intent handler."""

    question: str
    history: tuple[ConversationMessage, ...]
    interpretation: SemanticInterpretation
    current_location: SemanticLocation | None = None
    active_itinerary_id: str | None = None
    active_itinerary_version: int | None = None


@dataclass(frozen=True)
class IntentExecutionResult:
    """Normalized result returned by every concrete handler."""

    planned_calls: tuple[PlannedToolCall, ...] = ()
    executions: tuple[ToolExecution, ...] = ()
    response_policy: str | None = None
    destination_evidence: dict[str, Any] | None = None
    itinerary_evidence: dict[str, Any] | None = None
    itinerary: ItineraryMakingData | ItineraryData | None = None
    itinerary_operation: dict[str, Any] | None = None


class IntentHandler(Protocol):
    intent: TravelIntent

    def handle(self, context: IntentContext) -> IntentExecutionResult:
        ...


__all__ = ["IntentContext", "IntentExecutionResult", "IntentHandler"]
