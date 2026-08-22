"""Tests for structured semantic interpretation."""

import json

from django.test import SimpleTestCase
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import ValidationError

from chatbot.intent import TravelIntent
from chatbot.semantic import (
    MAX_HISTORY_MESSAGES,
    SEMANTIC_SYSTEM_PROMPT,
    ConversationMessage,
    InterpretationStatus,
    SemanticAction,
    SemanticActionType,
    SemanticInterpretation,
    SemanticInterpreter,
    SemanticLocation,
    SearchTargetType,
    TravelDomain,
    interpret_question,
)


class SemanticModelTests(SimpleTestCase):
    def test_valid_interpretation_is_strict_and_typed(self):
        interpretation = build_interpretation()

        self.assertEqual(interpretation.primary_intent, TravelIntent.PLACE_SEARCH)
        self.assertEqual(interpretation.travel_domains, [TravelDomain.FOOD])
        self.assertEqual(
            interpretation.actions[0].type,
            SemanticActionType.DISCOVER_PLACES,
        )

        named_target = SemanticInterpretation.model_validate(
            {
                **interpretation.model_dump(mode="json"),
                "entities": {"search_target": "city"},
                "constraints": {"rank_strategy": "distance"},
            }
        )
        self.assertEqual(named_target.entities.search_target, SearchTargetType.CITY)
        self.assertEqual(named_target.constraints.rank_strategy, "distance")

        with self.assertRaises(ValidationError):
            SemanticInterpretation.model_validate(
                {
                    **interpretation.model_dump(mode="json"),
                    "tool_name": "mapbox_category_search",
                }
            )

    def test_location_requires_a_complete_valid_coordinate_pair(self):
        SemanticLocation(longitude=108.2, latitude=16.05, radius_km=1)

        for values in (
            {"longitude": 108.2},
            {"latitude": 16.05},
            {"longitude": 181, "latitude": 16.05},
            {"longitude": 108.2, "latitude": 91},
            {"longitude": 108.2, "latitude": 16.05, "radius_km": 11},
        ):
            with self.subTest(values=values):
                with self.assertRaises(ValidationError):
                    SemanticLocation.model_validate(values)

    def test_clarification_and_unsupported_status_require_matching_actions(self):
        base = build_interpretation().model_dump(mode="json")
        invalid_values = (
            {
                **base,
                "status": "needs_clarification",
                "missing_information": [],
            },
            {
                **base,
                "status": "needs_clarification",
                "missing_information": ["current_location"],
            },
            {
                **base,
                "status": "unsupported",
            },
        )

        for values in invalid_values:
            with self.subTest(status=values["status"]):
                with self.assertRaises(ValidationError):
                    SemanticInterpretation.model_validate(values)

        clarification = SemanticInterpretation.model_validate(
            {
                **base,
                "status": "needs_clarification",
                "missing_information": ["current_location"],
                "actions": [{"type": "request_clarification"}],
            }
        )
        unsupported = SemanticInterpretation.model_validate(
            {
                **base,
                "primary_intent": "unsupported_capability",
                "status": "unsupported",
                "actions": [{"type": "report_unsupported"}],
            }
        )

        self.assertEqual(
            clarification.status,
            InterpretationStatus.NEEDS_CLARIFICATION,
        )
        self.assertEqual(unsupported.status, InterpretationStatus.UNSUPPORTED)


class SemanticInterpreterTests(SimpleTestCase):
    def test_interpreter_uses_json_schema_and_serializes_history_and_location(self):
        response = build_interpretation().model_dump(mode="json")
        model = StubChatModel(response)
        history = [
            ConversationMessage(role="user", content="Tìm cafe gần Mỹ Khê"),
            ConversationMessage(role="assistant", content="Có ba quán phù hợp."),
        ]
        location = SemanticLocation(longitude=108.2, latitude=16.05)

        result = SemanticInterpreter(model).interpret(
            "  Quán thứ hai trông ổn đấy  ",
            history=history,
            current_location=location,
        )

        self.assertIsInstance(result, SemanticInterpretation)
        self.assertIs(model.schema, SemanticInterpretation)
        self.assertEqual(model.method, "json_schema")
        self.assertEqual(len(model.structured.invocations), 1)

        messages = model.structured.invocations[0]
        self.assertIsInstance(messages[0], SystemMessage)
        self.assertIsInstance(messages[1], HumanMessage)
        payload = json.loads(messages[1].content)
        self.assertEqual(payload["question"], "Quán thứ hai trông ổn đấy")
        self.assertEqual(payload["history"][0]["role"], "user")
        self.assertEqual(payload["current_location"]["longitude"], 108.2)

    def test_interpreter_rejects_empty_questions_and_excessive_history(self):
        model = StubChatModel(build_interpretation())
        interpreter = SemanticInterpreter(model)

        with self.assertRaisesRegex(ValueError, "must not be empty"):
            interpreter.interpret("   ")

        history = [
            ConversationMessage(role="user", content=f"Message {index}")
            for index in range(MAX_HISTORY_MESSAGES + 1)
        ]
        with self.assertRaisesRegex(ValueError, "at most"):
            interpreter.interpret("Tìm cafe", history=history)

    def test_helper_uses_injected_model_without_calling_live_gemini(self):
        model = StubChatModel(build_interpretation())

        result = interpret_question("Tìm cafe", chat_model=model)

        self.assertEqual(result.primary_intent, TravelIntent.PLACE_SEARCH)
        self.assertEqual(len(model.structured.invocations), 1)

    def test_prompt_keeps_semantic_and_execution_boundaries_explicit(self):
        self.assertIn("đúng một primary_intent", SEMANTIC_SYSTEM_PROMPT)
        self.assertIn("Không tạo tên tool", SEMANTIC_SYSTEM_PROMPT)
        self.assertIn("Mapbox canonicalId", SEMANTIC_SYSTEM_PROMPT)
        self.assertIn("không lưu và không tính route", SEMANTIC_SYSTEM_PROMPT)
        self.assertIn("giao thông thời gian thực", SEMANTIC_SYSTEM_PROMPT)
        self.assertIn("needs_clarification", SEMANTIC_SYSTEM_PROMPT)
        self.assertIn("entities.search_target", SEMANTIC_SYSTEM_PROMPT)
        self.assertIn("constraints.rank_strategy=distance", SEMANTIC_SYSTEM_PROMPT)


def build_interpretation() -> SemanticInterpretation:
    return SemanticInterpretation(
        primary_intent=TravelIntent.PLACE_SEARCH,
        normalized_query="Tìm quán cafe gần Mỹ Khê",
        travel_domains=[TravelDomain.FOOD],
        actions=[SemanticAction(type=SemanticActionType.DISCOVER_PLACES)],
        status=InterpretationStatus.SUPPORTED,
    )


class StubStructuredModel:
    def __init__(self, response):
        self.response = response
        self.invocations = []

    def invoke(self, messages):
        self.invocations.append(list(messages))
        return self.response


class StubChatModel:
    def __init__(self, response):
        self.schema = None
        self.method = None
        self.structured = StubStructuredModel(response)

    def with_structured_output(self, schema, method):
        self.schema = schema
        self.method = method
        return self.structured
