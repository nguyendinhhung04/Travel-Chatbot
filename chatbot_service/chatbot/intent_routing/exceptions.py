"""Errors raised while validating the intent handler registry."""

from __future__ import annotations

from chatbot.intent import TravelIntent


class IntentHandlerRegistryError(ValueError):
    """Base error for invalid router wiring."""


class MissingIntentHandlersError(IntentHandlerRegistryError):
    def __init__(self, intents: set[TravelIntent]) -> None:
        self.intents = frozenset(intents)
        names = ", ".join(sorted(intent.value for intent in intents))
        super().__init__(f"Missing intent handlers: {names}")


class DuplicateIntentHandlerError(IntentHandlerRegistryError):
    def __init__(self, intent: TravelIntent) -> None:
        self.intent = intent
        super().__init__(f"Duplicate intent handler registered for: {intent.value}")


__all__ = [
    "DuplicateIntentHandlerError",
    "IntentHandlerRegistryError",
    "MissingIntentHandlersError",
]
