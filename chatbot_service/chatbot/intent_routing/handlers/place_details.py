from chatbot.intent import TravelIntent
from chatbot.response_policy import MAPBOX_FIRST_POLICY

from ..contracts import IntentContext, IntentExecutionResult
from ..planning import plan_place_search_calls
from .base import BaseIntentHandler


class PlaceDetailsHandler(BaseIntentHandler):
    intent = TravelIntent.PLACE_DETAILS

    def handle(self, context: IntentContext) -> IntentExecutionResult:
        if self.should_skip_tools(context):
            return IntentExecutionResult()
        calls = plan_place_search_calls(
            context.interpretation,
            include_rag=True,
        )
        # A named destination can arrive with only answer_travel_question. Keep
        # the deterministic city/address lookup fallback from the old planner.
        if (
            not any(call.evidence_kind == "destination_location" for call in calls)
            and not any(call.evidence_kind == "poi" for call in calls)
        ):
            from ..planning import forward_search_target, plan_destination_lookup

            if context.interpretation.entities.destinations:
                target = forward_search_target(context.interpretation)
                target_types = (
                    target.value
                    if target.value in {"country", "city", "address", "place"}
                    else "city,place"
                )
                destination_call = plan_destination_lookup(
                    context.interpretation,
                    types=target_types,
                    limit=5,
                )
                if destination_call is not None:
                    calls = (*calls, destination_call)
        return self.execute_calls(
            context,
            calls,
            response_policy=MAPBOX_FIRST_POLICY,
        )


__all__ = ["PlaceDetailsHandler"]
