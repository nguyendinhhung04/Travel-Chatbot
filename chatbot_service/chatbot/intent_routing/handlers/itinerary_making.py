from __future__ import annotations

from typing import Any

from chatbot.intent import TravelIntent
from chatbot.itinerary_making import (
    ItineraryCandidateGenerator,
    ItineraryMakingPipeline,
)
from chatbot.response_policy import ITINERARY_MAKING_POLICY

from ..contracts import IntentContext, IntentExecutionResult
from ..planning import plan_discovery_calls
from .base import BaseIntentHandler


class ItineraryMakingHandler(BaseIntentHandler):
    intent = TravelIntent.ITINERARY_MAKING

    def __init__(
        self,
        chat_model: Any,
        registry,
        *,
        max_tool_calls: int,
        candidate_generator: ItineraryCandidateGenerator | None = None,
    ) -> None:
        super().__init__(registry, max_tool_calls=max_tool_calls)
        self._chat_model = chat_model
        self._candidate_generator = candidate_generator

    def handle(self, context: IntentContext) -> IntentExecutionResult:
        if self.should_skip_tools(context):
            return IntentExecutionResult()
        planned = plan_discovery_calls(context.interpretation)
        run = ItineraryMakingPipeline(
            self._chat_model,
            self._registry,
            itinerary_creator=lambda call: self._registry.execute(
                call.name,
                call.arguments,
            ),
            candidate_generator=self._candidate_generator,
            max_tool_calls=self._max_tool_calls,
        ).execute(
            context.question,
            history=context.history,
            interpretation=context.interpretation,
            planned_calls=planned,
            prior_places=context.prior_places,
        )
        return IntentExecutionResult(
            planned_calls=tuple(run.calls),
            executions=tuple(run.executions),
            response_policy=ITINERARY_MAKING_POLICY,
            itinerary_evidence=run.evidence,
            itinerary=run.itinerary,
            itinerary_operation={
                "type": "create_itinerary",
                "success": run.itinerary is not None,
                **(
                    {}
                    if run.itinerary is not None
                    else {"errorCode": run.evidence.get("errorCode")}
                ),
            },
        )


__all__ = ["ItineraryMakingHandler"]
