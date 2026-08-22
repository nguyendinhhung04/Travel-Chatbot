"""HTTP client for the ASP.NET typed Mapbox tool endpoints."""

from __future__ import annotations

import logging
from typing import Any, TypeVar, cast

import httpx
from django.conf import settings
from pydantic import TypeAdapter, ValidationError

from .models import (
    MapboxCategorySearchInput,
    MapboxForwardSearchInput,
    MapboxPlaceToolData,
    MapboxReverseLookupInput,
    ToolResult,
)


logger = logging.getLogger(__name__)

TOOL_TIMEOUT_ERROR = "tool_timeout"
TOOL_UNAVAILABLE_ERROR = "tool_unavailable"
TOOL_INVALID_RESPONSE_ERROR = "tool_invalid_response"

_PLACE_RESULT_ADAPTER = TypeAdapter(ToolResult[MapboxPlaceToolData])
_ResultData = TypeVar("_ResultData")


class MapboxToolClient:
    """Call and validate responses from the ASP.NET typed Mapbox tools."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._base_url = (
            base_url or settings.MAPBOX_TOOL_BASE_URL
        ).strip().rstrip("/")
        self._timeout_seconds = (
            timeout_seconds
            if timeout_seconds is not None
            else settings.MAPBOX_TOOL_TIMEOUT_SECONDS
        )
        self._owns_http_client = http_client is None
        self._http_client = http_client or httpx.Client()

    def forward_search(
        self,
        request: MapboxForwardSearchInput,
    ) -> ToolResult[MapboxPlaceToolData]:
        return self._post(
            "/api/chatbot/tools/mapbox-forward-search",
            request.model_dump(exclude_none=True),
            _PLACE_RESULT_ADAPTER,
        )

    def category_search(
        self,
        request: MapboxCategorySearchInput,
    ) -> ToolResult[MapboxPlaceToolData]:
        return self._post(
            "/api/chatbot/tools/mapbox-category-search",
            request.model_dump(exclude_none=True),
            _PLACE_RESULT_ADAPTER,
        )

    def reverse_lookup(
        self,
        request: MapboxReverseLookupInput,
    ) -> ToolResult[MapboxPlaceToolData]:
        return self._post(
            "/api/chatbot/tools/mapbox-reverse-lookup",
            request.model_dump(exclude_none=True),
            _PLACE_RESULT_ADAPTER,
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
                headers={"Accept": "application/json"},
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
