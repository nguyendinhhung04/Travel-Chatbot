"""Tests for the refined evidence payload sent to Gemini."""

import json

from django.test import SimpleTestCase

from chatbot.evidence_context import build_evidence_context
from chatbot.tool_planner import PlannedToolCall
from chatbot.tools.registry import ToolExecution


class EvidenceContextTests(SimpleTestCase):
    def test_groups_destinations_limits_and_deduplicates_normalized_pois(self):
        calls = [
            PlannedToolCall(
                "search_travel_knowledge",
                {"query": "Hà Nội: đi đâu?"},
                destination="Hà Nội",
                evidence_kind="knowledge",
            ),
            PlannedToolCall(
                "mapbox_forward_search",
                {"q": "Hà Nội"},
                destination="Hà Nội",
                evidence_kind="location",
            ),
            PlannedToolCall(
                "mapbox_category_search",
                {"category_id": "restaurant", "near": "Hà Nội"},
                destination="Hà Nội",
                evidence_kind="poi",
                category_id="restaurant",
            ),
            PlannedToolCall(
                "mapbox_category_search",
                {"category_id": "cafe", "near": "Hà Nội"},
                destination="Hà Nội",
                evidence_kind="poi",
                category_id="cafe",
            ),
        ]
        executions = [
            execution(
                {
                    "chunks": [
                        {
                            "title": f"Kiến thức {index}",
                            "heading": "Ẩm thực",
                            "content": f"Nội dung {index}",
                            "source": "hanoi.md",
                        }
                        for index in range(4)
                    ]
                }
            ),
            execution({"results": [place("city.1", "Hà Nội")]}),
            execution(
                {
                    "results": [
                        place("poi.1", "Quán 1"),
                        place("poi.2", "Quán 2"),
                        place("poi.2", "Quán 2 trùng"),
                        place("poi.3", "Quán 3"),
                        place("poi.4", "Quán 4"),
                    ],
                    "rawResponse": {
                        "response_id": "không gửi sang Gemini",
                        "features": [
                            {
                                "properties": {
                                    "mapbox_id": "poi.1",
                                    "brand": ["Brand thật"],
                                    "metadata": {
                                        "phone": "0123",
                                        "website": "https://example.test",
                                    },
                                }
                            },
                            {
                                "properties": {
                                    "mapbox_id": "raw.only",
                                    "name": "Không thuộc normalized results",
                                    "metadata": {"phone": "0999"},
                                }
                            },
                        ],
                    },
                }
            ),
            execution({"results": [place("poi.1", "Quán 1"), place("poi.5", "Cafe 5")]}),
        ]

        payload = build_evidence_context(calls, executions)

        destination = payload["destinations"][0]
        self.assertEqual(destination["name"], "Hà Nội")
        self.assertEqual(destination["location"]["mapboxId"], "city.1")
        self.assertEqual(len(destination["knowledge"]), 3)
        self.assertEqual(
            [item["mapboxId"] for item in destination["poiGroups"][0]["results"]],
            ["poi.1", "poi.2", "poi.3"],
        )
        self.assertEqual(
            [item["mapboxId"] for item in destination["poiGroups"][1]["results"]],
            ["poi.5"],
        )
        first_poi = destination["poiGroups"][0]["results"][0]
        self.assertEqual(first_poi["phone"], "0123")
        self.assertEqual(first_poi["website"], "https://example.test")
        self.assertNotIn("openingHours", first_poi)
        serialized = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn("rawResponse", serialized)
        self.assertNotIn("response_id", serialized)
        self.assertNotIn("raw.only", serialized)
        self.assertNotIn("0999", serialized)

    def test_marks_empty_and_failed_groups_separately(self):
        calls = [
            PlannedToolCall(
                "mapbox_category_search",
                {},
                destination="Đà Lạt",
                evidence_kind="poi",
                category_id="restaurant",
            ),
            PlannedToolCall(
                "mapbox_category_search",
                {},
                destination="Đà Lạt",
                evidence_kind="poi",
                category_id="lodging",
            ),
        ]
        executions = [
            execution({"results": []}),
            ToolExecution(
                content='{"success":false,"data":null,"errorCode":"tool_unavailable"}',
                sources=(),
                success=False,
                system_failure=True,
                error_code="tool_unavailable",
            ),
        ]

        payload = build_evidence_context(calls, executions)

        groups = payload["destinations"][0]["poiGroups"]
        self.assertEqual(
            [(group["categoryId"], group["status"]) for group in groups],
            [("restaurant", "empty"), ("lodging", "failed")],
        )


def place(mapbox_id, name):
    return {
        "mapboxId": mapbox_id,
        "name": name,
        "featureType": "poi",
        "fullAddress": "Hà Nội",
        "longitude": 105.8,
        "latitude": 21.0,
        "poiCategories": ["Food"],
        "poiCategoryIds": ["restaurant"],
        "operationalStatus": None,
        "distanceMeters": 0,
        "etaMinutes": None,
        "rating": None,
        "popularity": 0,
    }


def execution(data):
    return ToolExecution(
        content=json.dumps(
            {"success": True, "data": data},
            ensure_ascii=False,
        ),
        sources=(),
        success=True,
        system_failure=False,
    )
