"""Tests for verified itinerary construction before backend integration."""

from __future__ import annotations

import json
from typing import Any

from django.test import SimpleTestCase

from chatbot.intent import TravelIntent
from chatbot.itinerary_making import (
    ITINERARY_CANDIDATE_PROMPT,
    ItineraryCandidate,
    ItineraryCandidateGenerator,
    ItineraryCandidatePlan,
    ItineraryMakingPipeline,
    MAX_ITINERARY_STOPS,
)
from chatbot.semantic import (
    ConversationMessage,
    InterpretationStatus,
    SemanticAction,
    SemanticActionType,
    SemanticEntities,
    SemanticInterpretation,
    SemanticTimeContext,
    TravelDomain,
)
from chatbot.tool_planner import plan_tools
from chatbot.tools.registry import ToolExecution


class ItineraryMakingPipelineTests(SimpleTestCase):
    def test_candidate_generator_uses_structured_schema_and_grounded_payload(self):
        expected = candidate_plan(3)
        model = StubChatModel(expected)
        generator = ItineraryCandidateGenerator(model)
        interpretation = build_interpretation()

        result = generator.generate(
            "Lập lịch trình Hà Nội 3 ngày 2 đêm",
            interpretation=interpretation,
            history=(ConversationMessage(role="user", content="Tôi thích lịch sử"),),
            knowledge_chunks=(
                {"title": "Du lịch Hà Nội", "content": "Ưu tiên di sản."},
            ),
        )

        self.assertEqual(result, expected)
        self.assertIs(model.schema, ItineraryCandidatePlan)
        self.assertEqual(model.method, "json_schema")
        self.assertEqual(len(model.invocations), 1)
        messages = model.invocations[0]
        self.assertEqual(messages[0].content, ITINERARY_CANDIDATE_PROMPT)
        payload = json.loads(messages[1].content)
        self.assertEqual(payload["question"], "Lập lịch trình Hà Nội 3 ngày 2 đêm")
        self.assertEqual(payload["history"][0]["content"], "Tôi thích lịch sử")
        self.assertEqual(payload["knowledgeBase"][0]["content"], "Ưu tiên di sản.")
        self.assertEqual(
            payload["semanticInterpretation"]["primary_intent"],
            "itinerary_making",
        )

    def test_success_reorders_only_verified_pois_and_preserves_reasons(self):
        interpretation = build_interpretation()
        registry = StubRegistry()
        optimizer = StubOptimizer(order=[2, 0, 1])
        pipeline = ItineraryMakingPipeline(
            object(),
            registry,
            candidate_generator=StubCandidateGenerator(candidate_plan(3)),
            route_optimizer=optimizer,
        )

        result = pipeline.execute(
            "Lập lịch trình Hà Nội 3 ngày 2 đêm",
            history=(),
            interpretation=interpretation,
            planned_calls=plan_tools(interpretation, max_categories=1),
        )

        self.assertIsNotNone(result.itinerary)
        assert result.itinerary is not None
        self.assertTrue(result.evidence["success"])
        self.assertEqual(result.itinerary.duration_days, 3)
        self.assertEqual(result.itinerary.duration_nights, 2)
        self.assertEqual(
            [stop.mapbox_id for stop in result.itinerary.stops],
            ["mapbox.poi.3", "mapbox.poi.1", "mapbox.poi.2"],
        )
        self.assertEqual(
            [stop.order for stop in result.itinerary.stops],
            [1, 2, 3],
        )
        self.assertEqual(result.itinerary.stops[0].reason, "Lý do 3")
        self.assertEqual(result.itinerary.route.type, "LineString")
        self.assertEqual(result.itinerary.distance_meters, 12000)
        self.assertEqual(
            [call.name for call in result.calls],
            [
                "search_travel_knowledge",
                "mapbox_forward_search",
                "mapbox_resolve_candidates",
                "mapbox_optimize_route",
            ],
        )
        self.assertEqual(len(optimizer.calls), 1)
        optimizer_stops = optimizer.calls[0].arguments["stops"]
        self.assertNotIn("reason", optimizer_stops[0])
        self.assertNotIn("fullAddress", optimizer_stops[0])

    def test_success_persists_itinerary_and_returns_backend_id_and_version(self):
        interpretation = build_interpretation()
        registry = StubRegistry()
        persisted = persisted_itinerary_execution()
        creator_calls = []

        def creator(call):
            creator_calls.append(call)
            return persisted

        pipeline = ItineraryMakingPipeline(
            object(),
            registry,
            itinerary_creator=creator,
            candidate_generator=StubCandidateGenerator(candidate_plan(3)),
        )

        result = pipeline.execute(
            "Láº­p lá»‹ch trĂ¬nh HĂ  Ná»™i 3 ngĂ y 2 Ä‘Ăªm",
            history=(),
            interpretation=interpretation,
            planned_calls=plan_tools(interpretation, max_categories=1),
        )

        self.assertIsNotNone(result.itinerary)
        assert result.itinerary is not None
        self.assertEqual(result.itinerary.id, "507f1f77bcf86cd799439011")
        self.assertEqual(result.itinerary.version, 1)
        self.assertEqual(result.calls[-1].name, "create_itinerary")
        self.assertEqual(len(creator_calls), 1)
        self.assertEqual(creator_calls[0].arguments["durationDays"], 3)
        self.assertEqual(len(creator_calls[0].arguments["stops"]), 3)

    def test_persistence_failure_never_returns_unsaved_itinerary(self):
        interpretation = build_interpretation()

        def creator(_call):
            return ToolExecution(
                content=json.dumps({
                    "success": False,
                    "data": None,
                    "errorCode": "database_unavailable",
                }),
                sources=(),
                success=False,
                system_failure=True,
                error_code="database_unavailable",
            )

        result = ItineraryMakingPipeline(
            object(),
            StubRegistry(),
            itinerary_creator=creator,
            candidate_generator=StubCandidateGenerator(candidate_plan(3)),
        ).execute(
            "Láº­p lá»‹ch trĂ¬nh HĂ  Ná»™i",
            history=(),
            interpretation=interpretation,
            planned_calls=plan_tools(interpretation, max_categories=1),
        )

        self.assertIsNone(result.itinerary)
        self.assertEqual(result.evidence["errorCode"], "database_unavailable")

    def test_ambiguous_non_poi_and_duplicate_results_cannot_reach_optimizer(self):
        interpretation = build_interpretation()
        registry = StubRegistry(
            resolution_overrides={
                "candidate-1": {"mapboxId": "mapbox.same", "featureType": "poi"},
                "candidate-2": {"mapboxId": "mapbox.same", "featureType": "poi"},
                "candidate-3": {"status": "ambiguous"},
                "candidate-4": {
                    "mapboxId": "mapbox.city",
                    "featureType": "place",
                },
            }
        )
        optimizer = StubOptimizer()
        pipeline = ItineraryMakingPipeline(
            object(),
            registry,
            candidate_generator=StubCandidateGenerator(candidate_plan(4)),
            route_optimizer=optimizer,
        )

        result = pipeline.execute(
            "Lập lịch trình Hà Nội 3 ngày 2 đêm",
            history=(),
            interpretation=interpretation,
            planned_calls=plan_tools(interpretation, max_categories=1),
        )

        self.assertIsNone(result.itinerary)
        self.assertEqual(result.evidence["errorCode"], "insufficient_verified_stops")
        self.assertEqual(
            [stop["mapboxId"] for stop in result.evidence["verifiedStops"]],
            ["mapbox.same"],
        )
        self.assertEqual(optimizer.calls, [])

    def test_more_than_twelve_candidates_are_capped_before_resolution(self):
        interpretation = build_interpretation()
        registry = StubRegistry()
        optimizer = StubOptimizer()
        pipeline = ItineraryMakingPipeline(
            object(),
            registry,
            candidate_generator=StubCandidateGenerator(candidate_plan(14)),
            route_optimizer=optimizer,
        )

        result = pipeline.execute(
            "Lập lịch trình Hà Nội 3 ngày 2 đêm",
            history=(),
            interpretation=interpretation,
            planned_calls=plan_tools(interpretation, max_categories=1),
        )

        self.assertIsNotNone(result.itinerary)
        assert result.itinerary is not None
        self.assertEqual(len(result.itinerary.stops), MAX_ITINERARY_STOPS)
        resolution_calls = [
            call
            for call in registry.calls
            if call[0] == "mapbox_resolve_candidates"
        ]
        self.assertEqual(
            [len(arguments["candidates"]) for _, arguments in resolution_calls],
            [5, 5, 2],
        )
        self.assertEqual(len(optimizer.calls[0].arguments["stops"]), 12)

    def test_missing_or_mismatched_destination_stops_before_resolution(self):
        missing_interpretation = build_interpretation(destination=None)
        missing_registry = StubRegistry()
        missing_optimizer = StubOptimizer()
        missing_result = ItineraryMakingPipeline(
            object(),
            missing_registry,
            candidate_generator=StubCandidateGenerator(candidate_plan(3)),
            route_optimizer=missing_optimizer,
        ).execute(
            "Lập lịch trình 3 ngày 2 đêm",
            history=(),
            interpretation=missing_interpretation,
            planned_calls=plan_tools(missing_interpretation),
        )

        self.assertEqual(missing_result.evidence["errorCode"], "missing_destination")
        self.assertEqual(missing_registry.calls, [])
        self.assertEqual(missing_optimizer.calls, [])

        mismatch_registry = StubRegistry()
        mismatch_optimizer = StubOptimizer()
        mismatch_result = ItineraryMakingPipeline(
            object(),
            mismatch_registry,
            candidate_generator=StubCandidateGenerator(
                candidate_plan(3, destination="Đà Nẵng")
            ),
            route_optimizer=mismatch_optimizer,
        ).execute(
            "Lập lịch trình Hà Nội 3 ngày 2 đêm",
            history=(),
            interpretation=build_interpretation(),
            planned_calls=plan_tools(build_interpretation(), max_categories=1),
        )

        self.assertEqual(
            mismatch_result.evidence["errorCode"],
            "candidate_destination_mismatch",
        )
        self.assertFalse(
            any(name == "mapbox_resolve_candidates" for name, _ in mismatch_registry.calls)
        )
        self.assertEqual(mismatch_optimizer.calls, [])

    def test_failed_or_inconsistent_optimization_never_returns_route(self):
        interpretation = build_interpretation()

        failed = ItineraryMakingPipeline(
            object(),
            StubRegistry(),
            candidate_generator=StubCandidateGenerator(candidate_plan(3)),
            route_optimizer=StubOptimizer(error_code="mapbox_timeout"),
        ).execute(
            "Lập lịch trình Hà Nội",
            history=(),
            interpretation=interpretation,
            planned_calls=plan_tools(interpretation, max_categories=1),
        )
        self.assertIsNone(failed.itinerary)
        self.assertEqual(failed.evidence["errorCode"], "mapbox_timeout")
        self.assertNotIn("itinerary", failed.evidence)

        inconsistent = ItineraryMakingPipeline(
            object(),
            StubRegistry(),
            candidate_generator=StubCandidateGenerator(candidate_plan(3)),
            route_optimizer=StubOptimizer(order=[0, 1], input_count=3),
        ).execute(
            "Lập lịch trình Hà Nội",
            history=(),
            interpretation=interpretation,
            planned_calls=plan_tools(interpretation, max_categories=1),
        )
        self.assertIsNone(inconsistent.itinerary)
        self.assertEqual(
            inconsistent.evidence["errorCode"],
            "invalid_optimization_result",
        )

    def test_unavailable_optimizer_and_tool_budget_fail_without_fake_geometry(self):
        interpretation = build_interpretation()
        unavailable = ItineraryMakingPipeline(
            object(),
            StubRegistry(),
            candidate_generator=StubCandidateGenerator(candidate_plan(3)),
        ).execute(
            "Lập lịch trình Hà Nội",
            history=(),
            interpretation=interpretation,
            planned_calls=plan_tools(interpretation, max_categories=1),
        )
        self.assertEqual(
            unavailable.evidence["errorCode"],
            "route_optimizer_unavailable",
        )
        self.assertNotIn("route", unavailable.evidence)

        budgeted_optimizer = StubOptimizer()
        budgeted = ItineraryMakingPipeline(
            object(),
            StubRegistry(),
            candidate_generator=StubCandidateGenerator(candidate_plan(3)),
            route_optimizer=budgeted_optimizer,
            max_tool_calls=3,
        ).execute(
            "Lập lịch trình Hà Nội",
            history=(),
            interpretation=interpretation,
            planned_calls=plan_tools(interpretation, max_categories=1),
        )
        self.assertEqual(budgeted.evidence["errorCode"], "tool_call_budget_exceeded")
        self.assertEqual(budgeted_optimizer.calls, [])

        def raising_optimizer(call):
            raise RuntimeError("backend unavailable")

        raised = ItineraryMakingPipeline(
            object(),
            StubRegistry(),
            candidate_generator=StubCandidateGenerator(candidate_plan(3)),
            route_optimizer=raising_optimizer,
        ).execute(
            "Lập lịch trình Hà Nội",
            history=(),
            interpretation=interpretation,
            planned_calls=plan_tools(interpretation, max_categories=1),
        )
        self.assertEqual(raised.evidence["errorCode"], "route_optimizer_failed")
        self.assertNotIn("route", raised.evidence)

    def test_candidate_prompt_forbids_provider_and_route_fabrication(self):
        self.assertIn("Không tạo địa chỉ, tọa độ, Mapbox ID", ITINERARY_CANDIDATE_PROMPT)
        self.assertIn("route geometry", ITINERARY_CANDIDATE_PROMPT)
        self.assertIn("không tự tối ưu thứ tự", ITINERARY_CANDIDATE_PROMPT)


class StubCandidateGenerator:
    def __init__(self, result: ItineraryCandidatePlan) -> None:
        self.result = result

    def generate(self, *args, **kwargs) -> ItineraryCandidatePlan:
        return self.result


class StubChatModel:
    def __init__(self, response: ItineraryCandidatePlan) -> None:
        self.response = response
        self.schema = None
        self.method = None
        self.invocations = []

    def with_structured_output(self, schema, *, method):
        self.schema = schema
        self.method = method
        return self

    def invoke(self, messages):
        self.invocations.append(list(messages))
        return self.response


class StubRegistry:
    def __init__(
        self,
        *,
        resolution_overrides: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.resolution_overrides = resolution_overrides or {}

    def execute(self, name: str, arguments: Any) -> ToolExecution:
        normalized_arguments = dict(arguments)
        self.calls.append((name, normalized_arguments))
        if name == "search_travel_knowledge":
            return success_execution(
                {
                    "chunks": [
                        {
                            "title": "Du lịch Hà Nội",
                            "content": "Ưu tiên các điểm phù hợp thời lượng.",
                            "source": "hanoi.md",
                        }
                    ],
                    "sources": [],
                }
            )
        if name == "mapbox_forward_search":
            return success_execution(
                {
                    "results": [
                        {
                            "name": "Hà Nội",
                            "longitude": 105.8342,
                            "latitude": 21.0278,
                        }
                    ]
                }
            )
        if name == "mapbox_resolve_candidates":
            return self._resolution_execution(normalized_arguments)
        raise AssertionError(f"Unexpected registry call: {name}")

    def _resolution_execution(self, arguments: dict[str, Any]) -> ToolExecution:
        results = []
        for candidate in arguments["candidates"]:
            candidate_id = candidate["candidateId"]
            number = int(candidate_id.rsplit("-", 1)[1])
            override = self.resolution_overrides.get(candidate_id, {})
            status = override.get("status", "matched")
            place = None
            if status == "matched":
                place = {
                    "mapboxId": override.get("mapboxId", f"mapbox.poi.{number}"),
                    "name": candidate["name"],
                    "featureType": override.get("featureType", "poi"),
                    "fullAddress": f"Địa chỉ {number}, Hà Nội",
                    "longitude": 105.8 + number / 100,
                    "latitude": 21.0 + number / 100,
                    "poiCategories": ["tourist_attraction"],
                    "poiCategoryIds": ["tourist_attraction"],
                }
            results.append(
                {
                    "candidateId": candidate_id,
                    "status": status,
                    "similarity": 1.0 if status == "matched" else None,
                    "place": place,
                }
            )
        return success_execution(
            {
                "attribution": "© Mapbox",
                "results": results,
                "additionalPlaces": [],
            }
        )


class StubOptimizer:
    def __init__(
        self,
        *,
        order: list[int] | None = None,
        input_count: int | None = None,
        error_code: str | None = None,
    ) -> None:
        self.order = order
        self.input_count = input_count
        self.error_code = error_code
        self.calls = []

    def __call__(self, call):
        self.calls.append(call)
        if self.error_code:
            return ToolExecution(
                content=json.dumps(
                    {
                        "success": False,
                        "errorCode": self.error_code,
                        "errorMessage": "Optimization failed.",
                    }
                ),
                sources=(),
                success=False,
                system_failure=True,
                error_code=self.error_code,
            )

        stops = call.arguments["stops"]
        output_order = self.order if self.order is not None else list(range(len(stops)))
        source_count = self.input_count if self.input_count is not None else len(stops)
        ordered_stops = []
        for order_number, input_index in enumerate(output_order, start=1):
            source = stops[input_index]
            ordered_stops.append(
                {
                    **source,
                    "order": order_number,
                    "inputIndex": input_index,
                }
            )
        coordinates = [
            [stop["longitude"], stop["latitude"]]
            for stop in ordered_stops
        ]
        if len(coordinates) < 2 and source_count >= 2:
            coordinates.append(coordinates[0])
        return success_execution(
            {
                "profile": call.arguments["profile"],
                "orderedStops": ordered_stops,
                "geometry": {
                    "type": "LineString",
                    "coordinates": coordinates,
                },
                "distanceMeters": 12000,
                "durationSeconds": 3600,
            }
        )


def candidate_plan(
    count: int,
    *,
    destination: str = "Hà Nội",
) -> ItineraryCandidatePlan:
    return ItineraryCandidatePlan(
        title="Hà Nội 3 ngày 2 đêm",
        destination=destination,
        candidates=[
            ItineraryCandidate(
                name=f"Địa điểm {index}",
                aliases=[],
                categoryHints=["tourist_attraction"],
                reason=f"Lý do {index}",
            )
            for index in range(1, count + 1)
        ],
    )


def build_interpretation(
    *,
    destination: str | None = "Hà Nội",
) -> SemanticInterpretation:
    return SemanticInterpretation(
        primary_intent=TravelIntent.ITINERARY_MAKING,
        normalized_query="Lập lịch trình Hà Nội 3 ngày 2 đêm",
        travel_domains=[TravelDomain.ATTRACTION],
        entities=SemanticEntities(
            destinations=[destination] if destination else [],
            place_types=["địa điểm vui chơi"],
        ),
        time_context=SemanticTimeContext(duration_days=3, duration_nights=2),
        actions=[
            SemanticAction(type=SemanticActionType.DISCOVER_PLACES),
            SemanticAction(type=SemanticActionType.MAKE_ITINERARY),
        ],
        status=InterpretationStatus.SUPPORTED,
    )


def success_execution(data: dict[str, Any]) -> ToolExecution:
    return ToolExecution(
        content=json.dumps(
            {
                "success": True,
                "data": data,
                "errorCode": None,
                "errorMessage": None,
            },
            ensure_ascii=False,
        ),
        sources=(),
        success=True,
        system_failure=False,
    )


def persisted_itinerary_execution() -> ToolExecution:
    return success_execution(
        {
            "id": "507f1f77bcf86cd799439011",
            "userId": "admin",
            "version": 1,
            "title": "HĂ  Ná»™i 3 ngĂ y 2 Ä‘Ăªm",
            "destination": "HĂ  Ná»™i",
            "durationDays": 3,
            "durationNights": 2,
            "profile": "driving",
            "stops": [
                {
                    "id": "507f1f77bcf86cd799439012",
                    "order": 1,
                    "inputIndex": 0,
                    "mapboxId": "mapbox.poi.1",
                    "name": "Äiá»ƒm Ä‘i 1",
                    "longitude": 105.81,
                    "latitude": 21.01,
                },
                {
                    "id": "507f1f77bcf86cd799439013",
                    "order": 2,
                    "inputIndex": 1,
                    "mapboxId": "mapbox.poi.2",
                    "name": "Äiá»ƒm Ä‘i 2",
                    "longitude": 105.82,
                    "latitude": 21.02,
                },
            ],
            "route": {
                "type": "LineString",
                "coordinates": [[105.81, 21.01], [105.82, 21.02]],
            },
            "distanceMeters": 12000,
            "durationSeconds": 3600,
            "provider": "mapbox",
            "generatedAt": "2026-08-28T10:00:00Z",
            "createdAt": "2026-08-28T10:00:00Z",
            "updatedAt": "2026-08-28T10:00:00Z",
        }
    )
