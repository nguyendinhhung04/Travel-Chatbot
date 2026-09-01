from chatbot.intent import TravelIntent
from chatbot.response_policy import RAG_FIRST_ADVICE_POLICY

from ..contracts import IntentContext, IntentExecutionResult
from ..planning import plan_place_search_calls, plan_rag_search
from .base import BaseIntentHandler


class ItineraryAdviceHandler(BaseIntentHandler):
    intent = TravelIntent.ITINERARY_ADVICE
    response_policy = RAG_FIRST_ADVICE_POLICY

    def handle(self, context: IntentContext) -> IntentExecutionResult:
        if self.should_skip_tools(context):
            return IntentExecutionResult()
        calls = plan_place_search_calls(context.interpretation)
        rag_call = plan_rag_search(context.interpretation)
        if calls and calls[0].evidence_kind == "destination_location":
            calls = (calls[0], rag_call, *calls[1:])
        else:
            calls = (rag_call, *calls)
        return self.execute_calls(
            context,
            calls,
            response_policy=self.response_policy,
        )


__all__ = ["ItineraryAdviceHandler"]
