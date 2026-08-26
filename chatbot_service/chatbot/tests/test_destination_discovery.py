"""Tests for structured destination candidates and Mapbox verification."""

import json
from contextlib import redirect_stdout
from io import StringIO

from django.test import SimpleTestCase
from langchain_core.messages import AIMessage

from chatbot.destination_discovery import (
    DestinationCandidate,
    DestinationCandidateGenerator,
    DestinationCandidateSet,
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
            knowledge_chunks=[
                {
                    "title": "Hoạt động tại Đà Lạt",
                    "content": "Đi dạo quanh hồ vào sáng sớm.",
                }
            ],
        )

        self.assertEqual(result.candidates[0].name, "Hồ Xuân Hương")
        self.assertIs(model.schema, DestinationCandidateSet)
        self.assertEqual(model.method, "json_schema")
        payload = json.loads(structured_model.messages[1].content)
        self.assertEqual(
            payload["knowledgeBase"],
            [
                {
                    "title": "Hoạt động tại Đà Lạt",
                    "content": "Đi dạo quanh hồ vào sáng sớm.",
                }
            ],
        )


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
                "mapbox_resolve_candidates",
            ],
        )
        self.assertEqual(len(registry.calls[2][1]["candidates"]), 2)
        self.assertEqual(
            registry.calls[-1][1]["categoryId"],
            "tourist_attraction",
        )
        final_context = model.messages[0].content
        evidence = json.loads(
            final_context.split("=== DỮ LIỆU BACKEND ===\n", 1)[1]
        )
        self.assertEqual(
            evidence["matchedCandidates"],
            [
                {
                    "name": "Ho Xuan Huong",
                    "mapboxId": "mapbox.lake",
                    "fullAddress": "Đà Lạt, Lâm Đồng",
                    "categoryHints": ["lake"],
                    "reason": "Biểu tượng Đà Lạt",
                    "poiCategories": ["lake"],
                    "longitude": 108.44,
                    "latitude": 11.94,
                    "distanceMeters": 902.0,
                    "etaMinutes": None,
                    "rating": None,
                    "popularity": None,
                }
            ],
        )
        self.assertEqual(
            set(evidence["matchedCandidates"][0]),
            {
                "name",
                "mapboxId",
                "fullAddress",
                "categoryHints",
                "reason",
                "poiCategories",
                "longitude",
                "latitude",
                "distanceMeters",
                "etaMinutes",
                "rating",
                "popularity",
            },
        )
        self.assertEqual(
            evidence["additionalMapboxPlaces"][0]["place"]["mapboxId"],
            "mapbox.garden",
        )
        self.assertEqual(
            evidence["knowledgeBase"],
            [
                {
                    "title": "Hoạt động du lịch tại Đà Lạt",
                    "content": "Dành buổi sáng đi dạo quanh hồ.",
                }
            ],
        )
        self.assertEqual(
            set(evidence["knowledgeBase"][0]),
            {"title", "content"},
        )
        self.assertNotIn("Địa điểm không tồn tại", final_context)
        verification_log = terminal_output.getvalue()
        final_request_log = verification_log.split(
            "Gemini request messages:\n",
            1,
        )[1].split("Gemini response:\n", 1)[0]
        self.assertIn('"knowledgeBase": [', final_request_log)
        self.assertIn('"title": "Hoạt động du lịch tại Đà Lạt"', final_request_log)
        self.assertIn(
            '"content": "Dành buổi sáng đi dạo quanh hồ."',
            final_request_log,
        )
        self.assertNotIn('"source":', final_request_log)
        self.assertNotIn('"heading":', final_request_log)
        self.assertNotIn('"sources":', final_request_log)
        self.assertNotIn('"errorCode":', final_request_log)
        self.assertNotIn('"errorMessage":', final_request_log)
        self.assertEqual(
            verification_log.count("Destination verification Mapbox request:"),
            1,
        )
        self.assertIn('"method": "POST"', verification_log)
        self.assertIn(
            '"path": "/api/chatbot/tools/mapbox-resolve-candidates"',
            verification_log,
        )
        self.assertIn('"name": "Hồ Xuân Hương"', verification_log)
        self.assertIn('"longitude": 108.44', verification_log)
        self.assertIn('"latitude": 11.94', verification_log)
        self.assertIn('"accessToken": "[server-side omitted]"', verification_log)
        self.assertNotIn("access_token", verification_log)
        self.assertEqual(
            verification_log.count("Destination verification Mapbox response:"),
            1,
        )
        self.assertNotIn('"rawResponse"', verification_log)
        self.assertNotIn('"features"', verification_log)
        self.assertIn("Destination verification result:", verification_log)
        self.assertIn('"status": "matched"', verification_log)
        self.assertIn('"status": "not_found"', verification_log)
        self.assertIn('"mapboxId": "mapbox.lake"', verification_log)
        self.assertIn('"mapboxId": "mapbox.garden"', verification_log)

    def test_batch_resolution_uses_one_tool_call_for_all_candidates(self):
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

        self.assertEqual(len(registry.calls), 3)
        self.assertEqual(registry.calls[-1][0], "mapbox_resolve_candidates")
        self.assertEqual(len(registry.calls[-1][1]["candidates"]), 5)


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
    content = {
        "success": True,
        "data": {
            "attribution": "© Mapbox",
            "results": [item.model_dump(mode="json", by_alias=True) for item in places],
        },
    }
    return ToolExecution(
        content=json.dumps(content, ensure_ascii=False),
        sources=(),
        success=True,
        system_failure=False,
    )


def candidate_resolution_execution():
    lake = place("mapbox.lake", "Ho Xuan Huong", ["lake"], distance=902)
    garden = place(
        "mapbox.garden",
        "Vườn Hoa Thành Phố",
        ["tourist_attraction"],
    )
    content = {
        "success": True,
        "data": {
            "attribution": "© Mapbox",
            "results": [
                {
                    "candidateId": "candidate-1",
                    "status": "matched",
                    "similarity": 1.0,
                    "place": lake.model_dump(mode="json", by_alias=True),
                },
                {
                    "candidateId": "candidate-2",
                    "status": "not_found",
                    "similarity": None,
                    "place": None,
                },
            ],
            "additionalPlaces": [
                garden.model_dump(mode="json", by_alias=True)
            ],
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
                        "data": {
                            "chunks": [
                                {
                                    "content": "  Dành buổi sáng đi dạo quanh hồ.  ",
                                    "title": "Hoạt động du lịch tại Đà Lạt",
                                    "source": "destinations/da-lat/activities.md",
                                    "heading": "Đi dạo",
                                }
                            ],
                            "sources": [
                                {
                                    "type": "knowledge_base",
                                    "title": "Hoạt động du lịch tại Đà Lạt",
                                    "source": "destinations/da-lat/activities.md",
                                }
                            ],
                        },
                        "errorCode": None,
                        "errorMessage": None,
                    }
                ),
                sources=(),
                success=True,
                system_failure=False,
            )
        if name == "mapbox_resolve_candidates":
            return candidate_resolution_execution()
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
        return mapbox_execution()
