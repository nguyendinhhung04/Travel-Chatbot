from chatbot.intent import TravelIntent

from ..contracts import IntentContext, IntentExecutionResult
from .base import BaseIntentHandler


class GeneralChatHandler(BaseIntentHandler):
    intent = TravelIntent.GENERAL_CHAT

    def handle(self, context: IntentContext) -> IntentExecutionResult:
        return IntentExecutionResult()


__all__ = ["GeneralChatHandler"]
