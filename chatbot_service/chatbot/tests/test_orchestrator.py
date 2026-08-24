"""Tests for intent-aware deterministic tool orchestration."""

from contextlib import redirect_stdout
from io import StringIO

from django.test import SimpleTestCase
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from chatbot.intent import TravelIntent
from chatbot.orchestrator import (
    ChatOrchestrator,
    NO_TOOL_CONTEXT,
    SYSTEM_PROMPT,
    ToolInfrastructureError,
)
from chatbot.response_policy import (
    DESTINATION_DISCOVERY_POLICY,
    MAPBOX_FIRST_POLICY,
    RAG_FIRST_ADVICE_POLICY,
)
from chatbot.semantic import (
    ConversationMessage,
    InterpretationStatus,
    SemanticAction,
    SemanticActionType,
    SemanticEntities,
    SemanticInterpretation,
    SemanticLocation,
    TravelDomain,
)
from chatbot.tools.models import KnowledgeBaseSource, MapboxSource
from chatbot.tools.registry import ToolExecution


class ChatOrchestratorTests(SimpleTestCase):
    def test_system_prompt_preserves_q_and_a_scope_and_place_safety(self):
        self.assertIn("dữ liệu backend", SYSTEM_PROMPT)
        self.assertIn("Không tự tạo dữ liệu có thể thay đổi", SYSTEM_PROMPT)
        self.assertIn("rating", SYSTEM_PROMPT)
        self.assertIn("needs_clarification", SYSTEM_PROMPT)
        self.assertIn("unsupported", SYSTEM_PROMPT)
        self.assertIn("không tuyên bố đã lưu", SYSTEM_PROMPT)
        self.assertIn("plain text", SYSTEM_PROMPT)
        self.assertIn("tránh khuôn lặp", SYSTEM_PROMPT)

    def test_travel_qa_executes_rag_and_sends_validated_semantics_to_model(self):
        interpretation = build_interpretation(
            intent=TravelIntent.TRAVEL_QA,
            actions=[SemanticActionType.ANSWER_TRAVEL_QUESTION],
        )
        source = KnowledgeBaseSource(title="Huế", source="hue.md")
        registry = StubRegistry(
            {
                "search_travel_knowledge": successful_execution(source),
            }
        )
        interpreter = StubInterpreter(interpretation)
        model = StubChatModel([AIMessage(content=" Huế có nhiều di sản. ")])
        history = [ConversationMessage(role="user", content="Tôi thích lịch sử")]

        result = ChatOrchestrator(
            model,
            registry,
            semantic_interpreter=interpreter,
            max_tool_calls=4,
        ).answer("  Huế có gì?  ", history=history)

        self.assertEqual(result.answer, "Huế có nhiều di sản.")
        self.assertIs(result.interpretation, interpretation)
        self.assertEqual(result.sources, [source])
        self.assertEqual(
            registry.calls,
            [
                (
                    "search_travel_knowledge",
                    {"query": "Huế có gì?"},
                )
            ],
        )
        self.assertEqual(interpreter.calls[0][0], "Huế có gì?")
        messages = model.invocations[0]
        self.assertIsInstance(messages[0], SystemMessage)
        self.assertIn(RAG_FIRST_ADVICE_POLICY.strip(), messages[0].content)
        self.assertIn('"primary_intent": "travel_qa"', messages[0].content)
        self.assertIn('"success": true', messages[0].content)
        self.assertIn("=== PHÂN TÍCH BACKEND ===", messages[0].content)
        self.assertIn("=== DỮ LIỆU BACKEND ===", messages[0].content)
        self.assertEqual(
            [message.content for message in messages if isinstance(message, HumanMessage)],
            ["Tôi thích lịch sử", "Huế có gì?"],
        )

    def test_place_discovery_uses_resolved_categories_and_deduplicates_sources(self):
        interpretation = build_interpretation(
            intent=TravelIntent.PLACE_SEARCH,
            actions=[SemanticActionType.DISCOVER_PLACES],
            domains=[TravelDomain.NIGHTLIFE],
            entities=SemanticEntities(destinations=["Hà Nội"]),
        )
        mapbox_source = MapboxSource(attribution="Mapbox")
        registry = StubRegistry(
            {
                "mapbox_forward_search": mapbox_place_execution(
                    105.854041,
                    21.028333,
                    mapbox_source,
                ),
            },
            default_execution=successful_execution(mapbox_source),
        )
        model = StubChatModel([AIMessage(content="Đã tìm thấy địa điểm phù hợp.")])

        result = ChatOrchestrator(
            model,
            registry,
            semantic_interpreter=StubInterpreter(interpretation),
            max_tool_calls=4,
        ).answer("Buổi tối ở Hà Nội có gì chơi?")

        self.assertEqual(
            [name for name, _ in registry.calls],
            [
                "mapbox_forward_search",
                "mapbox_category_search",
                "mapbox_category_search",
                "mapbox_category_search",
            ],
        )
        self.assertEqual(
            [arguments["category_id"] for _, arguments in registry.calls[1:]],
            ["nightlife", "bar", "music_venue"],
        )
        for _, arguments in registry.calls[1:]:
            self.assertEqual(arguments["language"], "vi")
            self.assertEqual(arguments["limit"], 10)
            self.assertEqual(arguments["minimum_rating"], 0.0)
            self.assertEqual(arguments["proximity"], "105.854041,21.028333")
        self.assertEqual(result.sources, [mapbox_source])
        self.assertIn(
            MAPBOX_FIRST_POLICY.strip(),
            model.invocations[0][0].content,
        )
        self.assertFalse(
            any(name == "mapbox_list_categories" for name, _ in registry.calls)
        )

    def test_place_discovery_falls_back_to_near_when_anchor_has_no_coordinates(self):
        interpretation = build_interpretation(
            intent=TravelIntent.PLACE_SEARCH,
            actions=[SemanticActionType.DISCOVER_PLACES],
            domains=[TravelDomain.FOOD],
            entities=SemanticEntities(
                destinations=["FPT Phạm Văn Bạch"],
                place_types=["quán cafe"],
            ),
            location=SemanticLocation(near="FPT Phạm Văn Bạch"),
        )
        registry = StubRegistry(
            {
                "mapbox_forward_search": ToolExecution(
                    content='{"success":true,"data":{"results":[]}}',
                    sources=(),
                    success=True,
                    system_failure=False,
                ),
            },
            default_execution=successful_execution(),
        )
        model = StubChatModel([AIMessage(content="Đã tìm thấy quán cafe.")])

        ChatOrchestrator(
            model,
            registry,
            semantic_interpreter=StubInterpreter(interpretation),
            max_tool_calls=4,
        ).answer("Cafe quanh FPT Phạm Văn Bạch")

        self.assertEqual(registry.calls[0][0], "mapbox_forward_search")
        self.assertEqual(
            [arguments["category_id"] for _, arguments in registry.calls[1:]],
            ["cafe", "coffee_shop", "restaurant"],
        )
        for _, arguments in registry.calls[1:]:
            self.assertEqual(arguments["near"], "FPT Phạm Văn Bạch")
            self.assertNotIn("proximity", arguments)

    def test_dalat_discovery_resolves_coordinates_then_searches_one_category(self):
        interpretation = build_interpretation(
            intent=TravelIntent.DESTINATION_DISCOVERY,
            actions=[SemanticActionType.DISCOVER_PLACES],
            domains=[TravelDomain.ATTRACTION, TravelDomain.NATURE],
            entities=SemanticEntities(destinations=["Đà Lạt"]),
            location=SemanticLocation(near="Đà Lạt"),
            normalized_query="Đi chơi Đà Lạt thì đi đâu?",
        )
        mapbox_source = MapboxSource(attribution="Mapbox")
        registry = StubRegistry(
            {
                "mapbox_forward_search": mapbox_place_execution(
                    108.458313,
                    11.940419,
                    mapbox_source,
                ),
                "search_travel_knowledge": successful_execution(),
            },
            default_execution=successful_execution(mapbox_source),
        )
        model = StubChatModel([AIMessage(content="Đã tìm thấy điểm tham quan.")])

        result = ChatOrchestrator(
            model,
            registry,
            semantic_interpreter=StubInterpreter(interpretation),
            max_tool_calls=4,
        ).answer("Đi chơi Đà Lạt thì đi đâu?")

        self.assertEqual(
            [name for name, _ in registry.calls],
            [
                "search_travel_knowledge",
                "mapbox_forward_search",
                "mapbox_category_search",
            ],
        )
        category_arguments = registry.calls[2][1]
        self.assertEqual(category_arguments["category_id"], "tourist_attraction")
        self.assertEqual(category_arguments["proximity"], "108.458313,11.940419")
        self.assertNotIn("types", category_arguments)
        self.assertNotIn("near", category_arguments)
        self.assertEqual(result.sources, [mapbox_source])
        messages = model.invocations[0]
        self.assertIn(
            DESTINATION_DISCOVERY_POLICY.strip(),
            messages[0].content,
        )
        self.assertIn("Knowledge Base", messages[0].content)
        self.assertIn("matchedCandidates đã được backend xác minh", messages[0].content)
        self.assertIn("additionalMapboxPlaces để bổ sung", messages[0].content)

    def test_general_chat_and_clarification_do_not_call_tools(self):
        cases = (
            build_interpretation(
                intent=TravelIntent.GENERAL_CHAT,
                actions=[SemanticActionType.ANSWER_TRAVEL_QUESTION],
            ),
            build_interpretation(
                intent=TravelIntent.PLACE_SEARCH,
                actions=[SemanticActionType.REQUEST_CLARIFICATION],
                status=InterpretationStatus.NEEDS_CLARIFICATION,
                missing_information=["Vị trí hiện tại"],
            ),
        )

        for interpretation in cases:
            with self.subTest(intent=interpretation.primary_intent):
                registry = StubRegistry()
                model = StubChatModel([AIMessage(content="Câu trả lời.")])
                ChatOrchestrator(
                    model,
                    registry,
                    semantic_interpreter=StubInterpreter(interpretation),
                    max_tool_calls=4,
                ).answer("Câu hỏi")

                self.assertEqual(registry.calls, [])
                self.assertIn(NO_TOOL_CONTEXT, model.invocations[0][0].content)

    def test_tool_budget_caps_the_backend_plan_before_execution(self):
        interpretation = build_interpretation(
            intent=TravelIntent.ITINERARY_ADVICE,
            actions=[
                SemanticActionType.PROVIDE_ITINERARY_ADVICE,
                SemanticActionType.DISCOVER_PLACES,
            ],
            domains=[TravelDomain.NATURE],
            entities=SemanticEntities(destinations=["Đà Nẵng"]),
        )
        registry = StubRegistry(default_execution=successful_execution())
        model = StubChatModel([AIMessage(content="Lịch trình gợi ý.")])

        ChatOrchestrator(
            model,
            registry,
            semantic_interpreter=StubInterpreter(interpretation),
            max_tool_calls=2,
        ).answer("Gợi ý lịch trình thiên nhiên ở Đà Nẵng")

        self.assertEqual(len(registry.calls), 2)
        self.assertEqual(registry.calls[0][0], "mapbox_forward_search")
        self.assertEqual(registry.calls[1][0], "search_travel_knowledge")

    def test_all_planned_tools_failing_from_infrastructure_raises(self):
        interpretation = build_interpretation(
            intent=TravelIntent.PLACE_SEARCH,
            actions=[SemanticActionType.FIND_NAMED_PLACE],
            entities=SemanticEntities(places=["Bà Nà Hills"]),
        )
        registry = StubRegistry(
            default_execution=ToolExecution(
                content='{"success":false}',
                sources=(),
                success=False,
                system_failure=True,
                error_code="tool_unavailable",
            )
        )
        model = StubChatModel([AIMessage(content="unused")])

        with self.assertRaises(ToolInfrastructureError):
            ChatOrchestrator(
                model,
                registry,
                semantic_interpreter=StubInterpreter(interpretation),
                max_tool_calls=4,
            ).answer("Tìm Bà Nà Hills")

        self.assertEqual(model.invocations, [])

    def test_terminal_diagnostic_prints_final_request_and_model_response(self):
        interpretation = build_interpretation(
            intent=TravelIntent.GENERAL_CHAT,
            actions=[SemanticActionType.ANSWER_TRAVEL_QUESTION],
        )
        model = StubChatModel([AIMessage(content="Xin chào!")])
        terminal_output = StringIO()

        with redirect_stdout(terminal_output):
            ChatOrchestrator(
                model,
                StubRegistry(),
                semantic_interpreter=StubInterpreter(interpretation),
                max_tool_calls=4,
            ).answer("Nội dung người dùng không được in")

        output = terminal_output.getvalue()
        self.assertIn("SemanticInterpretation result:", output)
        self.assertIn('"primary_intent": "general_chat"', output)
        self.assertIn('"normalized_query":', output)
        self.assertIn("Gemini request messages:", output)
        self.assertIn("--- MESSAGE 1: SYSTEM ---", output)
        self.assertIn("--- MESSAGE 2: HUMAN ---", output)
        self.assertIn("Bạn là trợ lý tư vấn du lịch tiếng Việt.", output)
        self.assertIn("Nội dung người dùng không được in", output)
        self.assertNotIn('"additional_kwargs"', output)
        self.assertNotIn('"response_metadata"', output)
        self.assertIn("Gemini response:", output)
        self.assertIn("Xin chào!", output)

    def test_invalid_max_calls_and_empty_model_answer_are_rejected(self):
        interpretation = build_interpretation(
            intent=TravelIntent.GENERAL_CHAT,
            actions=[SemanticActionType.ANSWER_TRAVEL_QUESTION],
        )
        interpreter = StubInterpreter(interpretation)

        for value in (0, -1, True, "3"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    ChatOrchestrator(
                        StubChatModel([]),
                        StubRegistry(),
                        semantic_interpreter=interpreter,
                        max_tool_calls=value,
                    )

        with self.assertRaisesRegex(RuntimeError, "empty answer"):
            ChatOrchestrator(
                StubChatModel([AIMessage(content="")]),
                StubRegistry(),
                semantic_interpreter=interpreter,
                max_tool_calls=4,
            ).answer("Xin chào")


def build_interpretation(
    *,
    intent: TravelIntent,
    actions: list[SemanticActionType],
    status: InterpretationStatus = InterpretationStatus.SUPPORTED,
    domains: list[TravelDomain] | None = None,
    entities: SemanticEntities | None = None,
    location: SemanticLocation | None = None,
    missing_information: list[str] | None = None,
    normalized_query: str = "Huế có gì?",
) -> SemanticInterpretation:
    return SemanticInterpretation(
        primary_intent=intent,
        normalized_query=normalized_query,
        travel_domains=domains or [],
        entities=entities or SemanticEntities(),
        location=location or SemanticLocation(),
        actions=[SemanticAction(type=action) for action in actions],
        missing_information=missing_information or [],
        status=status,
    )


def successful_execution(*sources):
    return ToolExecution(
        content='{"success":true,"data":{}}',
        sources=tuple(sources),
        success=True,
        system_failure=False,
    )


def mapbox_place_execution(longitude, latitude, *sources):
    return ToolExecution(
        content=(
            '{"success":true,"data":{"results":['
            f'{{"longitude":{longitude},"latitude":{latitude}}}'
            ']}}'
        ),
        sources=tuple(sources),
        success=True,
        system_failure=False,
    )


class StubInterpreter:
    def __init__(self, interpretation):
        self.interpretation = interpretation
        self.calls = []

    def interpret(self, question, *, history=(), current_location=None):
        self.calls.append((question, history, current_location))
        return self.interpretation


class StubRegistry:
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


class StubChatModel:
    def __init__(self, responses):
        self.responses = list(responses)
        self.invocations = []

    def invoke(self, messages):
        self.invocations.append(list(messages))
        if not self.responses:
            raise AssertionError("No model response configured")
        return self.responses.pop(0)
