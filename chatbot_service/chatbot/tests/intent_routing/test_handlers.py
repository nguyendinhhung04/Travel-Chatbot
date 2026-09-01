from types import SimpleNamespace

from django.test import SimpleTestCase

from chatbot.intent import TravelIntent
from chatbot.intent_routing.contracts import IntentContext
from chatbot.intent_routing.factory import build_intent_router
from chatbot.semantic import InterpretationStatus


class FailingRegistry:
    def execute(self, name, arguments):
        raise AssertionError(f"tool must not run: {name}")


class IntentHandlerTests(SimpleTestCase):
    def test_every_handler_respects_clarification_gate_without_provider_calls(self):
        router = build_intent_router(object(), FailingRegistry(), max_tool_calls=4)

        for intent in TravelIntent:
            with self.subTest(intent=intent):
                interpretation = SimpleNamespace(
                    primary_intent=intent,
                    status=InterpretationStatus.NEEDS_CLARIFICATION,
                )
                context = IntentContext(
                    question="Cần làm rõ",
                    history=(),
                    interpretation=interpretation,
                )

                result = router.dispatch(context)

                self.assertEqual(result.planned_calls, ())
                self.assertEqual(result.executions, ())
