"""Serializers for the travel chatbot API."""

from collections.abc import Mapping

from rest_framework import serializers


class ConversationMessageSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=("user", "assistant"))
    content = serializers.CharField(
        allow_blank=False,
        max_length=4000,
        trim_whitespace=True,
    )


class CurrentLocationSerializer(serializers.Serializer):
    near = serializers.CharField(
        required=False,
        allow_blank=False,
        trim_whitespace=True,
    )
    longitude = serializers.FloatField(
        required=False,
        min_value=-180,
        max_value=180,
    )
    latitude = serializers.FloatField(
        required=False,
        min_value=-90,
        max_value=90,
    )
    radius_km = serializers.FloatField(
        required=False,
        min_value=0.00001,
        max_value=10,
    )

    def validate(self, attrs):
        if ("longitude" in attrs) != ("latitude" in attrs):
            raise serializers.ValidationError(
                "longitude and latitude must be provided together."
            )
        return attrs


class ChatRequestSerializer(serializers.Serializer):
    """Validate a stateless question plus optional conversation context."""

    message = serializers.CharField(
        allow_blank=False,
        trim_whitespace=True,
    )
    history = ConversationMessageSerializer(
        many=True,
        required=False,
        max_length=6,
    )
    current_location = CurrentLocationSerializer(required=False)
    active_itinerary_id = serializers.RegexField(
        regex=r"^[0-9a-fA-F]{24}$",
        required=False,
        allow_blank=False,
    )
    active_itinerary_version = serializers.IntegerField(
        required=False,
        min_value=1,
    )

    def validate(self, attrs):
        has_id = "active_itinerary_id" in attrs
        has_version = "active_itinerary_version" in attrs
        if has_id != has_version:
            raise serializers.ValidationError(
                "active_itinerary_id and active_itinerary_version must be provided together."
            )
        return attrs

    def to_internal_value(self, data):
        """Reject non-string messages before CharField coerces their value."""
        if isinstance(data, Mapping) and "message" in data:
            if not isinstance(data["message"], str):
                raise serializers.ValidationError(
                    {"message": "This field must be a string."}
                )

        return super().to_internal_value(data)


__all__ = [
    "ChatRequestSerializer",
    "ConversationMessageSerializer",
    "CurrentLocationSerializer",
]
