from chatbot.intent import TravelIntent

from ..contracts import IntentContext, IntentExecutionResult
from .base import BaseIntentHandler


class UnsupportedCapabilityHandler(BaseIntentHandler):
    intent = TravelIntent.UNSUPPORTED_CAPABILITY

    def handle(self, context: IntentContext) -> IntentExecutionResult:
        return IntentExecutionResult()


__all__ = ["UnsupportedCapabilityHandler"]
