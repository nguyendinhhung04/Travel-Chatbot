"""Tests for intent-grouped response evidence policies."""

from django.test import SimpleTestCase

from chatbot.intent import TravelIntent
from chatbot.response_policy import (
    DESTINATION_DISCOVERY_POLICY,
    ITINERARY_MAKING_POLICY,
    MAPBOX_FIRST_POLICY,
    RAG_FIRST_ADVICE_POLICY,
    response_policy_for,
)


class ResponsePolicyTests(SimpleTestCase):
    def test_itinerary_making_requires_verified_optimized_route(self):
        policy = response_policy_for(TravelIntent.ITINERARY_MAKING)

        self.assertEqual(policy, ITINERARY_MAKING_POLICY)
        self.assertIn("success=true", policy)
        self.assertIn("Không tự tạo điểm dừng", policy)
        self.assertIn("Không tuyên bố lịch trình đã được lưu", policy)

    def test_destination_discovery_uses_rag_model_then_mapbox(self):
        policy = response_policy_for(TravelIntent.DESTINATION_DISCOVERY)

        self.assertEqual(policy, DESTINATION_DISCOVERY_POLICY)
        self.assertIn("Knowledge Base", policy)
        self.assertIn("kiến thức ổn định", policy)
        self.assertIn("additionalMapboxPlaces để bổ sung", policy)
        self.assertIn("Chỉ đề xuất tên có trong hai danh sách", policy)
        self.assertIn("khoảng cách, ETA, rating và popularity", policy)
        self.assertIn("không liệt kê máy móc", policy)
        self.assertIn("không dùng nó để", policy)

    def test_place_search_and_details_use_mapbox_first(self):
        for intent in (TravelIntent.PLACE_SEARCH, TravelIntent.PLACE_DETAILS):
            with self.subTest(intent=intent):
                self.assertEqual(response_policy_for(intent), MAPBOX_FIRST_POLICY)
        self.assertIn("mapbox.success=true", MAPBOX_FIRST_POLICY)
        self.assertIn("mapbox.success=false", MAPBOX_FIRST_POLICY)
        self.assertIn("chưa thể lấy dữ liệu", MAPBOX_FIRST_POLICY)
        self.assertIn("mapbox.destinationLocations", MAPBOX_FIRST_POLICY)
        self.assertIn("mapbox.places", MAPBOX_FIRST_POLICY)
        self.assertIn("Không suy đoán địa điểm thay thế", MAPBOX_FIRST_POLICY)

    def test_advice_intents_use_rag_first(self):
        intents = (
            TravelIntent.TRAVEL_QA,
            TravelIntent.ITINERARY_ADVICE,
            TravelIntent.TRANSPORTATION_QA,
            TravelIntent.BUDGET_QA,
        )

        for intent in intents:
            with self.subTest(intent=intent):
                self.assertEqual(
                    response_policy_for(intent),
                    RAG_FIRST_ADVICE_POLICY,
                )

    def test_chat_follow_up_and_unsupported_add_no_evidence_policy(self):
        intents = (
            TravelIntent.CONTEXT_FOLLOW_UP,
            TravelIntent.GENERAL_CHAT,
            TravelIntent.UNSUPPORTED_CAPABILITY,
        )

        for intent in intents:
            with self.subTest(intent=intent):
                self.assertIsNone(response_policy_for(intent))
