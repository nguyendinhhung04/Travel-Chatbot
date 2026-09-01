from chatbot.intent import TravelIntent
from chatbot.itinerary_management import ItineraryManagementPipeline
from chatbot.response_policy import ITINERARY_MANAGEMENT_POLICY

from ..contracts import IntentContext, IntentExecutionResult
from .base import BaseIntentHandler


class ItineraryManagementHandler(BaseIntentHandler):
    intent = TravelIntent.ITINERARY_MANAGEMENT

    def handle(self, context: IntentContext) -> IntentExecutionResult:
        if self.should_skip_tools(context):
            return IntentExecutionResult()
        run = ItineraryManagementPipeline(
            self._registry,
            max_tool_calls=self._max_tool_calls,
        ).execute(
            interpretation=context.interpretation,
            active_itinerary_id=context.active_itinerary_id,
            active_itinerary_version=context.active_itinerary_version,
        )
        operation = {
            "type": run.operation,
            "success": run.itinerary is not None,
        }
        if run.itinerary is None:
            operation["errorCode"] = run.evidence.get("errorCode")
        return IntentExecutionResult(
            planned_calls=tuple(run.calls),
            executions=tuple(run.executions),
            response_policy=ITINERARY_MANAGEMENT_POLICY,
            itinerary_evidence=run.evidence,
            itinerary=run.itinerary,
            itinerary_operation=operation,
        )


__all__ = ["ItineraryManagementHandler"]
