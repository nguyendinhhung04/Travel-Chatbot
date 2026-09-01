"""Deterministic dispatch from validated semantic intent to one handler."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from types import MappingProxyType

from chatbot.intent import TravelIntent

from .contracts import IntentContext, IntentExecutionResult, IntentHandler
from .exceptions import DuplicateIntentHandlerError, MissingIntentHandlersError


class IntentRouter:
    def __init__(self, handlers: Sequence[IntentHandler]) -> None:
        handler_map: dict[TravelIntent, IntentHandler] = {}
        for handler in handlers:
            intent = handler.intent
            if intent in handler_map:
                raise DuplicateIntentHandlerError(intent)
            handler_map[intent] = handler

        missing = set(TravelIntent) - set(handler_map)
        if missing:
            raise MissingIntentHandlersError(missing)

        self._handlers: Mapping[TravelIntent, IntentHandler] = MappingProxyType(
            dict(handler_map)
        )

    @property
    def handlers(self) -> Mapping[TravelIntent, IntentHandler]:
        return self._handlers

    def dispatch(self, context: IntentContext) -> IntentExecutionResult:
        return self._handlers[context.interpretation.primary_intent].handle(context)


__all__ = ["IntentRouter"]
