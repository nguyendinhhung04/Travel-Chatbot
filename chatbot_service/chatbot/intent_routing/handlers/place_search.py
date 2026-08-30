from chatbot.intent import TravelIntent
from chatbot.response_policy import MAPBOX_FIRST_POLICY

from ..contracts import IntentContext, IntentExecutionResult
from ..planning import plan_place_search_calls
from .base import BaseIntentHandler


class PlaceSearchHandler(BaseIntentHandler):
    intent = TravelIntent.PLACE_SEARCH

    def handle(self, context: IntentContext) -> IntentExecutionResult:
        if self.should_skip_tools(context):
            return IntentExecutionResult()
        calls = plan_place_search_calls(context.interpretation)
        return self.execute_calls(
            context,
            calls,
            response_policy=MAPBOX_FIRST_POLICY,
        )


__all__ = ["PlaceSearchHandler"]
