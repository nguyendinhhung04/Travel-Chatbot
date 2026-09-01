"""Tests for structured semantic interpretation."""

import json
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch

from django.test import SimpleTestCase
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.exceptions import OutputParserException
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
    SemanticItineraryContext,
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

    def test_missing_client_location_can_keep_the_requested_business_action(self):
        interpretation = SemanticInterpretation.model_validate(
            {
                **build_interpretation().model_dump(mode="json"),
                "location": {"use_current_location": True},
                "missing_information": ["current_location"],
                "status": "needs_clarification",
            }
        )

        self.assertEqual(
            interpretation.actions[0].type,
            SemanticActionType.DISCOVER_PLACES,
        )
        self.assertTrue(interpretation.location.use_current_location)

    def test_itinerary_making_requires_and_owns_make_itinerary_action(self):
        base = build_interpretation().model_dump(mode="json")

        valid = SemanticInterpretation.model_validate(
            {
                **base,
                "primary_intent": "itinerary_making",
                "actions": [
                    {"type": "discover_places"},
                    {"type": "make_itinerary"},
                ],
            }
        )

        self.assertEqual(valid.primary_intent, TravelIntent.ITINERARY_MAKING)
        self.assertEqual(
            [action.type for action in valid.actions],
            [
                SemanticActionType.DISCOVER_PLACES,
                SemanticActionType.MAKE_ITINERARY,
            ],
        )

        invalid_values = (
            {
                **base,
                "primary_intent": "itinerary_making",
                "actions": [{"type": "discover_places"}],
            },
            {
                **base,
                "primary_intent": "place_search",
                "actions": [{"type": "make_itinerary"}],
            },
            {
                **base,
                "primary_intent": "travel_qa",
                "actions": [{"type": "make_itinerary"}],
            },
        )
        for values in invalid_values:
            with self.subTest(intent=values["primary_intent"]):
                with self.assertRaises(ValidationError):
                    SemanticInterpretation.model_validate(values)

    def test_incomplete_itinerary_making_can_request_clarification(self):
        interpretation = SemanticInterpretation.model_validate(
            {
                **build_interpretation().model_dump(mode="json"),
                "primary_intent": "itinerary_making",
                "actions": [{"type": "request_clarification"}],
                "missing_information": ["destination"],
                "status": "needs_clarification",
            }
        )

        self.assertEqual(
            interpretation.primary_intent,
            TravelIntent.ITINERARY_MAKING,
        )
        self.assertEqual(
            interpretation.actions[0].type,
            SemanticActionType.REQUEST_CLARIFICATION,
        )

    def test_itinerary_management_actions_require_management_intent(self):
        base = build_interpretation().model_dump(mode="json")
        interpretation = SemanticInterpretation.model_validate(
            {
                **base,
                "primary_intent": "itinerary_management",
                "entities": {
                    "places": ["Công viên Yên Sở"],
                    "search_target": "poi",
                },
                "actions": [
                    {"type": "find_named_place"},
                    {"type": "add_itinerary_stop"},
                ],
            }
        )

        self.assertEqual(
            interpretation.primary_intent,
            TravelIntent.ITINERARY_MANAGEMENT,
        )
        self.assertEqual(
            interpretation.actions[-1].type,
            SemanticActionType.ADD_ITINERARY_STOP,
        )
        self.assertEqual(
            interpretation.itinerary_context,
            SemanticItineraryContext(),
        )

        for invalid_intent in ("context_follow_up", "itinerary_making"):
            with self.subTest(intent=invalid_intent):
                with self.assertRaises(ValidationError):
                    SemanticInterpretation.model_validate(
                        {
                            **base,
                            "primary_intent": invalid_intent,
                            "actions": [{"type": "add_itinerary_stop"}],
                        }
                    )


class SemanticInterpreterTests(SimpleTestCase):
    def test_interpreter_logs_validated_response_and_redacts_current_location(self):
        response = build_interpretation().model_copy(
            update={
                "location": SemanticLocation(
                    use_current_location=True,
                    longitude=108.2,
                    latitude=16.05,
                )
            }
        )
        terminal_output = StringIO()

        with redirect_stdout(terminal_output):
            SemanticInterpreter(StubChatModel(response)).interpret(
                "Tìm quán cafe gần tôi",
                current_location=SemanticLocation(
                    longitude=108.2,
                    latitude=16.05,
                ),
            )

        output = terminal_output.getvalue()
        self.assertIn("Semantic Gemini response (validated):", output)
        self.assertIn('"primary_intent": "place_search"', output)
        self.assertIn('"normalized_query": "Tìm quán cafe gần Mỹ Khê"', output)
        self.assertIn('"type": "discover_places"', output)
        self.assertIn("[location-redacted]", output)
        self.assertNotIn("108.2", output)
        self.assertNotIn("16.05", output)

    def test_current_location_is_hydrated_when_semantics_requests_it(self):
        response = build_interpretation().model_copy(
            update={
                "location": SemanticLocation(use_current_location=True),
            }
        )
        model = StubChatModel(response)

        result = SemanticInterpreter(model).interpret(
            "TĂ¬m quĂ¡n cafe gáº§n tĂ´i",
            current_location=SemanticLocation(longitude=108.2, latitude=16.05),
        )

        self.assertTrue(result.location.use_current_location)
        self.assertEqual(result.location.longitude, 108.2)
        self.assertEqual(result.location.latitude, 16.05)

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

    def test_interpreter_forwards_active_itinerary_id_as_structured_context(self):
        model = StubChatModel(build_interpretation())

        SemanticInterpreter(model).interpret(
            "Thêm Công viên Yên Sở vào lịch trình",
            active_itinerary_id="507f1f77bcf86cd799439011",
        )

        payload = json.loads(model.structured.invocations[0][1].content)
        self.assertEqual(
            payload["active_itinerary_id"],
            "507f1f77bcf86cd799439011",
        )

    def test_interpreter_retries_one_invalid_cross_field_response(self):
        valid = SemanticInterpretation.model_validate(
            {
                **build_interpretation().model_dump(mode="json"),
                "primary_intent": "itinerary_management",
                "normalized_query": "Thêm Công viên Yên Sở vào lịch trình",
                "entities": {
                    "places": ["Công viên Yên Sở"],
                    "search_target": "poi",
                },
                "actions": [
                    {"type": "find_named_place"},
                    {"type": "add_itinerary_stop"},
                ],
            }
        )
        model = StubChatModel(
            [OutputParserException("invalid intent/action pair"), valid]
        )

        result = SemanticInterpreter(model).interpret(
            "Thêm Công viên Yên Sở vào lịch trình"
        )

        self.assertEqual(result.primary_intent, TravelIntent.ITINERARY_MANAGEMENT)
        self.assertEqual(len(model.structured.invocations), 2)
        self.assertIn(
            "itinerary_management",
            model.structured.invocations[1][-1].content,
        )

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

    @patch("chatbot.semantic.get_chat_model")
    def test_helper_uses_low_thinking_by_default(self, get_chat_model_mock):
        model = StubChatModel(build_interpretation())
        get_chat_model_mock.return_value = model

        interpret_question("Tìm cafe")

        get_chat_model_mock.assert_called_once_with(thinking_level="low")

    def test_prompt_keeps_semantic_and_execution_boundaries_explicit(self):
        self.assertIn("Chọn đúng một primary_intent", SEMANTIC_SYSTEM_PROMPT)
        self.assertIn(
            "Phân biệt địa điểm cần tìm với địa điểm làm mốc",
            SEMANTIC_SYSTEM_PROMPT,
        )
        self.assertIn(
            'Ví dụ "quán cafe gần PTIT": action=discover_places',
            SEMANTIC_SYSTEM_PROMPT,
        )
        self.assertIn(
            'Ví dụ "tìm Highlands Coffee Nguyễn Trãi": action=find_named_place',
            SEMANTIC_SYSTEM_PROMPT,
        )
        self.assertIn("không tạo tên tool", SEMANTIC_SYSTEM_PROMPT)
        self.assertIn("canonicalId", SEMANTIC_SYSTEM_PROMPT)
        self.assertIn("Dùng itinerary_making", SEMANTIC_SYSTEM_PROMPT)
        self.assertIn("Dùng itinerary_advice", SEMANTIC_SYSTEM_PROMPT)
        self.assertIn("Dùng itinerary_management", SEMANTIC_SYSTEM_PROMPT)
        self.assertIn("Intent nghiệp vụ này ưu tiên hơn context_follow_up", SEMANTIC_SYSTEM_PROMPT)
        self.assertIn("Công viên Yên Sở", SEMANTIC_SYSTEM_PROMPT)
        self.assertIn('"các địa điểm chơi tại Hà Nội"', SEMANTIC_SYSTEM_PROMPT)
        self.assertIn("phải itinerary_making", SEMANTIC_SYSTEM_PROMPT)
        self.assertIn("không được thêm make_itinerary", SEMANTIC_SYSTEM_PROMPT)
        self.assertIn("không tự đoán điểm đến", SEMANTIC_SYSTEM_PROMPT)
        self.assertIn("semantic không tự tạo geometry", SEMANTIC_SYSTEM_PROMPT)
        self.assertIn("giao thông thời gian thực", SEMANTIC_SYSTEM_PROMPT)
        self.assertIn("needs_clarification", SEMANTIC_SYSTEM_PROMPT)
        self.assertIn("entities.search_target", SEMANTIC_SYSTEM_PROMPT)
        self.assertIn("location.use_current_location", SEMANTIC_SYSTEM_PROMPT)
        self.assertIn("gần nhất dùng distance", SEMANTIC_SYSTEM_PROMPT)


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
        response = self.response.pop(0) if isinstance(self.response, list) else self.response
        if isinstance(response, Exception):
            raise response
        return response


class StubChatModel:
    def __init__(self, response):
        self.schema = None
        self.method = None
        self.structured = StubStructuredModel(response)

    def with_structured_output(self, schema, method):
        self.schema = schema
        self.method = method
        return self.structured
