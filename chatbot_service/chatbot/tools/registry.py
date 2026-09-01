"""Allowlisted execution boundary for travel chatbot tools."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError

from .mapbox_client import (
    TOOL_INVALID_RESPONSE_ERROR,
    TOOL_TIMEOUT_ERROR,
    TOOL_UNAVAILABLE_ERROR,
    MapboxToolClient,
)
from .models import (
    ChatSource,
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
    MapboxPlaceToolData,
    MapboxReverseLookupInput,
    MapboxSource,
    RagToolData,
    SearchTravelKnowledgeInput,
    ToolResult,
)
from .rag_tool import (
    RAG_UNAVAILABLE_ERROR,
    SEARCH_TRAVEL_KNOWLEDGE_TOOL_NAME,
    search_travel_knowledge,
)


logger = logging.getLogger(__name__)

MAPBOX_FORWARD_SEARCH_TOOL_NAME = "mapbox_forward_search"
MAPBOX_CATEGORY_SEARCH_TOOL_NAME = "mapbox_category_search"
MAPBOX_REVERSE_LOOKUP_TOOL_NAME = "mapbox_reverse_lookup"
MAPBOX_RESOLVE_CANDIDATES_TOOL_NAME = "mapbox_resolve_candidates"
MAPBOX_OPTIMIZE_ROUTE_TOOL_NAME = "mapbox_optimize_route"
GET_ITINERARY_TOOL_NAME = "get_itinerary"
ADD_ITINERARY_STOP_TOOL_NAME = "add_itinerary_stop"
CREATE_ITINERARY_TOOL_NAME = "create_itinerary"
UNKNOWN_TOOL_ERROR = "unknown_tool"
INVALID_ARGUMENTS_ERROR = "invalid_arguments"
TOOL_EXECUTION_ERROR = "tool_execution_error"

SYSTEM_FAILURE_CODES = {
    RAG_UNAVAILABLE_ERROR,
    TOOL_TIMEOUT_ERROR,
    TOOL_UNAVAILABLE_ERROR,
    TOOL_INVALID_RESPONSE_ERROR,
    "mapbox_timeout",
    "mapbox_unavailable",
    "mapbox_http_error",
    "mapbox_invalid_response",
    "database_unavailable",
    TOOL_EXECUTION_ERROR,
}


@dataclass(frozen=True)
class ToolExecution:
    """Serialized tool response plus metadata needed by orchestration."""

    content: str
    sources: tuple[ChatSource, ...]
    success: bool
    system_failure: bool
    error_code: str | None = None


@dataclass(frozen=True)
class ToolDefinition:
    """Public description of one allowlisted backend tool."""

    name: str
    description: str
    input_model: type[BaseModel]


@dataclass(frozen=True)
class _RegisteredTool:
    definition: ToolDefinition
    handler: Callable[[BaseModel], ToolResult[Any]]


class ToolRegistry:
    """Validate and execute the allowlisted tools used by the chatbot runtime."""

    def __init__(
        self,
        mapbox_client: MapboxToolClient,
        *,
        rag_retriever: Any | None = None,
        rag_top_k: int | None = None,
    ) -> None:
        self._mapbox_client = mapbox_client
        self._rag_retriever = rag_retriever
        self._rag_top_k = rag_top_k
        self._tools = self._build_registered_tools()

    @property
    def definitions(self) -> tuple[ToolDefinition, ...]:
        return tuple(tool.definition for tool in self._tools.values())

    @property
    def names(self) -> frozenset[str]:
        return frozenset(self._tools)

    def execute(self, name: str, arguments: Any) -> ToolExecution:
        registered = self._tools.get(name)
        if registered is None:
            return self._failure(
                UNKNOWN_TOOL_ERROR,
                f"Tool '{name}' không được phép sử dụng.",
            )

        if not isinstance(arguments, Mapping):
            return self._failure(
                INVALID_ARGUMENTS_ERROR,
                "Đối số tool phải là một JSON object.",
            )

        try:
            request = registered.definition.input_model.model_validate(
                dict(arguments)
            )
        except ValidationError as error:
            details = self._format_validation_errors(error)
            return self._failure(
                INVALID_ARGUMENTS_ERROR,
                f"Đối số tool không hợp lệ: {details}",
            )

        try:
            result = registered.handler(request)
        except Exception as error:
            logger.warning(
                "Chatbot tool execution failed: %s (%s)",
                name,
                type(error).__name__,
            )
            return self._failure(
                TOOL_EXECUTION_ERROR,
                "Không thể thực thi tool do lỗi hệ thống.",
                system_failure=True,
            )

        sources = self._sources_for_result(result)
        error_code = result.error_code
        return ToolExecution(
            content=result.model_dump_json(by_alias=True, exclude_none=True),
            sources=sources,
            success=result.success,
            system_failure=(
                not result.success and error_code in SYSTEM_FAILURE_CODES
            ),
            error_code=error_code,
        )

    def _build_registered_tools(self) -> dict[str, _RegisteredTool]:
        tools = [
            _RegisteredTool(
                definition=ToolDefinition(
                    name=CREATE_ITINERARY_TOOL_NAME,
                    description=(
                        "Táº¡o má»™t lá»‹ch trÃ¬nh má»›i tá»« cÃ¡c POI Ä‘Ã£ xÃ¡c minh, tá»‘i Æ°u route vÃ  lÆ°u vÃ o backend."
                    ),
                    input_model=ItineraryCreateInput,
                ),
                handler=self._mapbox_client.create_itinerary,
            ),
            _RegisteredTool(
                definition=ToolDefinition(
                    name=GET_ITINERARY_TOOL_NAME,
                    description="Lấy lịch trình admin đang mở hoặc mới nhất.",
                    input_model=ItineraryGetInput,
                ),
                handler=self._mapbox_client.get_itinerary,
            ),
            _RegisteredTool(
                definition=ToolDefinition(
                    name=ADD_ITINERARY_STOP_TOOL_NAME,
                    description=(
                        "Thêm một POI đã xác minh, tối ưu lại route và lưu phiên bản mới."
                    ),
                    input_model=ItineraryAddStopInput,
                ),
                handler=self._mapbox_client.add_itinerary_stop,
            ),
            _RegisteredTool(
                definition=ToolDefinition(
                    name=MAPBOX_OPTIMIZE_ROUTE_TOOL_NAME,
                    description=(
                        "Tối ưu thứ tự và tuyến đường qua 2-12 POI đã được backend "
                        "xác minh cho yêu cầu xây dựng lịch trình."
                    ),
                    input_model=MapboxOptimizeRouteInput,
                ),
                handler=self._mapbox_client.optimize_route,
            ),
            _RegisteredTool(
                definition=ToolDefinition(
                    name=MAPBOX_RESOLVE_CANDIDATES_TOOL_NAME,
                    description=(
                        "Xác minh theo batch các candidate do Gemini đề xuất, matching "
                        "với Mapbox và trả dữ liệu địa điểm đã chuẩn hóa."
                    ),
                    input_model=MapboxCandidateResolveInput,
                ),
                handler=self._mapbox_client.resolve_candidates,
            ),
            _RegisteredTool(
                definition=ToolDefinition(
                    name=SEARCH_TRAVEL_KNOWLEDGE_TOOL_NAME,
                    description=(
                        "Tra cứu Knowledge Base cho kiến thức, kinh nghiệm, "
                        "ngân sách, di chuyển và tư vấn lịch trình dạng văn bản."
                    ),
                    input_model=SearchTravelKnowledgeInput,
                ),
                handler=lambda request: search_travel_knowledge(
                    request,
                    retriever=self._rag_retriever,
                    top_k=self._rag_top_k,
                ),
            ),
            _RegisteredTool(
                definition=ToolDefinition(
                    name=MAPBOX_FORWARD_SEARCH_TOOL_NAME,
                    description=(
                        "Tìm tên riêng, địa chỉ hoặc POI cụ thể đã được semantic "
                        "interpretation nhận diện."
                    ),
                    input_model=MapboxForwardSearchInput,
                ),
                handler=self._mapbox_client.forward_search,
            ),
            _RegisteredTool(
                definition=ToolDefinition(
                    name=MAPBOX_CATEGORY_SEARCH_TOOL_NAME,
                    description=(
                        "Khám phá POI bằng canonical category ID do category resolver "
                        "của backend chọn từ travel domain."
                    ),
                    input_model=MapboxCategorySearchInput,
                ),
                handler=self._mapbox_client.category_search,
            ),
            _RegisteredTool(
                definition=ToolDefinition(
                    name=MAPBOX_REVERSE_LOOKUP_TOOL_NAME,
                    description=(
                        "Tra cứu địa điểm hoặc địa chỉ quanh một cặp longitude, "
                        "latitude hợp lệ."
                    ),
                    input_model=MapboxReverseLookupInput,
                ),
                handler=self._mapbox_client.reverse_lookup,
            ),
        ]
        return {tool.definition.name: tool for tool in tools}

    @staticmethod
    def _sources_for_result(
        result: ToolResult[Any],
    ) -> tuple[ChatSource, ...]:
        if not result.success or result.data is None:
            return ()
        if isinstance(result.data, RagToolData):
            return tuple(result.data.sources)
        if isinstance(result.data, (MapboxPlaceSummaryData, MapboxPlaceToolData)):
            return (MapboxSource(attribution=result.data.attribution),)
        if isinstance(result.data, MapboxCandidateResolutionData):
            return (MapboxSource(attribution=result.data.attribution),)
        if isinstance(result.data, MapboxOptimizedRouteData):
            return (MapboxSource(attribution="© Mapbox"),)
        if isinstance(result.data, ItineraryData):
            return (MapboxSource(attribution="© Mapbox"),)
        return ()

    @staticmethod
    def _format_validation_errors(error: ValidationError) -> str:
        details: list[str] = []
        for item in error.errors(include_url=False, include_input=False)[:3]:
            location = ".".join(str(part) for part in item["loc"])
            prefix = f"{location}: " if location else ""
            details.append(f"{prefix}{item['msg']}")
        return "; ".join(details)

    @staticmethod
    def _failure(
        error_code: str,
        error_message: str,
        *,
        system_failure: bool = False,
    ) -> ToolExecution:
        content = json.dumps(
            {
                "success": False,
                "data": None,
                "errorCode": error_code,
                "errorMessage": error_message,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return ToolExecution(
            content=content,
            sources=(),
            success=False,
            system_failure=system_failure,
            error_code=error_code,
        )


__all__ = [
    "ADD_ITINERARY_STOP_TOOL_NAME",
    "CREATE_ITINERARY_TOOL_NAME",
    "GET_ITINERARY_TOOL_NAME",
    "INVALID_ARGUMENTS_ERROR",
    "MAPBOX_CATEGORY_SEARCH_TOOL_NAME",
    "MAPBOX_FORWARD_SEARCH_TOOL_NAME",
    "MAPBOX_OPTIMIZE_ROUTE_TOOL_NAME",
    "MAPBOX_REVERSE_LOOKUP_TOOL_NAME",
    "MAPBOX_RESOLVE_CANDIDATES_TOOL_NAME",
    "SEARCH_TRAVEL_KNOWLEDGE_TOOL_NAME",
    "TOOL_EXECUTION_ERROR",
    "ToolDefinition",
    "ToolExecution",
    "ToolRegistry",
    "UNKNOWN_TOOL_ERROR",
]
