from chatbot.intent import TravelIntent
from chatbot.semantic import SemanticActionType

from ..contracts import IntentContext, IntentExecutionResult
from ..planning import plan_place_search_calls, plan_rag_search
from .base import BaseIntentHandler


class ContextFollowUpHandler(BaseIntentHandler):
    intent = TravelIntent.CONTEXT_FOLLOW_UP

    def handle(self, context: IntentContext) -> IntentExecutionResult:
        if self.should_skip_tools(context):
            return IntentExecutionResult()
        actions = {action.type for action in context.interpretation.actions}
        calls = []
        if actions.intersection({
            SemanticActionType.ANSWER_TRAVEL_QUESTION,
            SemanticActionType.PROVIDE_ITINERARY_ADVICE,
            SemanticActionType.PROVIDE_TRANSPORTATION_ADVICE,
            SemanticActionType.PROVIDE_BUDGET_ADVICE,
        }):
            calls.append(plan_rag_search(context.interpretation))
        calls.extend(
            plan_place_search_calls(
                context.interpretation,
                include_rag=False,
            )
        )
        return self.execute_calls(context, calls)


__all__ = ["ContextFollowUpHandler"]
