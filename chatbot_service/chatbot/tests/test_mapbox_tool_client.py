"""Tests for the ASP.NET typed Mapbox tool HTTP client."""

import json

import httpx
from django.test import SimpleTestCase

from chatbot.tools.mapbox_client import (
    TOOL_INVALID_RESPONSE_ERROR,
    TOOL_TIMEOUT_ERROR,
    TOOL_UNAVAILABLE_ERROR,
    MapboxToolClient,
)
from chatbot.tools.models import (
    MapboxCategorySearchInput,
    MapboxCandidateInput,
    MapboxCandidateResolveInput,
    MapboxForwardSearchInput,
    MapboxReverseLookupInput,
)


class MapboxToolClientTests(SimpleTestCase):
    def test_resolve_candidates_posts_batch_contract(self):
        captured = None

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal captured
            captured = (request.url.path, json.loads(request.content))
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "data": {
                        "attribution": "Mapbox",
                        "results": [],
                        "additionalPlaces": [],
                    },
                    "errorCode": None,
                    "errorMessage": None,
                },
            )

        with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
            result = MapboxToolClient(
                base_url="http://tools.test",
                http_client=http_client,
            ).resolve_candidates(
                MapboxCandidateResolveInput(
                    longitude=108.44,
                    latitude=11.94,
                    candidates=[
                        MapboxCandidateInput(
                            candidateId="candidate-1",
                            name="Hồ Xuân Hương",
                            aliases=["Xuan Huong Lake"],
                            categoryHints=["lake"],
                        )
                    ],
                    categoryId="tourist_attraction",
                )
            )

        self.assertTrue(result.success)
        self.assertEqual(
            captured,
            (
                "/api/chatbot/tools/mapbox-resolve-candidates",
                {
                    "longitude": 108.44,
                    "latitude": 11.94,
                    "candidates": [
                        {
                            "candidateId": "candidate-1",
                            "name": "Hồ Xuân Hương",
                            "aliases": ["Xuan Huong Lake"],
                            "categoryHints": ["lake"],
                        }
                    ],
                    "categoryId": "tourist_attraction",
                },
            ),
        )

    def test_three_methods_post_to_expected_endpoints_with_snake_case_json(self):
        requests: list[tuple[str, dict]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append((request.url.path, json.loads(request.content)))
            timeout = request.extensions["timeout"]
            self.assertEqual(timeout["read"], 7)
            self.assertEqual(request.headers["accept"], "application/json")
            return httpx.Response(200, json=PLACE_SUCCESS_RESPONSE)

        with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
            client = MapboxToolClient(
                base_url="http://tools.test/",
                timeout_seconds=7,
                http_client=http_client,
            )

            forward = client.forward_search(
                MapboxForwardSearchInput(
                    q="coffee",
                    poi_category="cafe",
                    open_now=True,
                )
            )
            category_search = client.category_search(
                MapboxCategorySearchInput(
                    category_id="restaurant",
                    proximity="108.2,16.1",
                    minimum_rating=4,
                )
            )
            reverse = client.reverse_lookup(
                MapboxReverseLookupInput(
                    longitude=108.2,
                    latitude=16.1,
                    show_closed_pois=False,
                )
            )

        self.assertTrue(forward.success)
        self.assertTrue(category_search.success)
        self.assertTrue(reverse.success)
        self.assertEqual(forward.data.results[0].mapbox_id, "mapbox.cafe.1")
        self.assertEqual(forward.data.results[0].distance_meters, 120.0)
        self.assertEqual(
            requests,
            [
                (
                    "/api/chatbot/tools/mapbox-forward-search",
                    {"q": "coffee", "poi_category": "cafe", "open_now": True},
                ),
                (
                    "/api/chatbot/tools/mapbox-category-search",
                    {
                        "proximity": "108.2,16.1",
                        "category_id": "restaurant",
                        "minimum_rating": 4.0,
                    },
                ),
                (
                    "/api/chatbot/tools/mapbox-reverse-lookup",
                    {
                        "longitude": 108.2,
                        "latitude": 16.1,
                        "show_closed_pois": False,
                    },
                ),
            ],
        )

    def test_non_success_http_response_preserves_csharp_tool_error(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                504,
                json={
                    "success": False,
                    "data": None,
                    "errorCode": "mapbox_timeout",
                    "errorMessage": "Mapbox API timed out.",
                },
            )

        result = self.call_forward(handler)

        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "mapbox_timeout")
        self.assertEqual(result.error_message, "Mapbox API timed out.")

    def test_timeout_is_returned_as_safe_structured_failure(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("provider-secret", request=request)

        with self.assertLogs("chatbot.tools.mapbox_client", level="WARNING"):
            result = self.call_forward(handler)

        self.assertFalse(result.success)
        self.assertEqual(result.error_code, TOOL_TIMEOUT_ERROR)
        self.assertNotIn("provider-secret", result.error_message)

    def test_connection_error_is_returned_as_safe_structured_failure(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("internal-host-secret", request=request)

        with self.assertLogs("chatbot.tools.mapbox_client", level="WARNING"):
            result = self.call_forward(handler)

        self.assertFalse(result.success)
        self.assertEqual(result.error_code, TOOL_UNAVAILABLE_ERROR)
        self.assertNotIn("internal-host-secret", result.error_message)

    def test_invalid_json_and_contract_are_returned_as_structured_failure(self):
        responses = (
            httpx.Response(502, content=b"not-json"),
            httpx.Response(200, json={"success": True, "data": None}),
            httpx.Response(400, json={"title": "Validation failed"}),
        )

        for response in responses:
            with self.subTest(response=response):
                with self.assertLogs(
                    "chatbot.tools.mapbox_client",
                    level="WARNING",
                ):
                    result = self.call_forward(
                        lambda request, value=response: value
                    )

                self.assertFalse(result.success)
                self.assertEqual(result.error_code, TOOL_INVALID_RESPONSE_ERROR)
                self.assertIsNone(result.data)

    def call_forward(self, handler):
        with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
            client = MapboxToolClient(
                base_url="http://tools.test",
                timeout_seconds=5,
                http_client=http_client,
            )
            return client.forward_search(MapboxForwardSearchInput(q="coffee"))


PLACE_SUCCESS_RESPONSE = {
    "success": True,
    "data": {
        "attribution": "Mapbox",
        "results": [
            {
                "mapboxId": "mapbox.cafe.1",
                "name": "Cafe Example",
                "fullAddress": "Hà Nội",
                "longitude": 105.8,
                "latitude": 21.0,
                "poiCategories": ["cafe"],
                "distanceMeters": 120.0,
                "rating": 4.5,
            }
        ],
    },
    "errorCode": None,
    "errorMessage": None,
}
