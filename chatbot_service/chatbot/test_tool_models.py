"""Tests for structured chatbot tool contracts."""

from django.test import SimpleTestCase
from pydantic import TypeAdapter, ValidationError

from chatbot.tools.models import (
    ChatSource,
    KnowledgeBaseSource,
    MapboxCategorySearchInput,
    MapboxCategoryToolData,
    MapboxForwardSearchInput,
    MapboxPlaceToolData,
    MapboxReverseLookupInput,
    MapboxSource,
    RagChunk,
    RagToolData,
    ToolResult,
)


class ToolInputModelTests(SimpleTestCase):
    def test_forward_search_serializes_snake_case_and_omits_none(self):
        request = MapboxForwardSearchInput(
            q="  coffee  ",
            limit=5,
            poi_category=" cafe ",
            open_now=True,
        )

        self.assertEqual(
            request.model_dump(exclude_none=True),
            {
                "q": "coffee",
                "limit": 5,
                "poi_category": "cafe",
                "open_now": True,
            },
        )

    def test_forward_search_rejects_invalid_required_and_bounded_values(self):
        invalid_values = (
            {"q": " "},
            {"q": "coffee", "limit": 11},
            {"q": "coffee", "minimum_rating": 5.1},
            {"q": "coffee", "rank_strategy": "popularity"},
        )

        for values in invalid_values:
            with self.subTest(values=values):
                with self.assertRaises(ValidationError):
                    MapboxForwardSearchInput.model_validate(values)

    def test_category_and_reverse_inputs_validate_required_fields(self):
        category = MapboxCategorySearchInput(
            category_id=" restaurant ",
            limit=25,
            navigation_profile="walking",
        )
        reverse = MapboxReverseLookupInput(longitude=108.2, latitude=16.1)

        self.assertEqual(category.category_id, "restaurant")
        self.assertEqual(reverse.longitude, 108.2)

        for model, values in (
            (MapboxCategorySearchInput, {"category_id": ""}),
            (MapboxReverseLookupInput, {"longitude": 181, "latitude": 16}),
            (MapboxReverseLookupInput, {"longitude": 108, "latitude": -91}),
        ):
            with self.subTest(model=model.__name__, values=values):
                with self.assertRaises(ValidationError):
                    model.model_validate(values)

    def test_tool_inputs_reject_unknown_fields(self):
        with self.assertRaises(ValidationError):
            MapboxForwardSearchInput.model_validate(
                {"q": "coffee", "access_token": "caller-token"}
            )


class ToolResponseModelTests(SimpleTestCase):
    def test_place_result_parses_camel_case_response(self):
        result = ToolResult[MapboxPlaceToolData].model_validate(
            {
                "success": True,
                "data": {
                    "attribution": "Mapbox",
                    "results": [
                        {
                            "mapboxId": "mapbox.poi.1",
                            "name": "Coffee",
                            "featureType": "poi",
                            "fullAddress": "Da Nang",
                            "longitude": 108.2,
                            "latitude": 16.1,
                            "poiCategories": ["Cafe"],
                            "poiCategoryIds": ["cafe"],
                            "operationalStatus": "active",
                            "distanceMeters": 120.5,
                            "etaMinutes": 3.2,
                        }
                    ],
                    "rawResponse": {
                        "type": "FeatureCollection",
                        "features": [
                            {
                                "properties": {
                                    "mapbox_id": "mapbox.poi.1",
                                    "brand": ["Coffee Brand"],
                                    "metadata": {"phone": "0123456789"},
                                }
                            }
                        ],
                        "attribution": "Mapbox",
                        "response_id": "response-1",
                    },
                },
                "errorCode": None,
                "errorMessage": None,
            }
        )

        self.assertTrue(result.success)
        self.assertEqual(result.data.results[0].mapbox_id, "mapbox.poi.1")
        self.assertEqual(result.data.results[0].distance_meters, 120.5)
        self.assertEqual(
            result.data.raw_response["features"][0]["properties"]["metadata"][
                "phone"
            ],
            "0123456789",
        )
        self.assertEqual(result.data.raw_response["response_id"], "response-1")

    def test_category_result_and_failure_envelope_parse_camel_case(self):
        success = ToolResult[MapboxCategoryToolData].model_validate(
            {
                "success": True,
                "data": {
                    "attribution": "Mapbox",
                    "categories": [
                        {"canonicalId": "restaurant", "name": "Restaurant"}
                    ],
                    "rawResponse": {
                        "listItems": [
                            {
                                "canonical_id": "restaurant",
                                "name": "Restaurant",
                                "icon": "restaurant",
                                "version": "1",
                                "uuid": "category-1",
                            }
                        ],
                        "attribution": "Mapbox",
                        "version": "1",
                    },
                },
            }
        )
        failure = ToolResult[MapboxPlaceToolData].model_validate(
            {
                "success": False,
                "data": None,
                "errorCode": "mapbox_timeout",
                "errorMessage": "Mapbox timed out.",
            }
        )

        self.assertEqual(success.data.categories[0].canonical_id, "restaurant")
        self.assertEqual(
            success.data.raw_response["listItems"][0]["icon"],
            "restaurant",
        )
        self.assertEqual(failure.error_code, "mapbox_timeout")
        self.assertIsNone(failure.data)

    def test_tool_result_rejects_inconsistent_envelopes(self):
        invalid_results = (
            {"success": True, "data": None},
            {"success": False, "data": None},
            {
                "success": False,
                "data": {"attribution": "Mapbox", "results": []},
                "errorCode": "failed",
                "errorMessage": "Failed.",
            },
        )

        for values in invalid_results:
            with self.subTest(values=values):
                with self.assertRaises(ValidationError):
                    ToolResult[MapboxPlaceToolData].model_validate(values)


class RagAndSourceModelTests(SimpleTestCase):
    def test_rag_data_and_discriminated_sources_are_typed(self):
        source = KnowledgeBaseSource(title="Hue", source="hue/overview.md")
        rag_data = RagToolData(
            chunks=[
                RagChunk(
                    content="Travel content",
                    title=source.title,
                    source=source.source,
                    heading="Overview",
                )
            ],
            sources=[source],
        )
        adapter = TypeAdapter(ChatSource)
        mapbox_source = adapter.validate_python(
            {"type": "mapbox", "attribution": "Mapbox"}
        )

        self.assertEqual(rag_data.chunks[0].heading, "Overview")
        self.assertIsInstance(mapbox_source, MapboxSource)
        self.assertEqual(mapbox_source.source, "Mapbox Search API")
