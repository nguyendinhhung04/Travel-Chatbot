from io import StringIO
from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings
from langchain_core.documents import Document
from langchain_core.vectorstores import VectorStore

from chatbot.orchestrator import ChatOrchestratorResult
from chatbot.rag.rag_chain import (
    INSUFFICIENT_CONTEXT_MESSAGE,
    RAG_PROMPT,
    RAGResult,
    answer_question,
    build_prompt_template,
    format_context,
)
from chatbot.rag.retrieval import (
    get_retriever,
    normalize_destination,
    retrieve_documents,
)
from chatbot.tools.models import KnowledgeBaseSource, MapboxSource
from chatbot.views import CHAT_SERVICE_ERROR


class StubScoredVectorStore(VectorStore):
    """Return fixed relevance scores without calling an embedding service."""

    def __init__(self, documents_and_scores):
        self.documents_and_scores = documents_and_scores

    def similarity_search(self, query, k=4, **kwargs):
        return [document for document, _ in self.documents_and_scores[:k]]

    @classmethod
    def from_texts(cls, texts, embedding, metadatas=None, **kwargs):
        raise NotImplementedError

    def _similarity_search_with_relevance_scores(self, query, k=4, **kwargs):
        return self.documents_and_scores[:k]


class RetrievalTests(SimpleTestCase):
    @override_settings(RAG_RETRIEVAL_TOP_K=5, RAG_RELEVANCE_THRESHOLD=0.5)
    def test_get_retriever_uses_configured_top_k_and_threshold(self):
        vector_store = MagicMock()
        expected_retriever = MagicMock()
        vector_store.as_retriever.return_value = expected_retriever

        result = get_retriever(vector_store=vector_store)

        self.assertIs(result, expected_retriever)
        vector_store.as_retriever.assert_called_once_with(
            search_type="similarity_score_threshold",
            search_kwargs={"k": 5, "score_threshold": 0.5},
        )

    @override_settings(RAG_RELEVANCE_THRESHOLD=0.5)
    def test_get_retriever_accepts_custom_top_k(self):
        vector_store = MagicMock()

        get_retriever(vector_store=vector_store, top_k=3)

        vector_store.as_retriever.assert_called_once_with(
            search_type="similarity_score_threshold",
            search_kwargs={"k": 3, "score_threshold": 0.5},
        )

    @override_settings(RAG_RETRIEVAL_TOP_K=5, RAG_RELEVANCE_THRESHOLD=0.5)
    def test_get_retriever_filters_by_normalized_destination(self):
        vector_store = MagicMock()

        get_retriever(vector_store=vector_store, destination="Đà Lạt")

        vector_store.as_retriever.assert_called_once_with(
            search_type="similarity_score_threshold",
            search_kwargs={
                "k": 5,
                "score_threshold": 0.5,
                "filter": {"destination": "da-lat"},
            },
        )

    def test_normalize_destination_handles_vietnamese_names(self):
        self.assertEqual(normalize_destination(" Đà Lạt "), "da-lat")
        self.assertEqual(normalize_destination("Hội An"), "hoi-an")
        self.assertIsNone(normalize_destination("   "))

    @override_settings(RAG_RETRIEVAL_TOP_K=5, RAG_RELEVANCE_THRESHOLD=0.5)
    def test_retriever_filters_scores_below_threshold_and_keeps_boundary(self):
        below = Document(page_content="below")
        boundary = Document(page_content="boundary")
        above = Document(page_content="above")
        vector_store = StubScoredVectorStore(
            [(above, 0.8), (boundary, 0.5), (below, 0.49)]
        )

        retriever = get_retriever(vector_store=vector_store)
        documents = retriever.invoke("Hue co gi?")

        self.assertEqual(documents, [above, boundary])

    def test_get_retriever_rejects_invalid_top_k(self):
        vector_store = MagicMock()

        for top_k in (0, -1, True, "5"):
            with self.subTest(top_k=top_k):
                with self.assertRaises(ValueError):
                    get_retriever(vector_store=vector_store, top_k=top_k)

    def test_retrieve_documents_cleans_question_and_returns_documents(self):
        retriever = MagicMock()
        documents = [Document(page_content="Hue", metadata={"source": "hue.md"})]
        retriever.invoke.return_value = documents

        result = retrieve_documents("  Hue co gi?  ", retriever=retriever)

        self.assertIs(result, documents)
        retriever.invoke.assert_called_once_with("Hue co gi?")

    def test_retrieve_documents_rejects_empty_question(self):
        with self.assertRaises(ValueError):
            retrieve_documents("   ", retriever=MagicMock())

    @patch("chatbot.management.commands.retrieve_knowledge.retrieve_documents")
    def test_retrieve_command_prints_document_information(self, retrieve_mock):
        retrieve_mock.return_value = [
            Document(
                page_content="Noi dung ve Hue",
                metadata={
                    "source": "destinations/hue/overview.md",
                    "title": "Tong quan du lich Hue",
                    "header_1": "Hue",
                },
            )
        ]
        output = StringIO()

        call_command(
            "retrieve_knowledge",
            "Hue co gi?",
            top_k=3,
            stdout=output,
        )

        retrieve_mock.assert_called_once_with("Hue co gi?", top_k=3)
        rendered = output.getvalue()
        self.assertIn("Results: 1", rendered)
        self.assertIn("destinations/hue/overview.md", rendered)
        self.assertIn("Tong quan du lich Hue", rendered)

    @patch("chatbot.management.commands.retrieve_knowledge.retrieve_documents")
    def test_retrieve_command_explains_when_no_document_meets_threshold(
        self, retrieve_mock
    ):
        retrieve_mock.return_value = []
        output = StringIO()

        call_command("retrieve_knowledge", "Paris co gi?", stdout=output)

        self.assertIn("No documents met the relevance threshold", output.getvalue())


class RAGChainTests(SimpleTestCase):
    def setUp(self):
        self.documents = [
            Document(
                page_content="Co the tham quan Dai Noi Hue.",
                metadata={
                    "title": "Hoat dong tai Hue",
                    "source": "destinations/hue/activities.md",
                    "header_1": "Hoat dong",
                },
            )
        ]

    @patch("chatbot.rag.rag_chain.ChatGoogleGenerativeAI")
    def test_get_chat_model_uses_configured_values(self, chat_model_mock):
        from chatbot.rag.rag_chain import get_chat_model

        get_chat_model(api_key="test-key", model="test-model")

        chat_model_mock.assert_called_once_with(
            model="test-model",
            api_key="test-key",
            temperature=0.8,
        )

    def test_format_context_includes_content_and_metadata(self):
        rendered = format_context(self.documents)

        self.assertIn("Hoat dong tai Hue", rendered)
        self.assertIn("destinations/hue/activities.md", rendered)
        self.assertIn("Hoat dong", rendered)
        self.assertIn("Co the tham quan Dai Noi Hue.", rendered)

    def test_prompt_template_has_context_and_question_variables(self):
        prompt = build_prompt_template()

        rendered = prompt.invoke(
            {
                "context": "Đại Nội nằm ở thành phố Huế.",
                "question": "Đại Nội ở đâu?",
            }
        ).to_string()

        self.assertIn("Đại Nội nằm ở thành phố Huế.", rendered)
        self.assertIn("Đại Nội ở đâu?", rendered)
        self.assertIn("Ưu tiên sử dụng thông tin trong Context", rendered)
        self.assertIn("có thể dùng kiến thức của mình để bổ sung", rendered)
        self.assertIn(INSUFFICIENT_CONTEXT_MESSAGE, rendered)
        self.assertIn("sáng tạo", RAG_PROMPT)
        self.assertNotIn("ngắn gọn", RAG_PROMPT)
        self.assertNotIn("đoạn ngắn", RAG_PROMPT)

    @patch("chatbot.rag.rag_chain.retrieve_documents")
    def test_answer_question_passes_context_to_chain(self, retrieve_mock):
        retrieve_mock.return_value = self.documents
        chain = MagicMock()
        chain.invoke.return_value = "  Bạn có thể tham quan Đại Nội.  "

        result = answer_question(
            "  Hue co gi?  ",
            retriever=MagicMock(),
            chain=chain,
        )

        self.assertEqual(result.answer, "Bạn có thể tham quan Đại Nội.")
        self.assertIs(result.documents, self.documents)
        chain.invoke.assert_called_once()
        values = chain.invoke.call_args.args[0]
        self.assertEqual(values["question"], "Hue co gi?")
        self.assertIn("Co the tham quan Dai Noi Hue.", values["context"])

    @patch("chatbot.rag.rag_chain.retrieve_documents")
    def test_answer_question_passes_top_k_to_retrieval(self, retrieve_mock):
        retrieve_mock.return_value = self.documents
        chain = MagicMock()
        chain.invoke.return_value = "Câu trả lời"

        answer_question("  Hue co gi?  ", chain=chain, top_k=3)

        retrieve_mock.assert_called_once_with(
            "Hue co gi?",
            retriever=None,
            top_k=3,
        )

    @patch("chatbot.rag.rag_chain.retrieve_documents")
    def test_answer_question_rejects_empty_question(self, retrieve_mock):
        with self.assertRaises(ValueError):
            answer_question("   ", chain=MagicMock())

        retrieve_mock.assert_not_called()

    @patch("chatbot.rag.rag_chain.retrieve_documents")
    def test_answer_question_rejects_empty_model_answer(self, retrieve_mock):
        retrieve_mock.return_value = self.documents
        chain = MagicMock()
        chain.invoke.return_value = "   "

        with self.assertRaisesRegex(RuntimeError, "empty answer"):
            answer_question("Hue co gi?", chain=chain)

    @patch("chatbot.rag.rag_chain.retrieve_documents", return_value=[])
    def test_answer_question_returns_fallback_without_calling_chain(
        self, retrieve_mock
    ):
        chain = MagicMock()

        result = answer_question("Khong co du lieu", chain=chain)

        self.assertEqual(result.answer, INSUFFICIENT_CONTEXT_MESSAGE)
        self.assertEqual(result.documents, [])
        chain.invoke.assert_not_called()
        retrieve_mock.assert_called_once()

    @override_settings(GEMINI_API_KEY="")
    def test_get_chat_model_rejects_missing_api_key(self):
        from chatbot.rag.rag_chain import get_chat_model

        with self.assertRaises(ValueError):
            get_chat_model()


@override_settings(ALLOWED_HOSTS=["testserver"])
class ChatAPITests(SimpleTestCase):
    @patch("chatbot.views.orchestrate_chat")
    def test_invalid_messages_return_bad_request_without_orchestration(
        self,
        orchestrate_mock,
    ):
        invalid_payloads = (
            {},
            {"message": "   "},
            {"message": 123},
            {
                "message": "Tìm gần đây",
                "current_location": {"longitude": 108.2},
            },
            {
                "message": "Câu hỏi",
                "history": [
                    {"role": "user", "content": f"Tin nhắn {index}"}
                    for index in range(13)
                ],
            },
        )
        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                response = self.client.post(
                    "/api/chat/",
                    data=payload,
                    content_type="application/json",
                )

                self.assertEqual(response.status_code, 400)

        orchestrate_mock.assert_not_called()

    @patch("chatbot.views.orchestrate_chat")
    def test_no_relevant_documents_returns_fallback_without_sources(
        self, orchestrate_mock
    ):
        orchestrate_mock.return_value = ChatOrchestratorResult(
            answer=INSUFFICIENT_CONTEXT_MESSAGE,
            sources=[],
        )

        response = self.client.post(
            "/api/chat/",
            data={"message": "Paris co gi?"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"answer": INSUFFICIENT_CONTEXT_MESSAGE, "sources": []},
        )

    @patch("chatbot.views.orchestrate_chat")
    def test_success_serializes_typed_knowledge_and_mapbox_sources(
        self,
        orchestrate_mock,
    ):
        orchestrate_mock.return_value = ChatOrchestratorResult(
            answer="Câu trả lời",
            sources=[
                KnowledgeBaseSource(title="Huế", source="hue.md"),
                MapboxSource(attribution="© Mapbox"),
            ],
        )

        response = self.client.post(
            "/api/chat/",
            data={"message": "Huế có gì?"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "answer": "Câu trả lời",
                "sources": [
                    {
                        "type": "knowledge_base",
                        "title": "Huế",
                        "source": "hue.md",
                    },
                    {
                        "type": "mapbox",
                        "title": "Mapbox",
                        "source": "Mapbox Search API",
                        "attribution": "© Mapbox",
                    },
                ],
            },
        )

    @patch("chatbot.views.orchestrate_chat", side_effect=RuntimeError("failed"))
    def test_orchestrator_failure_returns_service_unavailable(
        self,
        orchestrate_mock,
    ):
        with self.assertLogs("chatbot.views", level="ERROR"):
            response = self.client.post(
                "/api/chat/",
                data={"message": "Huế có gì?"},
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"error": CHAT_SERVICE_ERROR})
        orchestrate_mock.assert_called_once_with(
            "Huế có gì?",
            history=(),
            current_location=None,
        )

    @patch("chatbot.views.orchestrate_chat")
    def test_optional_history_and_location_are_forwarded_to_orchestration(
        self,
        orchestrate_mock,
    ):
        orchestrate_mock.return_value = ChatOrchestratorResult(
            answer="Có quán cafe phù hợp.",
            sources=[],
        )

        response = self.client.post(
            "/api/chat/",
            data={
                "message": "Tìm quán gần đây",
                "history": [
                    {"role": "user", "content": "Tôi đang ở cầu Rồng"}
                ],
                "current_location": {
                    "longitude": 108.227,
                    "latitude": 16.061,
                    "radius_km": 1,
                },
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        call = orchestrate_mock.call_args
        self.assertEqual(call.args, ("Tìm quán gần đây",))
        self.assertEqual(call.kwargs["history"][0].role, "user")
        self.assertEqual(
            call.kwargs["current_location"].longitude,
            108.227,
        )


class AskTravelCommandTests(SimpleTestCase):
    @patch("chatbot.management.commands.ask_travel.answer_question")
    def test_command_prints_answer_and_sources(self, answer_mock):
        answer_mock.return_value = RAGResult(
            answer="Hue answer",
            documents=[
                Document(
                    page_content="Nội dung",
                    metadata={
                        "title": "Hue activities",
                        "source": "destinations/hue/activities.md",
                    },
                )
            ],
        )
        output = StringIO()

        call_command(
            "ask_travel",
            "Hue co gi?",
            top_k=3,
            stdout=output,
        )

        answer_mock.assert_called_once_with("Hue co gi?", top_k=3)
        rendered = output.getvalue()
        self.assertIn("Question: Hue co gi?", rendered)
        self.assertIn("Hue answer", rendered)
        self.assertIn("Hue activities", rendered)
        self.assertIn("destinations/hue/activities.md", rendered)

    @patch("chatbot.management.commands.ask_travel.answer_question")
    def test_command_wraps_rag_errors(self, answer_mock):
        answer_mock.side_effect = ValueError("question must not be empty")

        with self.assertRaisesMessage(CommandError, "question must not be empty"):
            call_command("ask_travel", "   ", stdout=StringIO())


class IngestKnowledgeCommandTests(SimpleTestCase):
    def test_command_pauses_between_embedding_batches(self):
        documents = [Document(page_content="Travel knowledge")]
        chunks = [Document(page_content="Travel chunk")]
        embedding_model = MagicMock()
        vector_store = MagicMock()
        stats = MagicMock(added=1, unchanged=0, deleted=0)

        with (
            patch(
                "chatbot.management.commands.ingest_knowledge."
                "load_markdown_documents",
                return_value=documents,
            ),
            patch(
                "chatbot.management.commands.ingest_knowledge.split_documents",
                return_value=chunks,
            ),
            patch(
                "chatbot.management.commands.ingest_knowledge.get_embedding_model",
                return_value=embedding_model,
            ),
            patch(
                "chatbot.management.commands.ingest_knowledge.verify_embedding",
                return_value=3072,
            ),
            patch(
                "chatbot.management.commands.ingest_knowledge.get_vector_store",
                return_value=vector_store,
            ),
            patch(
                "chatbot.management.commands.ingest_knowledge.sync_vector_store",
                return_value=stats,
            ) as sync_mock,
            patch(
                "chatbot.management.commands.ingest_knowledge.verify_vector_store"
            ),
        ):
            call_command("ingest_knowledge", stdout=StringIO())

        sync_mock.assert_called_once_with(
            vector_store,
            chunks,
            batch_size=50,
            batch_pause_seconds=65,
        )
