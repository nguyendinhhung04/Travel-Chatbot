"""HTTP client for the ASP.NET typed Mapbox tool endpoints."""

from __future__ import annotations

import logging
from typing import Any, TypeVar, cast

import httpx
from django.conf import settings
from pydantic import TypeAdapter, ValidationError

from .models import (
    ItineraryAddStopInput,
    ItineraryCreateInput,
    ItineraryData,
    ItineraryGetInput,
    MapboxCategorySearchInput,
    MapboxCandidateResolutionData,
    MapboxCandidateResolveInput,
    MapboxForwardSearchInput,
    MapboxOptimizeRouteInput,
    MapboxOptimizedRouteData,
    MapboxPlaceSummaryData,
    MapboxPlacesDetailsData,
    MapboxPlacesDetailsInput,
    MapboxReverseLookupInput,
    ToolResult,
)


logger = logging.getLogger(__name__)

TOOL_TIMEOUT_ERROR = "tool_timeout"
TOOL_UNAVAILABLE_ERROR = "tool_unavailable"
TOOL_INVALID_RESPONSE_ERROR = "tool_invalid_response"

_PLACE_SUMMARY_RESULT_ADAPTER = TypeAdapter(ToolResult[MapboxPlaceSummaryData])
_CANDIDATE_RESULT_ADAPTER = TypeAdapter(ToolResult[MapboxCandidateResolutionData])
_PLACE_DETAILS_RESULT_ADAPTER = TypeAdapter(ToolResult[MapboxPlacesDetailsData])
_OPTIMIZED_ROUTE_RESULT_ADAPTER = TypeAdapter(ToolResult[MapboxOptimizedRouteData])
_ITINERARY_ADAPTER = TypeAdapter(ItineraryData)
_ResultData = TypeVar("_ResultData")


class MapboxToolClient:
    """Call and validate responses from the ASP.NET typed Mapbox tools."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
        http_client: httpx.Client | None = None,
        authorization: str | None = None,
    ) -> None:
        self._base_url = (
            base_url or settings.MAPBOX_TOOL_BASE_URL
        ).strip().rstrip("/")
        self._timeout_seconds = (
            timeout_seconds
            if timeout_seconds is not None
            else settings.MAPBOX_TOOL_TIMEOUT_SECONDS
        )
        self._authorization = authorization.strip() if authorization else None
        self._owns_http_client = http_client is None
        self._http_client = http_client or httpx.Client()

    def forward_search(
        self,
        request: MapboxForwardSearchInput,
    ) -> ToolResult[MapboxPlaceSummaryData]:
        return self._post(
            "/api/chatbot/tools/mapbox-forward-search",
            request.model_dump(exclude_none=True),
            _PLACE_SUMMARY_RESULT_ADAPTER,
        )

    def category_search(
        self,
        request: MapboxCategorySearchInput,
    ) -> ToolResult[MapboxPlaceSummaryData]:
        return self._post(
            "/api/chatbot/tools/mapbox-category-search",
            request.model_dump(exclude_none=True),
            _PLACE_SUMMARY_RESULT_ADAPTER,
        )

    def reverse_lookup(
        self,
        request: MapboxReverseLookupInput,
    ) -> ToolResult[MapboxPlaceSummaryData]:
        return self._post(
            "/api/chatbot/tools/mapbox-reverse-lookup",
            request.model_dump(exclude_none=True),
            _PLACE_SUMMARY_RESULT_ADAPTER,
        )

    def resolve_candidates(
        self,
        request: MapboxCandidateResolveInput,
    ) -> ToolResult[MapboxCandidateResolutionData]:
        return self._post(
            "/api/chatbot/tools/mapbox-resolve-candidates",
            request.model_dump(mode="json", by_alias=True, exclude_none=True),
            _CANDIDATE_RESULT_ADAPTER,
        )

    def retrieve_place_details(
        self,
        request: MapboxPlacesDetailsInput,
    ) -> ToolResult[MapboxPlacesDetailsData]:
        return self._post(
            "/api/chatbot/tools/mapbox-place-details-batch",
            request.model_dump(mode="json"),
            _PLACE_DETAILS_RESULT_ADAPTER,
        )

    def optimize_route(
        self,
        request: MapboxOptimizeRouteInput,
    ) -> ToolResult[MapboxOptimizedRouteData]:
        return self._post(
            "/api/chatbot/tools/mapbox-optimize-route",
            request.model_dump(mode="json", by_alias=True),
            _OPTIMIZED_ROUTE_RESULT_ADAPTER,
        )

    def get_itinerary(self, request: ItineraryGetInput) -> ToolResult[ItineraryData]:
        endpoint = (
            f"/api/itineraries/{request.itinerary_id}"
            if request.itinerary_id
            else "/api/itineraries/latest"
        )
        return self._itinerary_request("GET", endpoint)

    def create_itinerary(
        self,
        request: ItineraryCreateInput,
    ) -> ToolResult[ItineraryData]:
        return self._itinerary_request(
            "POST",
            "/api/itineraries",
            request.model_dump(mode="json", by_alias=True),
        )

    def add_itinerary_stop(
        self,
        request: ItineraryAddStopInput,
    ) -> ToolResult[ItineraryData]:
        return self._itinerary_request(
            "POST",
            f"/api/itineraries/{request.itinerary_id}/stops",
            {
                "stop": request.stop.model_dump(mode="json", by_alias=True),
                "expectedVersion": request.expected_version,
                "position": request.position,
            },
        )

    def close(self) -> None:
        if self._owns_http_client:
            self._http_client.close()

    def __enter__(self) -> MapboxToolClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _post(
        self,
        endpoint: str,
        payload: dict[str, Any],
        result_adapter: TypeAdapter[ToolResult[_ResultData]],
    ) -> ToolResult[_ResultData]:
        url = f"{self._base_url}{endpoint}"
        try:
            response = self._http_client.post(
                url,
                json=payload,
                headers=self._headers(),
                timeout=self._timeout_seconds,
            )
        except httpx.TimeoutException:
            logger.warning("Typed Mapbox tool request timed out: %s", endpoint)
            return self._failure(
                TOOL_TIMEOUT_ERROR,
                "Dịch vụ Mapbox tool hết thời gian phản hồi.",
            )
        except httpx.RequestError as error:
            logger.warning(
                "Typed Mapbox tool request failed: %s (%s)",
                endpoint,
                type(error).__name__,
            )
            return self._failure(
                TOOL_UNAVAILABLE_ERROR,
                "Không thể kết nối đến dịch vụ Mapbox tool.",
            )

        try:
            response_payload = response.json()
            return result_adapter.validate_python(response_payload)
        except (ValueError, ValidationError) as error:
            logger.warning(
                "Typed Mapbox tool returned an invalid response: %s, status=%s (%s)",
                endpoint,
                response.status_code,
                type(error).__name__,
            )
            return self._failure(
                TOOL_INVALID_RESPONSE_ERROR,
                "Dịch vụ Mapbox tool trả về dữ liệu không hợp lệ.",
            )

    def _itinerary_request(
        self,
        method: str,
        endpoint: str,
        payload: dict[str, Any] | None = None,
    ) -> ToolResult[ItineraryData]:
        try:
            response = self._http_client.request(
                method,
                f"{self._base_url}{endpoint}",
                json=payload,
                headers=self._headers(),
                timeout=self._timeout_seconds,
            )
        except httpx.TimeoutException:
            return self._failure(
                TOOL_TIMEOUT_ERROR,
                "Dịch vụ lịch trình hết thời gian phản hồi.",
            )
        except httpx.RequestError:
            return self._failure(
                TOOL_UNAVAILABLE_ERROR,
                "Không thể kết nối đến dịch vụ lịch trình.",
            )

        try:
            body = response.json()
        except ValueError:
            return self._failure(
                TOOL_INVALID_RESPONSE_ERROR,
                "Dịch vụ lịch trình trả về dữ liệu không hợp lệ.",
            )
        if response.is_success:
            try:
                return ToolResult[ItineraryData](
                    success=True,
                    data=_ITINERARY_ADAPTER.validate_python(body),
                )
            except ValidationError:
                return self._failure(
                    TOOL_INVALID_RESPONSE_ERROR,
                    "Dịch vụ lịch trình trả về dữ liệu không hợp lệ.",
                )

        error_code = (
            body.get("errorCode")
            if isinstance(body, dict) and isinstance(body.get("errorCode"), str)
            else "itinerary_http_error"
        )
        error_message = (
            body.get("error")
            if isinstance(body, dict) and isinstance(body.get("error"), str)
            else "Yêu cầu lịch trình không thành công."
        )
        return ToolResult[ItineraryData](
            success=False,
            error_code=error_code,
            error_message=error_message,
        )

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self._authorization:
            headers["Authorization"] = self._authorization
        return headers

    @staticmethod
    def _failure(
        error_code: str,
        error_message: str,
    ) -> ToolResult[_ResultData]:
        result = ToolResult[Any](
            success=False,
            error_code=error_code,
            error_message=error_message,
        )
        return cast(ToolResult[_ResultData], result)


__all__ = ["MapboxToolClient"]
