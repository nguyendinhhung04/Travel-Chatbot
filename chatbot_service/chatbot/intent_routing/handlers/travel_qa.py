from chatbot.intent import TravelIntent
from chatbot.response_policy import RAG_FIRST_ADVICE_POLICY

from .base import RagFirstHandler


class TravelQAHandler(RagFirstHandler):
    intent = TravelIntent.TRAVEL_QA
    response_policy = RAG_FIRST_ADVICE_POLICY


__all__ = ["TravelQAHandler"]
