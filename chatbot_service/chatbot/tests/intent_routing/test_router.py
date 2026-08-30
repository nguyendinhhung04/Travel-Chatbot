from types import SimpleNamespace

from django.test import SimpleTestCase

from chatbot.intent import TravelIntent
from chatbot.intent_routing.contracts import IntentContext, IntentExecutionResult
from chatbot.intent_routing.exceptions import (
    DuplicateIntentHandlerError,
    MissingIntentHandlersError,
)
from chatbot.intent_routing.router import IntentRouter


class StubHandler:
    def __init__(self, intent):
        self.intent = intent
        self.calls = []

    def handle(self, context):
        self.calls.append(context)
        return IntentExecutionResult()


class IntentRouterTests(SimpleTestCase):
    def test_exact_coverage_and_dispatch_for_all_intents(self):
        handlers = [StubHandler(intent) for intent in TravelIntent]
        router = IntentRouter(handlers)

        self.assertEqual(set(router.handlers), set(TravelIntent))
        for handler in handlers:
            context = IntentContext(
                question="test",
                history=(),
                interpretation=SimpleNamespace(primary_intent=handler.intent),
            )
            self.assertIsInstance(router.dispatch(context), IntentExecutionResult)
            self.assertEqual(handler.calls, [context])

    def test_missing_handler_fails_fast_with_intent_name(self):
        handlers = [
            StubHandler(intent)
            for intent in TravelIntent
            if intent != TravelIntent.GENERAL_CHAT
        ]

        with self.assertRaises(MissingIntentHandlersError) as raised:
            IntentRouter(handlers)

        self.assertEqual(raised.exception.intents, {TravelIntent.GENERAL_CHAT})
        self.assertIn("general_chat", str(raised.exception))

    def test_duplicate_handler_fails_fast(self):
        handlers = [StubHandler(intent) for intent in TravelIntent]
        handlers.append(StubHandler(TravelIntent.PLACE_SEARCH))

        with self.assertRaises(DuplicateIntentHandlerError) as raised:
            IntentRouter(handlers)

        self.assertEqual(raised.exception.intent, TravelIntent.PLACE_SEARCH)

    def test_handler_mapping_is_immutable(self):
        router = IntentRouter([StubHandler(intent) for intent in TravelIntent])

        with self.assertRaises(TypeError):
            router.handlers[TravelIntent.GENERAL_CHAT] = StubHandler(
                TravelIntent.GENERAL_CHAT
            )
