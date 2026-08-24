"""Tests for structured destination candidates and Mapbox verification."""

import json
from contextlib import redirect_stdout
from io import StringIO

from django.test import SimpleTestCase
from langchain_core.messages import AIMessage

from chatbot.destination_discovery import (
    CandidateMatchStatus,
    DestinationCandidate,
    DestinationCandidateGenerator,
    DestinationCandidateSet,
    match_candidate,
    normalize_place_name,
    place_name_similarity,
)
from chatbot.intent import TravelIntent
from chatbot.orchestrator import ChatOrchestrator
from chatbot.semantic import (
    SemanticAction,
    SemanticActionType,
    SemanticEntities,
    SemanticInterpretation,
    SemanticLocation,
)
from chatbot.tools.models import MapboxPlaceItem
from chatbot.tools.registry import ToolExecution


class DestinationMatcherTests(SimpleTestCase):
    def test_normalizes_vietnamese_names_and_token_order(self):
        self.assertEqual(normalize_place_name("Hồ Xuân Hương"), "ho xuan huong")
        self.assertEqual(place_name_similarity("Hồ Xuân Hương", "Ho Xuan Huong"), 1)
        self.assertEqual(place_name_similarity("Lake Xuan Huong", "Xuan Huong Lake"), 1)

    def test_matches_alias_and_fuzzy_name(self):
        candidate = DestinationCandidate(
            name="Hồ Xuân Hương",
            aliases=["Xuan Huong Lake"],
            categoryHints=["lake"],
            reason="Biểu tượng Đà Lạt",
        )
        result = match_candidate(
            candidate,
            [place("mapbox.1", "Xuan Huong Lak", ["lake"])],
        )

        self.assertEqual(result.status, CandidateMatchStatus.MATCHED)
        self.assertEqual(result.place.mapbox_id, "mapbox.1")
        self.assertGreaterEqual(result.similarity, 0.88)

    def test_category_breaks_a_name_tie(self):
        candidate = DestinationCandidate(
            name="Central Park",
            categoryHints=["tourist_attraction"],
            reason="Điểm tham quan",
        )
        result = match_candidate(
            candidate,
            [
                place("mapbox.cafe", "Central Park", ["cafe"]),
                place(
                    "mapbox.attraction",
                    "Central Park",
                    ["tourist_attraction"],
                ),
            ],
        )

        self.assertEqual(result.status, CandidateMatchStatus.MATCHED)
        self.assertEqual(result.place.mapbox_id, "mapbox.attraction")

    def test_reports_ambiguous_and_not_found(self):
        candidate = DestinationCandidate(
            name="Love Valley",
            reason="Điểm tham quan",
        )
        ambiguous = match_candidate(
            candidate,
            [
                place("mapbox.1", "Love Valley", []),
                place("mapbox.2", "Love Valley", []),
            ],
        )
        missing = match_candidate(
            candidate,
            [place("mapbox.3", "Night Market", ["market"])],
        )

        self.assertEqual(ambiguous.status, CandidateMatchStatus.AMBIGUOUS)
        self.assertEqual(missing.status, CandidateMatchStatus.NOT_FOUND)

    def test_exact_name_match_beats_a_near_name_match(self):
        candidate = DestinationCandidate(
            name="Hồ Xuân Hương",
            categoryHints=["lake"],
            reason="Biểu tượng Đà Lạt",
        )

        result = match_candidate(
            candidate,
            [
                place("mapbox.exact", "Hồ Xuân Hương", ["lake"]),
                place("mapbox.near", "Hồ Xuân Hươn", ["lake"]),
            ],
        )

        self.assertEqual(result.status, CandidateMatchStatus.MATCHED)
        self.assertEqual(result.place.mapbox_id, "mapbox.exact")

    def test_duplicate_exact_names_choose_clearly_nearest_place(self):
        candidate = DestinationCandidate(
            name="Hồ Xuân Hương",
            categoryHints=["lake"],
            reason="Biểu tượng Đà Lạt",
        )

        result = match_candidate(
            candidate,
            [
                place(
                    "mapbox.far",
                    "Hồ Xuân Hương",
                    ["lake", "outdoors"],
                    distance=2207,
                ),
                place(
                    "mapbox.near",
                    "Hồ Xuân Hương",
                    ["lake", "outdoors"],
                    distance=902,
                ),
            ],
        )

        self.assertEqual(result.status, CandidateMatchStatus.MATCHED)
        self.assertEqual(result.place.mapbox_id, "mapbox.near")
        self.assertEqual(result.place.distance_meters, 902)

    def test_duplicate_exact_names_remain_ambiguous_when_distances_are_close(self):
        candidate = DestinationCandidate(
            name="Hồ Xuân Hương",
            categoryHints=["lake"],
            reason="Biểu tượng Đà Lạt",
        )

        result = match_candidate(
            candidate,
            [
                place("mapbox.one", "Hồ Xuân Hương", ["lake"], distance=900),
                place("mapbox.two", "Hồ Xuân Hương", ["lake"], distance=950),
            ],
        )

        self.assertEqual(result.status, CandidateMatchStatus.AMBIGUOUS)
        self.assertIsNone(result.place)


class CandidateGeneratorTests(SimpleTestCase):
    def test_uses_structured_schema_and_sends_knowledge_context(self):
        structured_model = StubStructuredModel(
            DestinationCandidateSet(
                destination="Đà Lạt",
                candidates=[
                    DestinationCandidate(
                        name="Hồ Xuân Hương",
                        reason="Biểu tượng Đà Lạt",
                    )
                ],
            )
        )
        model = StructuredChatModel(structured_model)
        generator = DestinationCandidateGenerator(model)
        interpretation = destination_interpretation()

        result = generator.generate(
            "Đi chơi Đà Lạt thì đi đâu?",
            interpretation=interpretation,
            history=(),
            knowledge_result={"success": True, "data": {"chunks": []}},
        )

        self.assertEqual(result.candidates[0].name, "Hồ Xuân Hương")
        self.assertIs(model.schema, DestinationCandidateSet)
        self.assertEqual(model.method, "json_schema")
        payload = json.loads(structured_model.messages[1].content)
        self.assertTrue(payload["knowledgeBaseResult"]["success"])


class DestinationDiscoveryPipelineTests(SimpleTestCase):
    def test_runs_candidates_matches_category_and_sends_only_safe_places(self):
        candidate_generator = StubCandidateGenerator(
            DestinationCandidateSet(
                destination="Đà Lạt",
                candidates=[
                    DestinationCandidate(
                        name="Hồ Xuân Hương",
                        categoryHints=["lake"],
                        reason="Biểu tượng Đà Lạt",
                    ),
                    DestinationCandidate(
                        name="Địa điểm không tồn tại",
                        reason="Ứng viên sai",
                    ),
                ],
            )
        )
        registry = DiscoveryRegistry()
        model = FinalChatModel()

        terminal_output = StringIO()
        with redirect_stdout(terminal_output):
            result = ChatOrchestrator(
                model,
                registry,
                semantic_interpreter=StubInterpreter(destination_interpretation()),
                candidate_generator=candidate_generator,
                max_tool_calls=8,
            ).answer("Đi chơi Đà Lạt thì đi đâu?")

        self.assertEqual(result.answer, "Đây là các địa điểm đã xác thực.")
        self.assertEqual(
            [name for name, _ in registry.calls],
            [
                "search_travel_knowledge",
                "mapbox_forward_search",
                "mapbox_forward_search",
                "mapbox_forward_search",
                "mapbox_category_search",
            ],
        )
        self.assertEqual(registry.calls[2][1]["types"], "poi")
        self.assertEqual(
            registry.calls[-1][1]["category_id"],
            "tourist_attraction",
        )
        final_context = model.messages[3].content
        self.assertIn('"mapboxId":"mapbox.lake"', final_context)
        self.assertIn('"mapboxId":"mapbox.garden"', final_context)
        self.assertNotIn("Địa điểm không tồn tại", final_context)
        self.assertEqual(final_context.count('"mapboxId":"mapbox.lake"'), 1)
        verification_log = terminal_output.getvalue()
        self.assertEqual(
            verification_log.count("Destination verification Mapbox request:"),
            2,
        )
        self.assertIn('"method": "GET"', verification_log)
        self.assertIn('"path": "/search/searchbox/v1/forward"', verification_log)
        self.assertIn('"q": "Hồ Xuân Hương"', verification_log)
        self.assertIn('"limit": 2', verification_log)
        self.assertIn('"proximity": "108.44,11.94"', verification_log)
        self.assertIn('"accessToken": "[server-side omitted]"', verification_log)
        self.assertNotIn("access_token", verification_log)
        self.assertEqual(
            verification_log.count("Destination verification Mapbox response:"),
            2,
        )
        self.assertIn('"type": "FeatureCollection"', verification_log)
        self.assertIn('"mapbox_id": "mapbox.lake"', verification_log)
        self.assertIn("Destination verification result:", verification_log)
        self.assertIn('"status": "matched"', verification_log)
        self.assertIn('"status": "not_found"', verification_log)
        self.assertIn('"mapboxId": "mapbox.lake"', verification_log)
        self.assertIn('"mapboxId": "mapbox.garden"', verification_log)

    def test_tool_budget_reserves_the_category_search(self):
        candidates = [
            DestinationCandidate(name=f"Place {index}", reason="Nổi tiếng")
            for index in range(5)
        ]
        registry = DiscoveryRegistry()

        ChatOrchestrator(
            FinalChatModel(),
            registry,
            semantic_interpreter=StubInterpreter(destination_interpretation()),
            candidate_generator=StubCandidateGenerator(
                DestinationCandidateSet(
                    destination="Đà Lạt",
                    candidates=candidates,
                )
            ),
            max_tool_calls=4,
        ).answer("Đi chơi Đà Lạt thì đi đâu?")

        self.assertEqual(len(registry.calls), 4)
        self.assertEqual(registry.calls[-1][0], "mapbox_category_search")


def place(mapbox_id, name, categories, *, distance=None):
    return MapboxPlaceItem(
        mapboxId=mapbox_id,
        name=name,
        featureType="poi",
        fullAddress="Đà Lạt, Lâm Đồng",
        longitude=108.44,
        latitude=11.94,
        poiCategories=categories,
        poiCategoryIds=categories,
        distanceMeters=distance,
    )


def destination_interpretation():
    return SemanticInterpretation(
        primary_intent=TravelIntent.DESTINATION_DISCOVERY,
        normalized_query="Đi chơi Đà Lạt thì đi đâu?",
        entities=SemanticEntities(destinations=["Đà Lạt"]),
        location=SemanticLocation(near="Đà Lạt"),
        actions=[SemanticAction(type=SemanticActionType.DISCOVER_PLACES)],
        status="supported",
    )


def mapbox_execution(*places):
    features = [
        {
            "properties": {
                "mapbox_id": item.mapbox_id,
                "name": item.name,
                "full_address": item.full_address,
            }
        }
        for item in places
    ]
    content = {
        "success": True,
        "data": {
            "attribution": "© Mapbox",
            "results": [item.model_dump(mode="json", by_alias=True) for item in places],
            "rawResponse": {
                "type": "FeatureCollection",
                "features": features,
                "attribution": "© Mapbox",
            },
        },
    }
    return ToolExecution(
        content=json.dumps(content, ensure_ascii=False),
        sources=(),
        success=True,
        system_failure=False,
    )


class StubStructuredModel:
    def __init__(self, result):
        self.result = result
        self.messages = None

    def invoke(self, messages):
        self.messages = messages
        return self.result


class StructuredChatModel:
    def __init__(self, structured_model):
        self.structured_model = structured_model
        self.schema = None
        self.method = None

    def with_structured_output(self, schema, *, method):
        self.schema = schema
        self.method = method
        return self.structured_model


class StubCandidateGenerator:
    def __init__(self, result):
        self.result = result

    def generate(self, question, **kwargs):
        return self.result


class StubInterpreter:
    def __init__(self, interpretation):
        self.interpretation = interpretation

    def interpret(self, question, *, history=(), current_location=None):
        return self.interpretation


class FinalChatModel:
    def __init__(self):
        self.messages = None

    def invoke(self, messages):
        self.messages = messages
        return AIMessage(content="Đây là các địa điểm đã xác thực.")


class DiscoveryRegistry:
    def __init__(self):
        self.calls = []

    def execute(self, name, arguments):
        self.calls.append((name, arguments))
        if name == "search_travel_knowledge":
            return ToolExecution(
                content=json.dumps(
                    {
                        "success": True,
                        "data": {"chunks": [], "sources": []},
                    }
                ),
                sources=(),
                success=True,
                system_failure=False,
            )
        if name == "mapbox_category_search":
            return mapbox_execution(
                place("mapbox.lake", "Hồ Xuân Hương", ["lake"]),
                place("mapbox.garden", "Vườn Hoa Thành Phố", ["tourist_attraction"]),
            )
        if arguments["q"] == "Đà Lạt":
            return ToolExecution(
                content=(
                    '{"success":true,"data":{"results":['
                    '{"longitude":108.44,"latitude":11.94}]}}'
                ),
                sources=(),
                success=True,
                system_failure=False,
            )
        if arguments["q"] == "Hồ Xuân Hương":
            return mapbox_execution(
                place("mapbox.lake", "Ho Xuan Huong", ["lake"])
            )
        return mapbox_execution()
