from __future__ import annotations

from typing import Any

from chatbot.destination_discovery import (
    DestinationCandidateGenerator,
    DestinationDiscoveryPipeline,
)
from chatbot.intent import TravelIntent
from chatbot.response_policy import DESTINATION_DISCOVERY_POLICY

from ..contracts import IntentContext, IntentExecutionResult
from ..planning import plan_discovery_calls
from .base import BaseIntentHandler


class DestinationDiscoveryHandler(BaseIntentHandler):
    intent = TravelIntent.DESTINATION_DISCOVERY

    def __init__(
        self,
        chat_model: Any,
        registry,
        *,
        max_tool_calls: int,
        candidate_generator: DestinationCandidateGenerator | None = None,
    ) -> None:
        super().__init__(registry, max_tool_calls=max_tool_calls)
        self._chat_model = chat_model
        self._candidate_generator = candidate_generator

    def handle(self, context: IntentContext) -> IntentExecutionResult:
        if self.should_skip_tools(context):
            return IntentExecutionResult()
        planned = plan_discovery_calls(context.interpretation)
        run = DestinationDiscoveryPipeline(
            self._chat_model,
            self._registry,
            max_tool_calls=self._max_tool_calls,
            candidate_generator=self._candidate_generator,
        ).execute(
            context.question,
            history=context.history,
            interpretation=context.interpretation,
            planned_calls=planned,
        )
        return IntentExecutionResult(
            planned_calls=tuple(run.calls),
            executions=tuple(run.executions),
            response_policy=DESTINATION_DISCOVERY_POLICY,
            destination_evidence=run.evidence,
        )


__all__ = ["DestinationDiscoveryHandler"]
