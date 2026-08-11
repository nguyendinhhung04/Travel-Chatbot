from io import StringIO
from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.test import SimpleTestCase
from langchain_core.documents import Document

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
