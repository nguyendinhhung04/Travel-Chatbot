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
    SearchTargetType,
    TravelDomain,
)
from chatbot.tool_planner import plan_tools


class ToolPlannerTests(SimpleTestCase):
    def test_itinerary_making_reuses_existing_discovery_without_route_tool(self):
        interpretation = build_interpretation(
            intent=TravelIntent.ITINERARY_MAKING,
            actions=[
                SemanticActionType.DISCOVER_PLACES,
                SemanticActionType.MAKE_ITINERARY,
            ],
            domains=[TravelDomain.ATTRACTION],
            entities=SemanticEntities(
                destinations=["Hà Nội"],
                place_types=["địa điểm vui chơi"],
            ),
        )

        calls = plan_tools(interpretation, max_categories=1)

        self.assertEqual(
            [call.name for call in calls],
            [
                "mapbox_forward_search",
                "search_travel_knowledge",
                "mapbox_category_search",
            ],
        )
        self.assertEqual(calls[0].arguments["types"], "city,place")
        self.assertNotIn("mapbox_optimize_route", [call.name for call in calls])

    def test_incomplete_itinerary_making_uses_no_tools(self):
        interpretation = build_interpretation(
            intent=TravelIntent.ITINERARY_MAKING,
            actions=[SemanticActionType.REQUEST_CLARIFICATION],
            status=InterpretationStatus.NEEDS_CLARIFICATION,
            missing_information=["destination"],
        )

        self.assertEqual(plan_tools(interpretation), ())

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

    def test_rag_uses_semantic_destination_as_metadata_filter(self):
        interpretation = build_interpretation(
            intent=TravelIntent.TRAVEL_QA,
            actions=[SemanticActionType.ANSWER_TRAVEL_QUESTION],
            entities=SemanticEntities(destinations=["Đà Lạt"]),
        )

        call = plan_tools(interpretation)[0]

        self.assertEqual(
            call.arguments,
            {
                "query": "Tháng 9 đi Đà Lạt có ổn không?",
                "destination": "Đà Lạt",
            },
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
            constraints=SemanticConstraints(open_now=True),
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
                "types": "poi",
                "rank_strategy": "relevance",
                "open_now": True,
                "minimum_rating": 0.0,
            },
        )

    def test_named_city_uses_forward_search_without_poi_rating(self):
        interpretation = build_interpretation(
            intent=TravelIntent.PLACE_SEARCH,
            actions=[SemanticActionType.FIND_NAMED_PLACE],
            entities=SemanticEntities(
                destinations=["Đà Nẵng"],
                search_target=SearchTargetType.CITY,
            ),
            constraints=SemanticConstraints(
                open_now=True,
                minimum_rating=4.5,
            ),
        )

        call = plan_tools(interpretation)[0]

        self.assertEqual(call.name, "mapbox_forward_search")
        self.assertEqual(
            call.arguments,
            {
                "q": "Đà Nẵng",
                "language": "vi",
                "limit": 5,
                "near": "Đà Nẵng",
                "types": "city",
                "rank_strategy": "relevance",
            },
        )

    def test_place_details_city_falls_back_to_destination_forward_search(self):
        interpretation = build_interpretation(
            intent=TravelIntent.PLACE_DETAILS,
            actions=[SemanticActionType.ANSWER_TRAVEL_QUESTION],
            entities=SemanticEntities(
                destinations=["Đà Lạt"],
                search_target=SearchTargetType.CITY,
            ),
        )

        calls = plan_tools(interpretation)

        self.assertEqual(
            [call.name for call in calls],
            ["search_travel_knowledge", "mapbox_forward_search"],
        )
        self.assertEqual(
            calls[1].arguments,
            {
                "q": "Đà Lạt",
                "language": "vi",
                "limit": 5,
                "types": "city",
                "rank_strategy": "relevance",
                "auto_complete": False,
            },
        )
        self.assertEqual(calls[1].evidence_kind, "destination_location")

    def test_named_poi_uses_explicit_distance_and_rating(self):
        interpretation = build_interpretation(
            intent=TravelIntent.PLACE_SEARCH,
            actions=[SemanticActionType.FIND_NAMED_PLACE],
            entities=SemanticEntities(places=["quán cafe"]),
            constraints=SemanticConstraints(
                minimum_rating=3.5,
                rank_strategy="distance",
            ),
        )

        call = plan_tools(interpretation)[0]

        self.assertEqual(call.arguments["types"], "poi")
        self.assertEqual(call.arguments["minimum_rating"], 3.5)
        self.assertEqual(call.arguments["rank_strategy"], "distance")

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
                "mapbox_forward_search",
                "mapbox_category_search",
                "mapbox_category_search",
                "mapbox_category_search",
            ],
        )
        self.assertEqual(
            calls[0].arguments,
            {
                "q": "Đà Nẵng",
                "language": "vi",
                "limit": 3,
                "types": "poi,address,city,place",
                "rank_strategy": "relevance",
                "auto_complete": False,
            },
        )
        self.assertEqual(
            [call.arguments["category_id"] for call in calls[1:]],
            ["cafe", "coffee_shop", "restaurant"],
        )
        for call in calls[1:]:
            self.assertEqual(call.arguments["language"], "vi")
            self.assertEqual(call.arguments["limit"], 10)
            self.assertEqual(call.arguments["minimum_rating"], 0.0)
        self.assertFalse(
            any(call.name == "mapbox_list_categories" for call in calls)
        )

    def test_cafe_near_named_poi_resolves_anchor_and_cafe_categories(self):
        interpretation = build_interpretation(
            intent=TravelIntent.PLACE_SEARCH,
            actions=[SemanticActionType.DISCOVER_PLACES],
            domains=[TravelDomain.FOOD],
            entities=SemanticEntities(
                destinations=["FPT Phạm Văn Bạch"],
                place_types=["quán cafe"],
            ),
            location=SemanticLocation(near="FPT Phạm Văn Bạch"),
        )

        calls = plan_tools(interpretation)

        self.assertEqual(calls[0].name, "mapbox_forward_search")
        self.assertEqual(calls[0].arguments["q"], "FPT Phạm Văn Bạch")
        self.assertEqual(calls[0].arguments["types"], "poi,address,city,place")
        self.assertEqual(
            [call.arguments["category_id"] for call in calls[1:]],
            ["cafe", "coffee_shop", "restaurant"],
        )
        self.assertTrue(
            all(call.destination == "FPT Phạm Văn Bạch" for call in calls[1:])
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
