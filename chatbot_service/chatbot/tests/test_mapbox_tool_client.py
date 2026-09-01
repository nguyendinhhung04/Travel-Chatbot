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
    ItineraryAddStopInput,
    ItineraryCreateInput,
    ItineraryGetInput,
    ItineraryStopInput,
    MapboxCategorySearchInput,
    MapboxCandidateInput,
    MapboxCandidateResolveInput,
    MapboxForwardSearchInput,
    MapboxOptimizationStopInput,
    MapboxOptimizeRouteInput,
    MapboxPlacesDetailsInput,
    MapboxReverseLookupInput,
)


def persisted_itinerary_payload(*, version: int):
    return {
        "id": "507f1f77bcf86cd799439011",
        "userId": "admin",
        "version": version,
        "title": "Hà Nội",
        "destination": "Hà Nội",
        "durationDays": 2,
        "durationNights": 1,
        "profile": "driving",
        "stops": [
            {"id": "507f1f77bcf86cd799439012", "order": 1, "inputIndex": 0, "mapboxId": "poi-a", "name": "A", "longitude": 105.8, "latitude": 21.0},
            {"id": "507f1f77bcf86cd799439013", "order": 2, "inputIndex": 1, "mapboxId": "poi-b", "name": "B", "longitude": 105.9, "latitude": 21.1},
        ],
        "route": {"type": "LineString", "coordinates": [[105.8, 21.0], [105.9, 21.1]]},
        "distanceMeters": 2000,
        "durationSeconds": 600,
        "provider": "mapbox",
        "generatedAt": "2026-08-28T10:00:00Z",
        "createdAt": "2026-08-28T09:00:00Z",
        "updatedAt": "2026-08-28T10:00:00Z",
    }


class MapboxToolClientTests(SimpleTestCase):
    def test_itinerary_create_posts_persistence_contract(self):
        captured = None

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal captured
            captured = (request.method, request.url.path, json.loads(request.content))
            return httpx.Response(201, json=persisted_itinerary_payload(version=1))

        with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
            client = MapboxToolClient(
                base_url="http://tools.test",
                http_client=http_client,
            )
            result = client.create_itinerary(ItineraryCreateInput(
                title="HĂ  Ná»™i",
                destination="HĂ  Ná»™i",
                durationDays=2,
                durationNights=1,
                profile="driving",
                stops=[
                    ItineraryStopInput(
                        mapboxId="poi-a",
                        name="A",
                        longitude=105.8,
                        latitude=21.0,
                    ),
                    ItineraryStopInput(
                        mapboxId="poi-b",
                        name="B",
                        longitude=105.9,
                        latitude=21.1,
                    ),
                ],
            ))

        self.assertTrue(result.success)
        self.assertEqual(result.data.version, 1)
        self.assertEqual(
            captured[:2],
            ("POST", "/api/users/admin/itineraries"),
        )
        self.assertEqual(captured[2]["durationDays"], 2)
        self.assertEqual(captured[2]["stops"][0]["mapboxId"], "poi-a")

    def test_itinerary_add_stop_forwards_version_and_parses_persisted_contract(self):
        captured = None

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal captured
            captured = (request.method, request.url.path, json.loads(request.content))
            return httpx.Response(200, json=persisted_itinerary_payload(version=4))

        with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
            client = MapboxToolClient(
                base_url="http://tools.test",
                http_client=http_client,
            )
            result = client.add_itinerary_stop(ItineraryAddStopInput(
                itineraryId="507f1f77bcf86cd799439011",
                expectedVersion=3,
                stop=ItineraryStopInput(
                    mapboxId="poi-yen-so",
                    name="Công viên Yên Sở",
                    longitude=105.88,
                    latitude=20.96,
                ),
            ))

        self.assertTrue(result.success)
        self.assertEqual(result.data.version, 4)
        self.assertEqual(
            captured[:2],
            ("POST", "/api/users/admin/itineraries/507f1f77bcf86cd799439011/stops"),
        )
        self.assertEqual(captured[2]["expectedVersion"], 3)

    def test_get_itinerary_preserves_backend_conflict_error(self):
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                409,
                json={"errorCode": "version_conflict", "error": "stale"},
            )

        with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
            result = MapboxToolClient(
                base_url="http://tools.test",
                http_client=http_client,
            ).get_itinerary(ItineraryGetInput(
                itineraryId="507f1f77bcf86cd799439011"
            ))

        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "version_conflict")

    def test_optimize_route_posts_alias_contract_and_parses_geometry(self):
        captured = None

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal captured
            captured = (request.url.path, json.loads(request.content))
            return httpx.Response(200, json={
                "success": True,
                "data": {
                    "profile": "driving",
                    "orderedStops": [
                        {"order": 1, "inputIndex": 1, "mapboxId": "poi-2", "name": "B", "longitude": 105.9, "latitude": 21.1},
                        {"order": 2, "inputIndex": 0, "mapboxId": "poi-1", "name": "A", "longitude": 105.8, "latitude": 21.0},
                    ],
                    "geometry": {"type": "LineString", "coordinates": [[105.9, 21.1], [105.8, 21.0]]},
                    "distanceMeters": 1234.5,
                    "durationSeconds": 456.7,
                },
            })

        with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
            result = MapboxToolClient(
                base_url="http://tools.test",
                http_client=http_client,
            ).optimize_route(MapboxOptimizeRouteInput(
                profile="driving",
                stops=[
                    MapboxOptimizationStopInput(mapboxId="poi-1", name="A", longitude=105.8, latitude=21.0),
                    MapboxOptimizationStopInput(mapboxId="poi-2", name="B", longitude=105.9, latitude=21.1),
                ],
            ))

        self.assertTrue(result.success)
        self.assertEqual(captured[0], "/api/chatbot/tools/mapbox-optimize-route")
        self.assertEqual(captured[1]["stops"][0]["mapboxId"], "poi-1")
        self.assertEqual(result.data.ordered_stops[0].input_index, 1)
        self.assertEqual(result.data.geometry.type, "LineString")

    def test_retrieve_place_details_posts_one_batch(self):
        captured = None

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal captured
            captured = (request.url.path, json.loads(request.content))
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "data": {
                        "results": [{
                            "mapboxId": "mapbox.poi.1",
                            "name": "Cafe Example",
                            "fullAddress": "Hà Nội",
                            "primaryCategory": "cafe",
                            "categories": ["cafe"],
                            "openingHours": "Mo-Su 07:00-22:00",
                            "permanentlyClosed": False,
                            "phone": "+84123456789",
                            "website": "https://example.test",
                            "status": "active",
                            "longitude": 105.8,
                            "latitude": 21.0,
                            "popularity": 0.9,
                            "photos": [{
                                "url": "https://images.example.test/place.jpg",
                                "width": 1200,
                                "height": 800,
                                "source": "web",
                            }],
                        }],
                        "missing": [],
                        "unprocessed": [],
                    },
                },
            )

        with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
            result = MapboxToolClient(
                base_url="http://tools.test",
                http_client=http_client,
            ).retrieve_place_details(
                MapboxPlacesDetailsInput(ids=["mapbox.poi.1"])
            )

        self.assertTrue(result.success)
        self.assertEqual(
            captured,
            (
                "/api/chatbot/tools/mapbox-place-details-batch",
                {"ids": ["mapbox.poi.1"]},
            ),
        )
        self.assertEqual(result.data.results[0].primary_category, "cafe")
        self.assertEqual(result.data.results[0].photos[0].width, 1200)

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
