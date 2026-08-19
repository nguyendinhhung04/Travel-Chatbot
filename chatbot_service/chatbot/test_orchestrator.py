"""Tests for the Gemini function-calling orchestration loop."""

import json

from django.test import SimpleTestCase
from langchain_core.messages import AIMessage, ToolMessage

from chatbot.orchestrator import (
    ChatOrchestrator,
    ToolInfrastructureError,
)
from chatbot.tools.models import KnowledgeBaseSource, MapboxSource
from chatbot.tools.registry import ToolExecution


class ChatOrchestratorTests(SimpleTestCase):
    def test_direct_greeting_returns_without_executing_tools(self):
        model = StubChatModel(bound_responses=[AIMessage(content=" Xin chào! ")])
        registry = StubRegistry()

        result = ChatOrchestrator(model, registry, max_tool_calls=3).answer(
            "  Xin chào  "
        )

        self.assertEqual(result.answer, "Xin chào!")
        self.assertEqual(result.sources, [])
        self.assertEqual(registry.calls, [])
        self.assertEqual(len(model.bound.invocations), 1)

    def test_rag_tool_result_is_sent_back_to_model_with_source(self):
        source = KnowledgeBaseSource(title="Huế", source="hue.md")
        registry = StubRegistry(
            {
                "search_travel_knowledge": ToolExecution(
                    content='{"success":true,"data":{"chunks":[]}}',
                    sources=(source,),
                    success=True,
                    system_failure=False,
                )
            }
        )
        model = StubChatModel(
            bound_responses=[
                tool_call_message("search_travel_knowledge", {"query": "Huế"}, "1"),
                AIMessage(content="Huế có nhiều di sản."),
            ]
        )

        result = ChatOrchestrator(model, registry, max_tool_calls=3).answer(
            "Huế có gì?"
        )

        self.assertEqual(result.sources, [source])
        second_messages = model.bound.invocations[1]
        self.assertIsInstance(second_messages[-1], ToolMessage)
        self.assertEqual(second_messages[-1].tool_call_id, "1")
        self.assertIn('"success":true', second_messages[-1].content)

    def test_sequential_category_tools_are_supported_and_sources_deduplicated(self):
        mapbox_source = MapboxSource(attribution="Mapbox")
        registry = StubRegistry(
            {
                "mapbox_list_categories": successful_execution(mapbox_source),
                "mapbox_category_search": successful_execution(mapbox_source),
            }
        )
        model = StubChatModel(
            bound_responses=[
                tool_call_message("mapbox_list_categories", {}, "1"),
                tool_call_message(
                    "mapbox_category_search",
                    {"category_id": "restaurant"},
                    "2",
                ),
                AIMessage(content="Đã tìm thấy nhà hàng phù hợp."),
            ]
        )

        result = ChatOrchestrator(model, registry, max_tool_calls=3).answer(
            "Tìm nhà hàng"
        )

        self.assertEqual(
            [name for name, _ in registry.calls],
            ["mapbox_list_categories", "mapbox_category_search"],
        )
        self.assertEqual(result.sources, [mapbox_source])

    def test_multiple_tools_in_one_turn_collect_rag_and_mapbox_sources(self):
        knowledge_source = KnowledgeBaseSource(title="Huế", source="hue.md")
        mapbox_source = MapboxSource(attribution="Mapbox")
        registry = StubRegistry(
            {
                "search_travel_knowledge": successful_execution(knowledge_source),
                "mapbox_forward_search": successful_execution(mapbox_source),
            }
        )
        model = StubChatModel(
            bound_responses=[
                AIMessage(
                    content="",
                    tool_calls=[
                        tool_call("search_travel_knowledge", {"query": "Huế"}, "1"),
                        tool_call("mapbox_forward_search", {"q": "Đại Nội"}, "2"),
                    ],
                ),
                AIMessage(content="Đại Nội là điểm tham quan nổi bật tại Huế."),
            ]
        )

        result = ChatOrchestrator(model, registry, max_tool_calls=3).answer(
            "Giới thiệu và tìm Đại Nội"
        )

        self.assertEqual(result.sources, [knowledge_source, mapbox_source])
        tool_messages = [
            message
            for message in model.bound.invocations[1]
            if isinstance(message, ToolMessage)
        ]
        self.assertEqual([message.tool_call_id for message in tool_messages], ["1", "2"])

    def test_tool_budget_executes_only_three_calls_then_forces_final_model(self):
        registry = StubRegistry(default_execution=successful_execution())
        model = StubChatModel(
            bound_responses=[
                AIMessage(
                    content="",
                    tool_calls=[
                        tool_call("tool_1", {}, "1"),
                        tool_call("tool_2", {}, "2"),
                        tool_call("tool_3", {}, "3"),
                        tool_call("tool_4", {}, "4"),
                    ],
                )
            ],
            final_responses=[AIMessage(content="Câu trả lời tổng hợp.")],
        )

        result = ChatOrchestrator(model, registry, max_tool_calls=3).answer(
            "Câu hỏi phức tạp"
        )

        self.assertEqual(len(registry.calls), 3)
        self.assertEqual(result.answer, "Câu trả lời tổng hợp.")
        self.assertEqual(len(model.final_invocations), 1)
        budget_messages = [
            message
            for message in model.final_invocations[0]
            if isinstance(message, ToolMessage)
            and "tool_budget_exceeded" in message.content
        ]
        self.assertEqual(len(budget_messages), 1)
        self.assertEqual(budget_messages[0].tool_call_id, "4")

    def test_all_requested_tools_failing_from_infrastructure_raises(self):
        registry = StubRegistry(
            {
                "mapbox_forward_search": ToolExecution(
                    content=json.dumps({"success": False}),
                    sources=(),
                    success=False,
                    system_failure=True,
                    error_code="tool_unavailable",
                )
            }
        )
        model = StubChatModel(
            bound_responses=[
                tool_call_message("mapbox_forward_search", {"q": "Huế"}, "1"),
                AIMessage(content="Không thể tìm kiếm."),
            ]
        )

        with self.assertRaises(ToolInfrastructureError):
            ChatOrchestrator(model, registry, max_tool_calls=3).answer("Tìm Huế")

    def test_invalid_max_calls_and_empty_model_answer_are_rejected(self):
        model = StubChatModel(bound_responses=[AIMessage(content="")])
        registry = StubRegistry()

        for value in (0, -1, True, "3"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    ChatOrchestrator(model, registry, max_tool_calls=value)

        with self.assertRaisesRegex(RuntimeError, "empty answer"):
            ChatOrchestrator(model, registry, max_tool_calls=3).answer("Xin chào")


def tool_call(name, args, call_id):
    return {"name": name, "args": args, "id": call_id, "type": "tool_call"}


def tool_call_message(name, args, call_id):
    return AIMessage(content="", tool_calls=[tool_call(name, args, call_id)])


def successful_execution(*sources):
    return ToolExecution(
        content='{"success":true,"data":{}}',
        sources=tuple(sources),
        success=True,
        system_failure=False,
    )


class StubRegistry:
    langchain_tools = []

    def __init__(self, executions=None, default_execution=None):
        self.executions = executions or {}
        self.default_execution = default_execution
        self.calls = []

    def execute(self, name, arguments):
        self.calls.append((name, arguments))
        if name in self.executions:
            return self.executions[name]
        if self.default_execution is not None:
            return self.default_execution
        raise AssertionError(f"Unexpected tool call: {name}")


class StubBoundModel:
    def __init__(self, responses):
        self.responses = list(responses)
        self.invocations = []

    def invoke(self, messages):
        self.invocations.append(list(messages))
        if not self.responses:
            raise AssertionError("No bound response configured")
        return self.responses.pop(0)


class StubChatModel:
    def __init__(self, *, bound_responses, final_responses=None):
        self.bound = StubBoundModel(bound_responses)
        self.final_responses = list(final_responses or [])
        self.final_invocations = []
        self.bound_tools = None

    def bind_tools(self, tools):
        self.bound_tools = tools
        return self.bound

    def invoke(self, messages):
        self.final_invocations.append(list(messages))
        if not self.final_responses:
            raise AssertionError("No final response configured")
        return self.final_responses.pop(0)

