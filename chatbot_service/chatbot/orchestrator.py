"""Application service for the travel chatbot request flow."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any

from django.conf import settings

from chatbot.destination_discovery import DestinationCandidateGenerator
from chatbot.intent_routing.contracts import IntentContext, IntentExecutionResult
from chatbot.intent_routing.execution import (
    ToolInfrastructureError,
    first_result_coordinates,
    raise_if_all_tools_had_system_failures,
)
from chatbot.intent_routing.factory import build_intent_router
from chatbot.intent_routing.router import IntentRouter
from chatbot.itinerary_making import ItineraryCandidateGenerator, ItineraryMakingData
from chatbot.rag.rag_chain import get_chat_model
from chatbot.semantic import (
    ConversationMessage,
    SemanticInterpretation,
    SemanticInterpreter,
    SemanticLocation,
)
from chatbot.tools.mapbox_client import MapboxToolClient
from chatbot.tools.models import ChatPlace, ChatSource, ItineraryData
from chatbot.tools.registry import ToolExecution, ToolRegistry

from .answer_composer import AnswerComposer, NO_TOOL_CONTEXT, SYSTEM_PROMPT
from .response_projector import PlaceDetailsLoader, ResponseProjector


CURRENT_LOCATION_TOOL_NAME = "get_current_location"


@dataclass(frozen=True)
class ChatOrchestratorResult:
    answer: str
    sources: list[ChatSource]
    interpretation: SemanticInterpretation | None = None
    places: list[ChatPlace] = field(default_factory=list)
    client_tool_call: str | None = None
    itinerary: ItineraryMakingData | ItineraryData | None = None
    itinerary_operation: dict[str, Any] | None = None


class ChatOrchestrator:
    """Run classifier, capability gate, router, composer and projector."""

    def __init__(
        self,
        chat_model: Any,
        registry: ToolRegistry,
        *,
        semantic_interpreter: SemanticInterpreter | None = None,
        candidate_generator: DestinationCandidateGenerator | None = None,
        itinerary_candidate_generator: ItineraryCandidateGenerator | None = None,
        place_details_loader: PlaceDetailsLoader | None = None,
        max_tool_calls: int | None = None,
        router: IntentRouter | None = None,
    ) -> None:
        resolved_max_calls = (
            settings.CHATBOT_MAX_TOOL_CALLS
            if max_tool_calls is None
            else max_tool_calls
        )
        if isinstance(resolved_max_calls, bool) or not isinstance(resolved_max_calls, int):
            raise ValueError("max_tool_calls must be an integer")
        if resolved_max_calls <= 0:
            raise ValueError("max_tool_calls must be greater than zero")

        self._semantic_interpreter = semantic_interpreter or SemanticInterpreter(chat_model)
        self._router = router or build_intent_router(
            chat_model,
            registry,
            max_tool_calls=resolved_max_calls,
            candidate_generator=candidate_generator,
            itinerary_candidate_generator=itinerary_candidate_generator,
        )
        self._answer_composer = AnswerComposer(chat_model)
        self._response_projector = ResponseProjector(place_details_loader)

    def answer(
        self,
        question: str,
        *,
        history: Sequence[ConversationMessage] = (),
        current_location: SemanticLocation | None = None,
        active_itinerary_id: str | None = None,
        active_itinerary_version: int | None = None,
    ) -> ChatOrchestratorResult:
        cleaned_question = question.strip()
        if not cleaned_question:
            raise ValueError("question must not be empty")

        interpretation_arguments: dict[str, Any] = {
            "history": history,
            "current_location": current_location,
        }
        if active_itinerary_id is not None:
            interpretation_arguments["active_itinerary_id"] = active_itinerary_id
        interpretation = self._semantic_interpreter.interpret(
            cleaned_question,
            **interpretation_arguments,
        )
        if (
            current_location is None
            and (
                interpretation.location.use_current_location
                or "current_location" in interpretation.missing_information
            )
        ):
            return ChatOrchestratorResult(
                answer="",
                sources=[],
                interpretation=interpretation,
                client_tool_call=CURRENT_LOCATION_TOOL_NAME,
            )

        context = IntentContext(
            question=cleaned_question,
            history=tuple(history),
            interpretation=interpretation,
            current_location=current_location,
            active_itinerary_id=active_itinerary_id,
            active_itinerary_version=active_itinerary_version,
        )
        started_at = perf_counter()
        execution_result = self._router.dispatch(context)
        duration_ms = round((perf_counter() - started_at) * 1000, 2)
        self._log_routing(interpretation, execution_result, duration_ms)
        raise_if_all_tools_had_system_failures(execution_result.executions)

        answer = self._answer_composer.compose(
            cleaned_question,
            history=history,
            interpretation=interpretation,
            execution_result=execution_result,
            sensitive_location=current_location,
        )
        sources = ResponseProjector.collect_unique_sources(execution_result.executions)
        places = self._response_projector.project_places(
            answer,
            execution_result.executions,
            execution_result.destination_evidence,
        )
        return ChatOrchestratorResult(
            answer=answer,
            sources=sources,
            interpretation=interpretation,
            places=places,
            itinerary=execution_result.itinerary,
            itinerary_operation=execution_result.itinerary_operation,
        )

    def _log_routing(
        self,
        interpretation: SemanticInterpretation,
        result: IntentExecutionResult,
        duration_ms: float,
    ) -> None:
        import logging

        logging.getLogger(__name__).info(
            "intent routed",
            extra={
                "primary_intent": interpretation.primary_intent.value,
                "semantic_status": interpretation.status.value,
                "handler_class": type(
                    self._router.handlers[interpretation.primary_intent]
                ).__name__,
                "handler_tool_names": [call.name for call in result.planned_calls],
                "tool_count": len(result.planned_calls),
                "handler_duration_ms": duration_ms,
                "failure_category": (
                    "success"
                    if any(execution.success for execution in result.executions)
                    or not result.executions
                    else "tool_failure"
                ),
            },
        )

    # Compatibility aliases keep the old unit-level helpers available while
    # their implementation lives in dedicated modules.
    _first_result_coordinates = staticmethod(first_result_coordinates)
    _ordinary_evidence_content = staticmethod(AnswerComposer.ordinary_evidence_content)
    _collect_answer_places = staticmethod(ResponseProjector.collect_answer_places)
    _collect_unique_sources = staticmethod(ResponseProjector.collect_unique_sources)
    _invoke_ai_message = staticmethod(AnswerComposer.invoke_ai_message)
    _print_model_request = staticmethod(AnswerComposer.print_model_request)
    _print_model_response = staticmethod(AnswerComposer.print_model_response)
    _print_terminal = staticmethod(AnswerComposer.print_terminal)
    _normalized_response_text = staticmethod(AnswerComposer.normalized_response_text)

    def _enrich_answer_places(self, places: list[ChatPlace]) -> list[ChatPlace]:
        return self._response_projector.enrich_places(places)

    @staticmethod
    def _raise_if_all_tools_had_system_failures(
        executions: Sequence[ToolExecution],
    ) -> None:
        raise_if_all_tools_had_system_failures(executions)


def orchestrate_chat(
    question: str,
    *,
    history: Sequence[ConversationMessage] = (),
    current_location: SemanticLocation | None = None,
    active_itinerary_id: str | None = None,
    active_itinerary_version: int | None = None,
    chat_model: Any | None = None,
    registry: ToolRegistry | None = None,
    semantic_interpreter: SemanticInterpreter | None = None,
    candidate_generator: DestinationCandidateGenerator | None = None,
    itinerary_candidate_generator: ItineraryCandidateGenerator | None = None,
    max_tool_calls: int | None = None,
    router: IntentRouter | None = None,
    place_details_loader: PlaceDetailsLoader | None = None,
) -> ChatOrchestratorResult:
    """Run one stateless request and close owned HTTP resources."""
    active_model = chat_model or get_chat_model(thinking_level="medium")
    active_interpreter = semantic_interpreter
    active_candidate_generator = candidate_generator
    active_itinerary_candidate_generator = itinerary_candidate_generator

    if chat_model is None and (
        active_interpreter is None or active_candidate_generator is None
    ):
        planning_model = get_chat_model(thinking_level="low")
        active_interpreter = active_interpreter or SemanticInterpreter(planning_model)
        active_candidate_generator = (
            active_candidate_generator or DestinationCandidateGenerator(planning_model)
        )

    if registry is not None:
        orchestrator_options: dict[str, Any] = {}
        if router is not None:
            orchestrator_options["router"] = router
        if place_details_loader is not None:
            orchestrator_options["place_details_loader"] = place_details_loader
        return ChatOrchestrator(
            active_model,
            registry,
            semantic_interpreter=active_interpreter,
            candidate_generator=active_candidate_generator,
            itinerary_candidate_generator=active_itinerary_candidate_generator,
            max_tool_calls=max_tool_calls,
            **orchestrator_options,
        ).answer(
            question,
            history=history,
            current_location=current_location,
            active_itinerary_id=active_itinerary_id,
            active_itinerary_version=active_itinerary_version,
        )

    with MapboxToolClient() as mapbox_client:
        active_registry = ToolRegistry(mapbox_client)
        return ChatOrchestrator(
            active_model,
            active_registry,
            semantic_interpreter=active_interpreter,
            candidate_generator=active_candidate_generator,
            itinerary_candidate_generator=active_itinerary_candidate_generator,
            place_details_loader=(
                place_details_loader or mapbox_client.retrieve_place_details
            ),
            max_tool_calls=max_tool_calls,
            **({"router": router} if router is not None else {}),
        ).answer(
            question,
            history=history,
            current_location=current_location,
            active_itinerary_id=active_itinerary_id,
            active_itinerary_version=active_itinerary_version,
        )


__all__ = [
    "ChatOrchestrator",
    "ChatOrchestratorResult",
    "CURRENT_LOCATION_TOOL_NAME",
    "NO_TOOL_CONTEXT",
    "SYSTEM_PROMPT",
    "ToolInfrastructureError",
    "orchestrate_chat",
]
