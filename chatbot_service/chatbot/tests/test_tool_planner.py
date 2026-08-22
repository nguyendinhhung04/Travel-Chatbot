"""Tests for deterministic semantic-to-tool planning."""

from django.test import SimpleTestCase

from chatbot.intent import TravelIntent
from chatbot.semantic import (
    InterpretationStatus,
    SemanticAction,
    SemanticActionType,
    SemanticConstraints,
    SemanticEntities,
    SemanticInterpretation,
    SemanticLocation,
    TravelDomain,
)
from chatbot.tool_planner import plan_tools


class ToolPlannerTests(SimpleTestCase):
    def test_travel_qa_uses_only_knowledge_base(self):
        interpretation = build_interpretation(
            intent=TravelIntent.TRAVEL_QA,
            actions=[SemanticActionType.ANSWER_TRAVEL_QUESTION],
        )

        calls = plan_tools(interpretation)

        self.assertEqual(
            [(call.name, call.arguments) for call in calls],
            [
                (
                    "search_travel_knowledge",
                    {"query": "Tháng 9 đi Đà Lạt có ổn không?"},
                )
            ],
        )

    def test_named_place_uses_forward_search_with_semantic_filters(self):
        interpretation = build_interpretation(
            intent=TravelIntent.PLACE_DETAILS,
            actions=[SemanticActionType.FIND_NAMED_PLACE],
            entities=SemanticEntities(
                destinations=["Đà Nẵng"],
                places=["Bà Nà Hills"],
            ),
            location=SemanticLocation(near="Đà Nẵng"),
            constraints=SemanticConstraints(open_now=True, minimum_rating=4),
        )

        calls = plan_tools(interpretation)

        self.assertEqual(
            [call.name for call in calls],
            ["search_travel_knowledge", "mapbox_forward_search"],
        )
        self.assertEqual(
            calls[1].arguments,
            {
                "q": "Bà Nà Hills",
                "language": "vi",
                "limit": 5,
                "near": "Đà Nẵng",
                "open_now": True,
                "minimum_rating": 4.0,
            },
        )

    def test_discovery_resolves_categories_without_category_list_call(self):
        interpretation = build_interpretation(
            intent=TravelIntent.PLACE_SEARCH,
            actions=[SemanticActionType.DISCOVER_PLACES],
            domains=[TravelDomain.FOOD],
            entities=SemanticEntities(
                destinations=["Đà Nẵng"],
                place_types=["quán cafe"],
            ),
        )

        calls = plan_tools(interpretation)

        self.assertEqual(
            [call.name for call in calls],
            [
                "mapbox_category_search",
                "mapbox_category_search",
                "mapbox_category_search",
            ],
        )
        self.assertEqual(
            [call.arguments["category_id"] for call in calls],
            ["cafe", "coffee_shop", "restaurant"],
        )
        self.assertTrue(
            all(call.arguments["near"] == "Đà Nẵng" for call in calls)
        )
        self.assertFalse(
            any(call.name == "mapbox_list_categories" for call in calls)
        )

    def test_current_coordinates_are_forwarded_without_route_arguments(self):
        interpretation = build_interpretation(
            intent=TravelIntent.PLACE_SEARCH,
            actions=[SemanticActionType.DISCOVER_PLACES],
            domains=[TravelDomain.ESSENTIAL],
            location=SemanticLocation(
                longitude=108.2,
                latitude=16.1,
                radius_km=1,
            ),
            entities=SemanticEntities(place_types=["nhà thuốc"]),
        )

        calls = plan_tools(interpretation, max_categories=1)

        self.assertEqual(calls[0].arguments["proximity"], "108.2,16.1")
        self.assertEqual(calls[0].arguments["radius"], 0.008983)
        for unsupported_argument in (
            "route",
            "route_geometry",
            "eta_type",
            "navigation_profile",
            "origin",
        ):
            self.assertNotIn(unsupported_argument, calls[0].arguments)

    def test_reverse_geocode_requires_and_uses_coordinate_pair(self):
        interpretation = build_interpretation(
            intent=TravelIntent.PLACE_DETAILS,
            actions=[SemanticActionType.REVERSE_GEOCODE],
            location=SemanticLocation(longitude=108.2, latitude=16.1),
        )

        calls = plan_tools(interpretation)

        self.assertEqual(calls[-1].name, "mapbox_reverse_lookup")
        self.assertEqual(
            calls[-1].arguments,
            {
                "longitude": 108.2,
                "latitude": 16.1,
                "language": "vi",
                "limit": 5,
            },
        )

    def test_general_clarification_and_unsupported_requests_use_no_tools(self):
        cases = (
            build_interpretation(
                intent=TravelIntent.GENERAL_CHAT,
                actions=[SemanticActionType.ANSWER_TRAVEL_QUESTION],
            ),
            build_interpretation(
                intent=TravelIntent.PLACE_SEARCH,
                actions=[SemanticActionType.REQUEST_CLARIFICATION],
                status=InterpretationStatus.NEEDS_CLARIFICATION,
                missing_information=["Vị trí hiện tại"],
            ),
            build_interpretation(
                intent=TravelIntent.UNSUPPORTED_CAPABILITY,
                actions=[SemanticActionType.REPORT_UNSUPPORTED],
                status=InterpretationStatus.UNSUPPORTED,
            ),
        )

        for interpretation in cases:
            with self.subTest(intent=interpretation.primary_intent):
                self.assertEqual(plan_tools(interpretation), ())


def build_interpretation(
    *,
    intent: TravelIntent,
    actions: list[SemanticActionType],
    status: InterpretationStatus = InterpretationStatus.SUPPORTED,
    domains: list[TravelDomain] | None = None,
    entities: SemanticEntities | None = None,
    location: SemanticLocation | None = None,
    constraints: SemanticConstraints | None = None,
    missing_information: list[str] | None = None,
) -> SemanticInterpretation:
    return SemanticInterpretation(
        primary_intent=intent,
        normalized_query="Tháng 9 đi Đà Lạt có ổn không?",
        travel_domains=domains or [],
        entities=entities or SemanticEntities(),
        location=location or SemanticLocation(),
        constraints=constraints or SemanticConstraints(),
        actions=[SemanticAction(type=action) for action in actions],
        missing_information=missing_information or [],
        status=status,
    )
