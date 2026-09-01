"""Tests for the local travel-knowledge retrieval tool."""

from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from langchain_core.documents import Document

from chatbot.tools.models import SearchTravelKnowledgeInput
from chatbot.tools.rag_tool import (
    RAG_UNAVAILABLE_ERROR,
    build_rag_tool_data,
    search_travel_knowledge,
)


class TravelKnowledgeToolTests(SimpleTestCase):
    @patch("chatbot.tools.rag_tool.retrieve_documents")
    def test_tool_retrieves_and_maps_chunks_without_generating_answer(
        self,
        retrieve_mock,
    ):
        documents = [
            Document(
                page_content="  Nội dung về Đại Nội Huế.  ",
                metadata={
                    "title": "Đại Nội Huế",
                    "source": "places/dai-noi-hue/overview.md",
                    "header_1": "Đại Nội",
                    "header_3": "Giờ tham quan",
                },
            ),
            Document(
                page_content="Một lưu ý khác.",
                metadata={
                    "title": "Đại Nội Huế",
                    "source": "places/dai-noi-hue/overview.md",
                    "header_2": "Lưu ý",
                },
            ),
        ]
        retrieve_mock.return_value = documents
        retriever = MagicMock()

        result = search_travel_knowledge(
            SearchTravelKnowledgeInput(query="  Đại Nội ở đâu?  "),
            retriever=retriever,
            top_k=3,
        )

        self.assertTrue(result.success)
        self.assertIsNotNone(result.data)
        self.assertEqual(len(result.data.chunks), 2)
        self.assertEqual(result.data.chunks[0].content, "Nội dung về Đại Nội Huế.")
        self.assertEqual(result.data.chunks[0].heading, "Giờ tham quan")
        self.assertEqual(result.data.chunks[1].heading, "Lưu ý")
        self.assertEqual(len(result.data.sources), 1)
        self.assertEqual(result.data.sources[0].type, "knowledge_base")
        retrieve_mock.assert_called_once_with(
            "Đại Nội ở đâu?",
            retriever=retriever,
            top_k=3,
            destination=None,
        )

    @patch("chatbot.tools.rag_tool.retrieve_documents", return_value=[])
    def test_tool_returns_success_with_empty_data_when_no_documents_match(
        self,
        retrieve_mock,
    ):
        result = search_travel_knowledge(
            SearchTravelKnowledgeInput(query="Không có dữ liệu")
        )

        self.assertTrue(result.success)
        self.assertEqual(result.data.chunks, [])
        self.assertEqual(result.data.sources, [])
        retrieve_mock.assert_called_once_with(
            "Không có dữ liệu",
            retriever=None,
            top_k=None,
            destination=None,
        )

    @patch("chatbot.tools.rag_tool.retrieve_documents", return_value=[])
    def test_tool_passes_destination_to_retrieval(self, retrieve_mock):
        result = search_travel_knowledge(
            SearchTravelKnowledgeInput(
                query="Đi chơi Đà Lạt",
                destination="Đà Lạt",
            )
        )

        self.assertTrue(result.success)
        retrieve_mock.assert_called_once_with(
            "Đi chơi Đà Lạt",
            retriever=None,
            top_k=None,
            destination="Đà Lạt",
        )

    def test_build_data_uses_safe_metadata_defaults_and_skips_blank_chunks(self):
        data = build_rag_tool_data(
            [
                Document(page_content="   ", metadata={"title": "Skipped"}),
                Document(page_content="Travel content", metadata={}),
            ]
        )

        chunk = self.assert_single(data.chunks)
        source = self.assert_single(data.sources)
        self.assertEqual(chunk.title, "Không rõ")
        self.assertEqual(chunk.source, "unknown")
        self.assertIsNone(chunk.heading)
        self.assertEqual(source.title, "Không rõ")
        self.assertEqual(source.source, "unknown")

    @patch(
        "chatbot.tools.rag_tool.retrieve_documents",
        side_effect=RuntimeError("provider-secret"),
    )
    def test_retrieval_failure_returns_safe_structured_error(self, retrieve_mock):
        with self.assertLogs("chatbot.tools.rag_tool", level="WARNING") as logs:
            result = search_travel_knowledge(
                SearchTravelKnowledgeInput(query="Huế có gì?")
            )

        self.assertFalse(result.success)
        self.assertIsNone(result.data)
        self.assertEqual(result.error_code, RAG_UNAVAILABLE_ERROR)
        self.assertNotIn("provider-secret", result.error_message)
        self.assertNotIn("provider-secret", " ".join(logs.output))
        retrieve_mock.assert_called_once()

    def assert_single(self, values):
        self.assertEqual(len(values), 1)
        return values[0]
