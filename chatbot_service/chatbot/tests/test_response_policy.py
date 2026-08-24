"""Tests for intent-grouped response evidence policies."""

from django.test import SimpleTestCase

from chatbot.intent import TravelIntent
from chatbot.response_policy import (
    DESTINATION_DISCOVERY_POLICY,
    MAPBOX_FIRST_POLICY,
    RAG_FIRST_ADVICE_POLICY,
    response_policy_for,
)


class ResponsePolicyTests(SimpleTestCase):
    def test_destination_discovery_uses_rag_model_then_mapbox(self):
        policy = response_policy_for(TravelIntent.DESTINATION_DISCOVERY)

        self.assertEqual(policy, DESTINATION_DISCOVERY_POLICY)
        self.assertIn("Knowledge Base", policy)
        self.assertIn("kiến thức ổn định", policy)
        self.assertIn("Mapbox Category Search chỉ để bổ sung", policy)
        self.assertIn("có mapboxId", policy)
        self.assertIn("một danh sách thống nhất", policy)
        self.assertIn("Điểm nổi bật", policy)

    def test_place_search_and_details_use_mapbox_first(self):
        for intent in (TravelIntent.PLACE_SEARCH, TravelIntent.PLACE_DETAILS):
            with self.subTest(intent=intent):
                self.assertEqual(response_policy_for(intent), MAPBOX_FIRST_POLICY)

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
