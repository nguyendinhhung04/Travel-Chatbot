using System.Text.Json.Serialization;

namespace Backend.Conversations;

public sealed record ConversationTurnRequest(
    [property: JsonPropertyName("turnId")] string? TurnId,
    [property: JsonPropertyName("userMessage")] ConversationMessageRequest? UserMessage,
    [property: JsonPropertyName("assistantMessage")] ConversationMessageRequest? AssistantMessage)
{
    public ConversationTurnInput ToDomain() => new(
        TurnId ?? string.Empty,
        UserMessage?.Content ?? string.Empty,
        AssistantMessage?.Content ?? string.Empty,
        AssistantMessage?.Sources,
        AssistantMessage?.Places,
        AssistantMessage?.Itinerary);
}

public sealed record ConversationMessageRequest(
    [property: JsonPropertyName("content")] string? Content,
    [property: JsonPropertyName("sources")] IReadOnlyList<ConversationSourceDocument>? Sources = null,
    [property: JsonPropertyName("places")] IReadOnlyList<ConversationPlaceDocument>? Places = null,
    [property: JsonPropertyName("itinerary")] ConversationItinerarySnapshot? Itinerary = null);
