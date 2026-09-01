"""Intent classification dispatch and per-intent application handlers."""

from .contracts import IntentContext, IntentExecutionResult, IntentHandler
from .exceptions import (
    DuplicateIntentHandlerError,
    IntentHandlerRegistryError,
    MissingIntentHandlersError,
)
from .factory import build_intent_router
from .router import IntentRouter

__all__ = [
    "DuplicateIntentHandlerError",
    "IntentContext",
    "IntentExecutionResult",
    "IntentHandler",
    "IntentHandlerRegistryError",
    "IntentRouter",
    "MissingIntentHandlersError",
    "build_intent_router",
]
