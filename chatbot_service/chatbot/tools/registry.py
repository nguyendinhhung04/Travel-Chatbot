"""Allowlisted Gemini tool declarations and execution handlers."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, ValidationError

from .mapbox_client import (
    TOOL_INVALID_RESPONSE_ERROR,
    TOOL_TIMEOUT_ERROR,
    TOOL_UNAVAILABLE_ERROR,
    MapboxToolClient,
)
from .models import (
    ChatSource,
    MapboxCategorySearchInput,
    MapboxCategoryToolData,
    MapboxForwardSearchInput,
    MapboxListCategoriesInput,
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
MAPBOX_LIST_CATEGORIES_TOOL_NAME = "mapbox_list_categories"
MAPBOX_CATEGORY_SEARCH_TOOL_NAME = "mapbox_category_search"
MAPBOX_REVERSE_LOOKUP_TOOL_NAME = "mapbox_reverse_lookup"
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
    TOOL_EXECUTION_ERROR,
}


@dataclass(frozen=True)
class ToolExecution:
    """Serialized tool response plus metadata needed by the orchestrator."""

    content: str
    sources: tuple[ChatSource, ...]
    success: bool
    system_failure: bool
    error_code: str | None = None


@dataclass(frozen=True)
class _RegisteredTool:
    name: str
    description: str
    input_model: type[BaseModel]
    handler: Callable[[BaseModel], ToolResult[Any]]


class ToolRegistry:
    """Expose exactly the five tools allowed by the travel chatbot."""

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
        self._langchain_tools = [
            self._build_langchain_tool(tool) for tool in self._tools.values()
        ]

    @property
    def langchain_tools(self) -> list[StructuredTool]:
        return list(self._langchain_tools)

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
            request = registered.input_model.model_validate(dict(arguments))
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
            content=result.model_dump_json(by_alias=True),
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
                name=SEARCH_TRAVEL_KNOWLEDGE_TOOL_NAME,
                description=(
                    "Tra cứu Knowledge Base du lịch nội bộ. Dùng cho lịch sử, văn hóa, "
                    "hoạt động, kinh nghiệm, lịch trình và thông tin tư vấn du lịch."
                ),
                input_model=SearchTravelKnowledgeInput,
                handler=lambda request: search_travel_knowledge(
                    request,
                    retriever=self._rag_retriever,
                    top_k=self._rag_top_k,
                ),
            ),
            _RegisteredTool(
                name=MAPBOX_FORWARD_SEARCH_TOOL_NAME,
                description=(
                    "Tìm địa điểm, địa chỉ hoặc POI bằng văn bản. Dùng khi người dùng "
                    "nêu tên nơi cần tìm hoặc muốn tìm một địa điểm cụ thể."
                ),
                input_model=MapboxForwardSearchInput,
                handler=self._mapbox_client.forward_search,
            ),
            _RegisteredTool(
                name=MAPBOX_LIST_CATEGORIES_TOOL_NAME,
                description=(
                    "Lấy danh sách canonical category ID của Mapbox. Gọi tool này trước "
                    "mapbox_category_search khi chưa biết category_id chính xác."
                ),
                input_model=MapboxListCategoriesInput,
                handler=self._mapbox_client.list_categories,
            ),
            _RegisteredTool(
                name=MAPBOX_CATEGORY_SEARCH_TOOL_NAME,
                description=(
                    "Tìm POI theo canonical category_id của Mapbox và các bộ lọc vị trí. "
                    "category_id nên lấy từ mapbox_list_categories."
                ),
                input_model=MapboxCategorySearchInput,
                handler=self._mapbox_client.category_search,
            ),
            _RegisteredTool(
                name=MAPBOX_REVERSE_LOOKUP_TOOL_NAME,
                description=(
                    "Tra cứu địa điểm hoặc địa chỉ quanh một cặp longitude, latitude. "
                    "Chỉ dùng khi đã có tọa độ hợp lệ."
                ),
                input_model=MapboxReverseLookupInput,
                handler=self._mapbox_client.reverse_lookup,
            ),
        ]
        return {tool.name: tool for tool in tools}

    def _build_langchain_tool(self, registered: _RegisteredTool) -> StructuredTool:
        def invoke_registered_tool(**arguments: Any) -> str:
            return self.execute(registered.name, arguments).content

        return StructuredTool.from_function(
            func=invoke_registered_tool,
            name=registered.name,
            description=registered.description,
            args_schema=registered.input_model,
            infer_schema=False,
        )

    @staticmethod
    def _sources_for_result(
        result: ToolResult[Any],
    ) -> tuple[ChatSource, ...]:
        if not result.success or result.data is None:
            return ()
        if isinstance(result.data, RagToolData):
            return tuple(result.data.sources)
        if isinstance(result.data, (MapboxPlaceToolData, MapboxCategoryToolData)):
            return (MapboxSource(attribution=result.data.attribution),)
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
    "INVALID_ARGUMENTS_ERROR",
    "MAPBOX_CATEGORY_SEARCH_TOOL_NAME",
    "MAPBOX_FORWARD_SEARCH_TOOL_NAME",
    "MAPBOX_LIST_CATEGORIES_TOOL_NAME",
    "MAPBOX_REVERSE_LOOKUP_TOOL_NAME",
    "SEARCH_TRAVEL_KNOWLEDGE_TOOL_NAME",
    "TOOL_EXECUTION_ERROR",
    "ToolExecution",
    "ToolRegistry",
    "UNKNOWN_TOOL_ERROR",
]
