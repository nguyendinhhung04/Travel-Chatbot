"""Tests for verified ADD_STOP itinerary mutations."""

import json

from django.test import SimpleTestCase
from langchain_core.messages import AIMessage

from chatbot.intent import TravelIntent
from chatbot.itinerary_management import ItineraryManagementPipeline
from chatbot.orchestrator import ChatOrchestrator
from chatbot.semantic import (
    InterpretationStatus,
    SemanticAction,
    SemanticActionType,
    SemanticEntities,
    SemanticInterpretation,
)
from chatbot.tools.registry import ToolExecution


class ItineraryManagementPipelineTests(SimpleTestCase):
    def test_orchestrator_returns_updated_itinerary_and_operation_metadata(self):
        registry = StubRegistry()

        result = ChatOrchestrator(
            StubAnswerModel(),
            registry,
            semantic_interpreter=StubInterpreter(add_interpretation()),
        ).answer(
            "Thêm Công viên Yên Sở vào lịch trình",
            active_itinerary_id=ITINERARY_ID,
            active_itinerary_version=3,
        )

        self.assertEqual(result.answer, "Đã thêm Công viên Yên Sở.")
        self.assertEqual(result.itinerary.version, 4)
        self.assertEqual(
            result.itinerary_operation,
            {"type": "add_itinerary_stop", "success": True},
        )

    def test_add_stop_verifies_place_and_forwards_expected_version(self):
        registry = StubRegistry()

        result = ItineraryManagementPipeline(registry).execute(
            interpretation=add_interpretation(),
            active_itinerary_id=ITINERARY_ID,
            active_itinerary_version=3,
        )

        self.assertIsNotNone(result.itinerary)
        self.assertTrue(result.evidence["success"])
        self.assertEqual(
            [name for name, _arguments in registry.calls],
            ["get_itinerary", "mapbox_resolve_candidates", "add_itinerary_stop"],
        )
        mutation = registry.calls[-1][1]
        self.assertEqual(mutation["expectedVersion"], 3)
        self.assertEqual(mutation["stop"]["mapboxId"], "poi-yen-so")
        self.assertEqual(result.itinerary.version, 4)

    def test_add_stop_without_active_itinerary_does_not_call_tools(self):
        registry = StubRegistry()

        result = ItineraryManagementPipeline(registry).execute(
            interpretation=add_interpretation(),
            active_itinerary_id=None,
            active_itinerary_version=None,
        )

        self.assertIsNone(result.itinerary)
        self.assertEqual(result.evidence["errorCode"], "missing_active_itinerary")
        self.assertEqual(registry.calls, [])

    def test_duplicate_stop_is_rejected_before_mutation(self):
        registry = StubRegistry(existing_mapbox_id="poi-yen-so")

        result = ItineraryManagementPipeline(registry).execute(
            interpretation=add_interpretation(),
            active_itinerary_id=ITINERARY_ID,
            active_itinerary_version=3,
        )

        self.assertIsNone(result.itinerary)
        self.assertEqual(result.evidence["errorCode"], "duplicate_stop")
        self.assertEqual(
            [name for name, _arguments in registry.calls],
            ["get_itinerary", "mapbox_resolve_candidates"],
        )


ITINERARY_ID = "507f1f77bcf86cd799439011"


def add_interpretation() -> SemanticInterpretation:
    return SemanticInterpretation(
        primary_intent=TravelIntent.ITINERARY_MANAGEMENT,
        normalized_query="Thêm Công viên Yên Sở vào lịch trình",
        entities=SemanticEntities(
            places=["Công viên Yên Sở"],
            search_target="poi",
        ),
        actions=[
            SemanticAction(type=SemanticActionType.FIND_NAMED_PLACE),
            SemanticAction(type=SemanticActionType.ADD_ITINERARY_STOP),
        ],
        status=InterpretationStatus.SUPPORTED,
    )


def itinerary_payload(*, version: int, extra_mapbox_id: str | None = None):
    stops = [
        {
            "id": "507f1f77bcf86cd799439012",
            "order": 1,
            "inputIndex": 0,
            "mapboxId": "poi-a",
            "name": "Điểm A",
            "longitude": 105.8,
            "latitude": 21.0,
        },
        {
            "id": "507f1f77bcf86cd799439013",
            "order": 2,
            "inputIndex": 1,
            "mapboxId": extra_mapbox_id or "poi-b",
            "name": "Điểm B",
            "longitude": 105.9,
            "latitude": 21.1,
        },
    ]
    if version == 4:
        stops.append({
            "id": "507f1f77bcf86cd799439014",
            "order": 3,
            "inputIndex": 2,
            "mapboxId": "poi-yen-so",
            "name": "Công viên Yên Sở",
            "longitude": 105.88,
            "latitude": 20.96,
        })
    return {
        "id": ITINERARY_ID,
        "userId": "admin",
        "version": version,
        "title": "Hà Nội 2 ngày 1 đêm",
        "destination": "Hà Nội",
        "durationDays": 2,
        "durationNights": 1,
        "profile": "driving",
        "stops": stops,
        "route": {
            "type": "LineString",
            "coordinates": [[105.8, 21.0], [105.9, 21.1]],
        },
        "distanceMeters": 3000,
        "durationSeconds": 900,
        "provider": "mapbox",
        "generatedAt": "2026-08-28T10:00:00Z",
        "createdAt": "2026-08-28T09:00:00Z",
        "updatedAt": "2026-08-28T10:00:00Z",
    }


def execution(payload, *, success=True, error_code=None):
    return ToolExecution(
        content=json.dumps(
            {
                "success": success,
                "data": payload if success else None,
                "errorCode": error_code,
            }
        ),
        sources=(),
        success=success,
        system_failure=False,
        error_code=error_code,
    )


class StubRegistry:
    def __init__(self, *, existing_mapbox_id: str | None = None):
        self.calls = []
        self.existing_mapbox_id = existing_mapbox_id

    def execute(self, name, arguments):
        self.calls.append((name, arguments))
        if name == "get_itinerary":
            return execution(
                itinerary_payload(
                    version=3,
                    extra_mapbox_id=self.existing_mapbox_id,
                )
            )
        if name == "mapbox_resolve_candidates":
            return execution({
                "attribution": "© Mapbox",
                "results": [{
                    "candidateId": "candidate-1",
                    "status": "matched",
                    "place": {
                        "mapboxId": "poi-yen-so",
                        "name": "Công viên Yên Sở",
                        "featureType": "poi",
                        "longitude": 105.88,
                        "latitude": 20.96,
                        "poiCategories": ["park"],
                        "poiCategoryIds": ["park"],
                    },
                }],
                "additionalPlaces": [],
            })
        if name == "add_itinerary_stop":
            return execution(itinerary_payload(version=4))
        raise AssertionError(f"Unexpected tool: {name}")


class StubInterpreter:
    def __init__(self, interpretation):
        self.interpretation = interpretation

    def interpret(self, _question, **_kwargs):
        return self.interpretation


class StubAnswerModel:
    def invoke(self, _messages):
        return AIMessage(content="Đã thêm Công viên Yên Sở.")
