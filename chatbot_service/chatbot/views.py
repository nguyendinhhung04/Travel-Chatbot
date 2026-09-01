"""HTTP views and response helpers for the travel chatbot API."""

import logging

from langchain_core.exceptions import OutputParserException
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .orchestrator import orchestrate_chat
from .semantic import ConversationMessage, SemanticLocation
from .serializers import ChatRequestSerializer


logger = logging.getLogger(__name__)

CHAT_SERVICE_ERROR = "Chatbot hiện không thể trả lời. Vui lòng thử lại sau."


class ChatAPIView(APIView):
    """Answer one travel question with backend-selected read-only tools."""

    def post(self, request):
        serializer = ChatRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        message = serializer.validated_data["message"]
        history = tuple(
            ConversationMessage.model_validate(item)
            for item in serializer.validated_data.get("history", [])
        )
        location_data = serializer.validated_data.get("current_location")
        current_location = (
            SemanticLocation.model_validate(location_data)
            if location_data is not None
            else None
        )
        active_itinerary_id = serializer.validated_data.get("active_itinerary_id")
        active_itinerary_version = serializer.validated_data.get(
            "active_itinerary_version"
        )
        try:
            result = orchestrate_chat(
                message,
                history=history,
                current_location=current_location,
                active_itinerary_id=active_itinerary_id,
                active_itinerary_version=active_itinerary_version,
            )
        except OutputParserException:
            logger.exception("Travel chatbot semantic interpretation failed")
            return Response(
                {
                    "error": (
                        "Chatbot chưa hiểu được thao tác lịch trình. "
                        "Vui lòng diễn đạt lại yêu cầu."
                    )
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        except Exception:
            logger.exception("Travel chatbot request failed")
            return Response(
                {"error": CHAT_SERVICE_ERROR},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        if result.client_tool_call is not None:
            return Response(
                {
                    "type": "client_tool_call",
                    "toolCall": {
                        "name": result.client_tool_call,
                        "arguments": {},
                    },
                },
                status=status.HTTP_200_OK,
            )

        payload = {
            "answer": result.answer,
            "sources": [
                source.model_dump(mode="json") for source in result.sources
            ],
            "places": [
                place.model_dump(
                    mode="json",
                    by_alias=True,
                    exclude_none=True,
                    exclude_defaults=True,
                )
                for place in result.places
            ],
        }
        if result.itinerary is not None:
            payload["itinerary"] = result.itinerary.model_dump(
                mode="json",
                by_alias=True,
                exclude_none=True,
            )
        if result.itinerary_operation is not None:
            payload["itineraryOperation"] = result.itinerary_operation

        return Response(payload, status=status.HTTP_200_OK)


__all__ = ["CHAT_SERVICE_ERROR", "ChatAPIView"]
