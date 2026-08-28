"""Tests for intent-aware deterministic tool orchestration."""

import json
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import call, patch

from django.test import SimpleTestCase
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from chatbot.intent import TravelIntent
from chatbot.orchestrator import (
    ChatOrchestrator,
    NO_TOOL_CONTEXT,
    SYSTEM_PROMPT,
    ToolInfrastructureError,
    orchestrate_chat,
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
from chatbot.tool_planner import PlannedToolCall
from chatbot.tools.models import (
    ChatPlace,
    KnowledgeBaseSource,
    MapboxPlaceDetailsItem,
    MapboxPlacePhoto,
    MapboxPlacesDetailsData,
    MapboxSource,
    ToolResult,
)
from chatbot.tools.registry import ToolExecution


class ChatOrchestratorTests(SimpleTestCase):
    def test_enrich_answer_places_calls_one_batch_and_merges_details(self):
        cafe_id = "dXJuOm1ieHBvaTpjYWZlLWV4YW1wbGU"
        missing_id = "dXJuOm1ieHBvaTptaXNzaW5n"
        captured_ids = []

        def load_details(request):
            captured_ids.append(request.ids)
            return ToolResult[
                MapboxPlacesDetailsData
            ].model_validate({
                "success": True,
                "data": MapboxPlacesDetailsData(
                    results=[
                        MapboxPlaceDetailsItem(
                            mapboxId=cafe_id,
                            name="Cafe Example",
                            fullAddress="1 Example Street",
                            primaryCategory="cafe",
                            categories=["cafe"],
                            openingHours="Mo-Su 07:00-22:00",
                            permanentlyClosed=False,
                            phone="+84123456789",
                            website="https://example.test",
                            status="active",
                            longitude=105.8,
                            latitude=21.0,
                            popularity=0.9,
                            photos=[MapboxPlacePhoto(
                                url="https://images.example.test/place.jpg"
                            )],
                        )
                    ]
                ),
            })

        orchestrator = ChatOrchestrator(
            StubChatModel([]),
            StubRegistry(),
            semantic_interpreter=StubInterpreter(None),
            place_details_loader=load_details,
        )
        places = orchestrator._enrich_answer_places([
            ChatPlace(
                mapboxId=cafe_id,
                name="Cafe Example",
                longitude=105.8,
                latitude=21.0,
            ),
            ChatPlace(
                mapboxId=missing_id,
                name="Missing Place",
                longitude=105.9,
                latitude=21.1,
            ),
        ])

        self.assertEqual(captured_ids, [[cafe_id, missing_id]])
        self.assertEqual(places[0].opening_hours, "Mo-Su 07:00-22:00")
        self.assertEqual(places[0].photos[0].source, None)
        self.assertIsNone(places[1].opening_hours)

    def test_enrich_answer_places_excludes_non_poi_ids_from_batch(self):
        poi_id = "dXJuOm1ieHBvaTpjYWZlLWV4YW1wbGU"
        city_id = "dXJuOm1ieHBsYzpSUFE"
        captured_ids = []

        def load_details(request):
            captured_ids.append(request.ids)
            return ToolResult[MapboxPlacesDetailsData].model_validate({
                "success": True,
                "data": {"results": []},
            })

        orchestrator = ChatOrchestrator(
            StubChatModel([]),
            StubRegistry(),
            semantic_interpreter=StubInterpreter(None),
            place_details_loader=load_details,
        )
        places = [
            ChatPlace(
                mapboxId=poi_id,
                name="Cafe Example",
                longitude=105.8,
                latitude=21.0,
            ),
            ChatPlace(
                mapboxId=city_id,
                name="New York",
                longitude=-74.006,
                latitude=40.7128,
            ),
        ]

        enriched = orchestrator._enrich_answer_places(places)

        self.assertEqual(captured_ids, [[poi_id]])
        self.assertEqual(enriched, places)

    def test_enrich_answer_places_skips_batch_when_no_poi_ids_exist(self):
        loader_called = False

        def load_details(_request):
            nonlocal loader_called
            loader_called = True
            raise AssertionError("Places Details should not be called")

        orchestrator = ChatOrchestrator(
            StubChatModel([]),
            StubRegistry(),
            semantic_interpreter=StubInterpreter(None),
            place_details_loader=load_details,
        )
        places = [ChatPlace(
            mapboxId="dXJuOm1ieHBsYzpSUFE",
            name="New York",
            longitude=-74.006,
            latitude=40.7128,
        )]

        enriched = orchestrator._enrich_answer_places(places)

        self.assertFalse(loader_called)
        self.assertEqual(enriched, places)

    def test_destination_coordinates_ignore_fuzzy_result_with_wrong_name(self):
        execution = ToolExecution(
            content=(
                '{"success":true,"data":{"results":['
                '{"name":"Cửa Hàng Đá Ốp Lát","longitude":105.79,"latitude":21.04},'
                '{"name":"Đà Lạt","longitude":108.45,"latitude":11.94}'
                ']}}'
            ),
            sources=(),
            success=True,
            system_failure=False,
        )

        self.assertEqual(
            ChatOrchestrator._first_result_coordinates(
                execution,
                destination="Đà Lạt",
            ),
            (108.45, 11.94),
        )

    def test_model_request_log_redacts_current_location_coordinates(self):
        terminal_output = StringIO()

        with redirect_stdout(terminal_output):
            ChatOrchestrator._print_model_request(
                [HumanMessage(content="near 108.2,16.05")],
                sensitive_location=SemanticLocation(
                    longitude=108.2,
                    latitude=16.05,
                ),
            )

        output = terminal_output.getvalue()
        self.assertIn("[location-redacted]", output)
        self.assertNotIn("108.2,16.05", output)

    def test_current_location_request_returns_client_tool_call_before_tools(self):
        interpretation = build_interpretation(
            intent=TravelIntent.PLACE_SEARCH,
            actions=[SemanticActionType.REQUEST_CLARIFICATION],
            status=InterpretationStatus.NEEDS_CLARIFICATION,
            location=SemanticLocation(use_current_location=True),
            missing_information=["current_location"],
        )
        registry = StubRegistry()
        model = StubChatModel([AIMessage(content="should not be called")])

        result = ChatOrchestrator(
            model,
            registry,
            semantic_interpreter=StubInterpreter(interpretation),
            max_tool_calls=4,
        ).answer("Tìm quán cafe gần tôi")

        self.assertEqual(result.client_tool_call, "get_current_location")
        self.assertEqual(result.answer, "")
        self.assertEqual(registry.calls, [])
        self.assertEqual(model.invocations, [])

    @patch("chatbot.orchestrator.ChatOrchestrator")
    @patch("chatbot.orchestrator.DestinationCandidateGenerator")
    @patch("chatbot.orchestrator.SemanticInterpreter")
    @patch("chatbot.orchestrator.get_chat_model")
    def test_default_models_split_planning_and_synthesis_thinking(
        self,
        get_chat_model_mock,
        semantic_interpreter_mock,
        candidate_generator_mock,
        orchestrator_mock,
    ):
        synthesis_model = object()
        planning_model = object()
        registry = StubRegistry()
        expected = object()
        get_chat_model_mock.side_effect = [synthesis_model, planning_model]
        orchestrator_mock.return_value.answer.return_value = expected

        result = orchestrate_chat("Huế có gì?", registry=registry)

        self.assertIs(result, expected)
        self.assertEqual(
            get_chat_model_mock.call_args_list,
            [
                call(thinking_level="medium"),
                call(thinking_level="low"),
            ],
        )
        semantic_interpreter_mock.assert_called_once_with(planning_model)
        candidate_generator_mock.assert_called_once_with(planning_model)
        orchestrator_mock.assert_called_once_with(
            synthesis_model,
            registry,
            semantic_interpreter=semantic_interpreter_mock.return_value,
            candidate_generator=candidate_generator_mock.return_value,
            max_tool_calls=None,
        )

    def test_system_prompt_preserves_q_and_a_scope_and_place_safety(self):
        self.assertIn("dữ liệu backend", SYSTEM_PROMPT)
        self.assertIn("Không tự tạo dữ liệu có thể thay đổi", SYSTEM_PROMPT)
        self.assertIn("rating", SYSTEM_PROMPT)
        self.assertIn("needs_clarification", SYSTEM_PROMPT)
        self.assertIn("unsupported", SYSTEM_PROMPT)
        self.assertIn("không tuyên bố đã lưu", SYSTEM_PROMPT)
        self.assertIn("plain text", SYSTEM_PROMPT)
        self.assertIn("tránh khuôn lặp", SYSTEM_PROMPT)
        self.assertIn("giữ nguyên trường `name`", SYSTEM_PROMPT)

    def test_collect_answer_places_keeps_only_unique_mentioned_verified_places(self):
        execution = ToolExecution(
            content=(
                '{"success":true,"data":{"results":['
                '{"mapboxId":"mapbox.ho","name":"Hồ Xuân Hương",'
                '"longitude":108.44,"latitude":11.94},'
                '{"mapboxId":"mapbox.garden","name":"Vườn hoa thành phố",'
                '"longitude":108.45,"latitude":11.95},'
                '{"mapboxId":"mapbox.unmentioned","name":"Thiền Viện Trúc Lâm",'
                '"longitude":108.46,"latitude":11.96},'
                '{"mapboxId":"mapbox.missing-coordinate","name":"Thác Datanla",'
                '"latitude":11.97},'
                '{"mapboxId":"mapbox.ambiguous-a","name":"Hồ",'
                '"longitude":108.40,"latitude":11.90},'
                '{"mapboxId":"mapbox.ambiguous-b","name":"Hồ",'
                '"longitude":108.41,"latitude":11.91}'
                ']}}'
            ),
            sources=(),
            success=True,
            system_failure=False,
        )

        places = ChatOrchestrator._collect_answer_places(
            "Nên ghé Hồ Xuân Hương. Vườn hoa thành phố cũng rất đẹp.",
            [execution, execution],
            None,
        )

        self.assertEqual(
            [
                place.model_dump(by_alias=True, exclude_none=True, exclude_defaults=True)
                for place in places
            ],
            [
                {
                    "mapboxId": "mapbox.ho",
                    "name": "Hồ Xuân Hương",
                    "longitude": 108.44,
                    "latitude": 11.94,
                },
                {
                    "mapboxId": "mapbox.garden",
                    "name": "Vườn hoa thành phố",
                    "longitude": 108.45,
                    "latitude": 11.95,
                },
            ],
        )

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
        self.assertIn('"knowledgeBase": []', messages[0].content)
        self.assertIn("=== CÂU HỎI ===\nHuế có gì?", messages[0].content)
        self.assertNotIn("=== PHÂN TÍCH BACKEND ===", messages[0].content)
        self.assertNotIn('"primary_intent"', messages[0].content)
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

    def test_ordinary_evidence_is_compact_and_separates_anchor_from_places(self):
        calls = [
            PlannedToolCall(
                "search_travel_knowledge",
                {"query": "Cafe gần FPT"},
                evidence_kind="knowledge",
            ),
            PlannedToolCall(
                "mapbox_forward_search",
                {"q": "FPT Phạm Văn Bạch"},
                evidence_kind="destination_location",
            ),
            PlannedToolCall(
                "mapbox_category_search",
                {"category_id": "cafe"},
                evidence_kind="poi",
            ),
        ]
        executions = [
            ToolExecution(
                content=(
                    '{"success":true,"data":{"chunks":['
                    '{"title":"Cafe","content":"Nội dung gọn",'
                    '"source":"cafe.md","heading":"Gợi ý"}],'
                    '"sources":[{"title":"Cafe","source":"cafe.md"}]}}'
                ),
                sources=(),
                success=True,
                system_failure=False,
            ),
            compact_mapbox_execution(
                mapbox_id="anchor.fpt",
                name="FPT Phạm Văn Bạch",
                longitude=105.79,
                latitude=21.03,
                feature_type="poi",
                popularity=0.8,
            ),
            compact_mapbox_execution(
                mapbox_id="cafe.1",
                name="Cafe Example",
                longitude=105.80,
                latitude=21.04,
                full_address="Cầu Giấy, Hà Nội",
                categories=["quán cafe"],
                distance=350.0,
                rating=4.5,
                feature_type="poi",
                popularity=0.9,
            ),
        ]

        evidence = json.loads(
            ChatOrchestrator._ordinary_evidence_content(calls, executions)
        )

        self.assertEqual(
            evidence,
            {
                "knowledgeBase": [
                    {"title": "Cafe", "content": "Nội dung gọn"}
                ],
                "mapbox": {
                    "success": True,
                    "destinationLocations": [
                        {
                            "mapboxId": "anchor.fpt",
                            "name": "FPT Phạm Văn Bạch",
                            "longitude": 105.79,
                            "latitude": 21.03,
                        }
                    ],
                    "places": [
                        {
                            "mapboxId": "cafe.1",
                            "name": "Cafe Example",
                            "fullAddress": "Cầu Giấy, Hà Nội",
                            "longitude": 105.8,
                            "latitude": 21.04,
                            "poiCategories": ["quán cafe"],
                            "distanceMeters": 350.0,
                            "rating": 4.5,
                        }
                    ],
                },
            },
        )
        serialized = json.dumps(evidence, ensure_ascii=False)
        self.assertNotIn("source", serialized)
        self.assertNotIn("attribution", serialized)
        self.assertNotIn("featureType", serialized)
        self.assertNotIn("poiCategoryIds", serialized)
        self.assertNotIn("popularity", serialized)

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
                "mapbox_resolve_candidates",
            ],
        )
        resolution_arguments = registry.calls[2][1]
        self.assertEqual(resolution_arguments["categoryId"], "tourist_attraction")
        self.assertEqual(resolution_arguments["longitude"], 108.458313)
        self.assertEqual(resolution_arguments["latitude"], 11.940419)
        self.assertEqual(resolution_arguments["candidates"], [])
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
        self.assertNotIn("SemanticInterpretation result:", output)
        self.assertNotIn('"primary_intent": "general_chat"', output)
        self.assertNotIn('"normalized_query":', output)
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


def compact_mapbox_execution(
    *,
    mapbox_id,
    name,
    longitude,
    latitude,
    full_address=None,
    categories=None,
    distance=None,
    rating=None,
    feature_type=None,
    popularity=None,
):
    place = {
        "mapboxId": mapbox_id,
        "name": name,
        "fullAddress": full_address,
        "longitude": longitude,
        "latitude": latitude,
        "poiCategories": categories or [],
        "operationalStatus": None,
        "distanceMeters": distance,
        "etaMinutes": None,
        "rating": rating,
        "featureType": feature_type,
        "poiCategoryIds": ["cafe"],
        "popularity": popularity,
    }
    return ToolExecution(
        content=json.dumps(
            {
                "success": True,
                "data": {"attribution": "Mapbox", "results": [place]},
            },
            ensure_ascii=False,
        ),
        sources=(),
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
