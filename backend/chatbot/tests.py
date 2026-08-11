from io import StringIO
from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings
from langchain_core.documents import Document

from chatbot.rag.rag_chain import (
    INSUFFICIENT_CONTEXT_MESSAGE,
    RAGResult,
    answer_question,
    build_prompt_template,
    format_context,
)
from chatbot.rag.retrieval import get_retriever, retrieve_documents


class RetrievalTests(SimpleTestCase):
    def test_get_retriever_uses_configured_top_k(self):
        vector_store = MagicMock()
        expected_retriever = MagicMock()
        vector_store.as_retriever.return_value = expected_retriever

        result = get_retriever(vector_store=vector_store)

        self.assertIs(result, expected_retriever)
        vector_store.as_retriever.assert_called_once_with(
            search_type="similarity",
            search_kwargs={"k": 5},
        )

    def test_get_retriever_accepts_custom_top_k(self):
        vector_store = MagicMock()

        get_retriever(vector_store=vector_store, top_k=3)

        vector_store.as_retriever.assert_called_once_with(
            search_type="similarity",
            search_kwargs={"k": 3},
        )

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
            temperature=0,
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
        self.assertIn("Chỉ trả lời dựa trên Context", rendered)
        self.assertIn(INSUFFICIENT_CONTEXT_MESSAGE, rendered)

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
