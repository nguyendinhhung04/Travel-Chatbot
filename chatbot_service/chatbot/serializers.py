"""Serializers for the travel chatbot API."""

from collections.abc import Mapping

from rest_framework import serializers


class ChatRequestSerializer(serializers.Serializer):
    """Validate a user's question before sending it to the RAG pipeline."""

    message = serializers.CharField(
        allow_blank=False,
        trim_whitespace=True,
    )

    def to_internal_value(self, data):
        """Reject non-string messages before CharField coerces their value."""
        if isinstance(data, Mapping) and "message" in data:
            if not isinstance(data["message"], str):
                raise serializers.ValidationError(
                    {"message": "This field must be a string."}
                )

        return super().to_internal_value(data)


__all__ = ["ChatRequestSerializer"]
