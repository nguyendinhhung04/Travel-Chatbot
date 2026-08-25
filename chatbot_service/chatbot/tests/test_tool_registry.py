"""Tests for backend-selected tool definitions and allowlisted execution."""

import json
from unittest.mock import MagicMock

from django.test import SimpleTestCase
from langchain_core.documents import Document

from chatbot.tools.models import (
    MapboxPlaceToolData,
    RagToolData,
    ToolResult,
)
from chatbot.tools.registry import (
    INVALID_ARGUMENTS_ERROR,
    MAPBOX_FORWARD_SEARCH_TOOL_NAME,
    SEARCH_TRAVEL_KNOWLEDGE_TOOL_NAME,
    TOOL_EXECUTION_ERROR,
    UNKNOWN_TOOL_ERROR,
    ToolRegistry,
)


class ToolRegistryTests(SimpleTestCase):
    def setUp(self):
        self.mapbox_client = MagicMock()
        self.registry = ToolRegistry(self.mapbox_client)

    def test_registry_exposes_backend_selected_tools(self):
        self.assertEqual(
            self.registry.names,
            {
                "search_travel_knowledge",
                "mapbox_forward_search",
                "mapbox_category_search",
                "mapbox_reverse_lookup",
                "mapbox_resolve_candidates",
            },
        )
        tools = {tool.name: tool for tool in self.registry.definitions}
        self.assertEqual(set(tools), self.registry.names)
        self.assertIn("q", tools["mapbox_forward_search"].input_model.model_fields)
        self.assertIn(
            "category_id",
            tools["mapbox_category_search"].input_model.model_fields,
        )
        self.assertIn(
            "tên riêng",
            tools["mapbox_forward_search"].description,
        )
        self.assertIn(
            "category resolver",
            tools["mapbox_category_search"].description,
        )
        self.assertIn(
            "Không truyền nguyên câu hỏi tư vấn",
            tools["mapbox_forward_search"].input_model.model_fields[
                "q"
            ].description,
        )
        self.assertIn(
            "category resolver",
            tools["mapbox_category_search"].input_model.model_fields[
                "category_id"
            ].description,
        )

    def test_unknown_tool_and_invalid_arguments_never_call_handlers(self):
        unknown = self.registry.execute("delete_everything", {})
        invalid = self.registry.execute(
            MAPBOX_FORWARD_SEARCH_TOOL_NAME,
            {"q": "coffee", "limit": 100},
        )

        self.assertEqual(unknown.error_code, UNKNOWN_TOOL_ERROR)
        self.assertEqual(invalid.error_code, INVALID_ARGUMENTS_ERROR)
        self.assertFalse(unknown.system_failure)
        self.assertFalse(invalid.system_failure)
        self.mapbox_client.forward_search.assert_not_called()
        self.assertEqual(json.loads(invalid.content)["success"], False)

    def test_rag_execution_returns_typed_content_and_knowledge_source(self):
        retriever = MagicMock()
        retriever.invoke.return_value = [
            Document(
                page_content="Nội dung Huế",
                metadata={"title": "Huế", "source": "hue.md"},
            )
        ]
        registry = ToolRegistry(self.mapbox_client, rag_retriever=retriever)

        execution = registry.execute(
            SEARCH_TRAVEL_KNOWLEDGE_TOOL_NAME,
            {"query": "Huế có gì?"},
        )

        self.assertTrue(execution.success)
        self.assertFalse(execution.system_failure)
        self.assertEqual(execution.sources[0].type, "knowledge_base")
        payload = json.loads(execution.content)
        self.assertEqual(payload["data"]["chunks"][0]["content"], "Nội dung Huế")

    def test_mapbox_execution_returns_attribution_source(self):
        self.mapbox_client.forward_search.return_value = ToolResult[
            MapboxPlaceToolData
        ](
            success=True,
            data=MapboxPlaceToolData(
                attribution="Mapbox",
                results=[],
            ),
        )

        execution = self.registry.execute(
            MAPBOX_FORWARD_SEARCH_TOOL_NAME,
            {"q": "coffee"},
        )

        self.assertTrue(execution.success)
        self.assertEqual(execution.sources[0].type, "mapbox")
        self.assertEqual(execution.sources[0].attribution, "Mapbox")
        payload = json.loads(execution.content)
        self.assertNotIn("rawResponse", payload["data"])
        request = self.mapbox_client.forward_search.call_args.args[0]
        self.assertEqual(request.q, "coffee")

    def test_tool_failure_is_classified_for_orchestrator(self):
        self.mapbox_client.forward_search.return_value = ToolResult[
            MapboxPlaceToolData
        ](
            success=False,
            error_code="mapbox_timeout",
            error_message="Timed out.",
        )

        execution = self.registry.execute(
            MAPBOX_FORWARD_SEARCH_TOOL_NAME,
            {"q": "coffee"},
        )

        self.assertFalse(execution.success)
        self.assertTrue(execution.system_failure)
        self.assertEqual(execution.error_code, "mapbox_timeout")

    def test_unexpected_handler_error_is_safe_system_failure(self):
        self.mapbox_client.forward_search.side_effect = RuntimeError(
            "provider-secret"
        )

        with self.assertLogs("chatbot.tools.registry", level="WARNING") as logs:
            execution = self.registry.execute(
                MAPBOX_FORWARD_SEARCH_TOOL_NAME,
                {"q": "coffee"},
            )

        self.assertEqual(execution.error_code, TOOL_EXECUTION_ERROR)
        self.assertTrue(execution.system_failure)
        self.assertNotIn("provider-secret", execution.content)
        self.assertNotIn("provider-secret", " ".join(logs.output))
