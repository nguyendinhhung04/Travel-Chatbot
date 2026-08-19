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
    MapboxForwardSearchInput,
    MapboxListCategoriesInput,
    MapboxReverseLookupInput,
)


class MapboxToolClientTests(SimpleTestCase):
    def test_four_methods_post_to_expected_endpoints_with_snake_case_json(self):
        requests: list[tuple[str, dict]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append((request.url.path, json.loads(request.content)))
            timeout = request.extensions["timeout"]
            self.assertEqual(timeout["read"], 7)
            self.assertEqual(request.headers["accept"], "application/json")
            if request.url.path.endswith("mapbox-list-categories"):
                return httpx.Response(200, json=CATEGORY_SUCCESS_RESPONSE)
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
            categories = client.list_categories(MapboxListCategoriesInput())
            category_search = client.category_search(
                MapboxCategorySearchInput(
                    category_id="restaurant",
                    proximity="108.2,16.1",
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
        self.assertTrue(categories.success)
        self.assertTrue(category_search.success)
        self.assertTrue(reverse.success)
        self.assertEqual(
            requests,
            [
                (
                    "/api/chatbot/tools/mapbox-forward-search",
                    {"q": "coffee", "poi_category": "cafe", "open_now": True},
                ),
                ("/api/chatbot/tools/mapbox-list-categories", {}),
                (
                    "/api/chatbot/tools/mapbox-category-search",
                    {"proximity": "108.2,16.1", "category_id": "restaurant"},
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
        "results": [],
    },
    "errorCode": None,
    "errorMessage": None,
}

CATEGORY_SUCCESS_RESPONSE = {
    "success": True,
    "data": {
        "attribution": "Mapbox",
        "categories": [],
    },
    "errorCode": None,
    "errorMessage": None,
}
