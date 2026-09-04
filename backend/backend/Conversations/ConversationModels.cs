using System.Text.Json.Serialization;
using Backend.Itineraries;
using MongoDB.Bson;
using MongoDB.Bson.Serialization.Attributes;

namespace Backend.Conversations;

public sealed class ConversationDocument
{
    [BsonId]
    [BsonRepresentation(BsonType.ObjectId)]
    [JsonPropertyName("id")]
    public required string Id { get; init; }

    [BsonElement("userId")]
    [JsonPropertyName("userId")]
    public required string UserId { get; init; }

    [BsonElement("title")]
    [JsonPropertyName("title")]
    public required string Title { get; init; }

    [BsonElement("lastMessagePreview")]
    [JsonPropertyName("lastMessagePreview")]
    public string LastMessagePreview { get; init; } = string.Empty;

    [BsonElement("lastTurnIndex")]
    [JsonPropertyName("lastTurnIndex")]
    public int LastTurnIndex { get; init; }

    [BsonElement("createdAt")]
    [BsonDateTimeOptions(Kind = DateTimeKind.Utc)]
    [JsonPropertyName("createdAt")]
    public required DateTime CreatedAt { get; init; }

    [BsonElement("updatedAt")]
    [BsonDateTimeOptions(Kind = DateTimeKind.Utc)]
    [JsonPropertyName("updatedAt")]
    public required DateTime UpdatedAt { get; init; }
}

public sealed class MessageDocument
{
    [BsonId]
    [BsonRepresentation(BsonType.ObjectId)]
    [JsonPropertyName("id")]
    public required string Id { get; init; }

    [BsonElement("conversationId")]
    [JsonPropertyName("conversationId")]
    public required string ConversationId { get; init; }

    [BsonElement("userId")]
    [JsonPropertyName("userId")]
    public required string UserId { get; init; }

    [BsonElement("turnId")]
    [JsonPropertyName("turnId")]
    public required string TurnId { get; init; }

    [BsonElement("turnIndex")]
    [JsonPropertyName("turnIndex")]
    public required int TurnIndex { get; init; }

    [BsonElement("role")]
    [JsonPropertyName("role")]
    public required string Role { get; init; }

    [BsonElement("content")]
    [JsonPropertyName("content")]
    public required string Content { get; init; }

    [BsonElement("sources")]
    [JsonPropertyName("sources")]
    public IReadOnlyList<ConversationSourceDocument> Sources { get; init; } = [];

    [BsonElement("places")]
    [JsonPropertyName("places")]
    public IReadOnlyList<ConversationPlaceDocument> Places { get; init; } = [];

    [BsonElement("itinerary")]
    [BsonIgnoreIfNull]
    [JsonPropertyName("itinerary")]
    public ConversationItinerarySnapshot? Itinerary { get; init; }

    [BsonElement("createdAt")]
    [BsonDateTimeOptions(Kind = DateTimeKind.Utc)]
    [JsonPropertyName("createdAt")]
    public required DateTime CreatedAt { get; init; }
}

public sealed class ConversationSourceDocument
{
    [BsonElement("type")]
    [JsonPropertyName("type")]
    public required string Type { get; init; }

    [BsonElement("title")]
    [JsonPropertyName("title")]
    public required string Title { get; init; }

    [BsonElement("source")]
    [JsonPropertyName("source")]
    public required string Source { get; init; }

    [BsonElement("attribution")]
    [BsonIgnoreIfNull]
    [JsonPropertyName("attribution")]
    public string? Attribution { get; init; }
}

public sealed class ConversationPlaceDocument
{
    [BsonElement("mapboxId")]
    [JsonPropertyName("mapboxId")]
    public required string MapboxId { get; init; }

    [BsonElement("name")]
    [JsonPropertyName("name")]
    public required string Name { get; init; }

    [BsonElement("longitude")]
    [JsonPropertyName("longitude")]
    public required double Longitude { get; init; }

    [BsonElement("latitude")]
    [JsonPropertyName("latitude")]
    public required double Latitude { get; init; }

    [BsonElement("fullAddress")]
    [BsonIgnoreIfNull]
    [JsonPropertyName("fullAddress")]
    public string? FullAddress { get; init; }

    [BsonElement("brand")]
    [BsonIgnoreIfNull]
    [JsonPropertyName("brand")]
    public string? Brand { get; init; }

    [BsonElement("primaryCategory")]
    [BsonIgnoreIfNull]
    [JsonPropertyName("primaryCategory")]
    public string? PrimaryCategory { get; init; }

    [BsonElement("categories")]
    [JsonPropertyName("categories")]
    public IReadOnlyList<string> Categories { get; init; } = [];

    [BsonElement("openingHours")]
    [BsonIgnoreIfNull]
    [JsonPropertyName("openingHours")]
    public string? OpeningHours { get; init; }

    [BsonElement("permanentlyClosed")]
    [BsonIgnoreIfNull]
    [JsonPropertyName("permanentlyClosed")]
    public bool? PermanentlyClosed { get; init; }

    [BsonElement("phone")]
    [BsonIgnoreIfNull]
    [JsonPropertyName("phone")]
    public string? Phone { get; init; }

    [BsonElement("website")]
    [BsonIgnoreIfNull]
    [JsonPropertyName("website")]
    public string? Website { get; init; }

    [BsonElement("operationalStatus")]
    [BsonIgnoreIfNull]
    [JsonPropertyName("operationalStatus")]
    public string? OperationalStatus { get; init; }

    [BsonElement("rating")]
    [BsonIgnoreIfNull]
    [JsonPropertyName("rating")]
    public double? Rating { get; init; }

    [BsonElement("popularity")]
    [BsonIgnoreIfNull]
    [JsonPropertyName("popularity")]
    public double? Popularity { get; init; }

    [BsonElement("photos")]
    [JsonPropertyName("photos")]
    public IReadOnlyList<ConversationPhotoDocument> Photos { get; init; } = [];
}

public sealed class ConversationPhotoDocument
{
    [BsonElement("url")]
    [JsonPropertyName("url")]
    public required string Url { get; init; }

    [BsonElement("width")]
    [BsonIgnoreIfNull]
    [JsonPropertyName("width")]
    public int? Width { get; init; }

    [BsonElement("height")]
    [BsonIgnoreIfNull]
    [JsonPropertyName("height")]
    public int? Height { get; init; }

    [BsonElement("source")]
    [BsonIgnoreIfNull]
    [JsonPropertyName("source")]
    public string? Source { get; init; }
}

public sealed class ConversationItinerarySnapshot
{
    [BsonElement("id")]
    [JsonPropertyName("id")]
    public required string Id { get; init; }

    [BsonElement("version")]
    [JsonPropertyName("version")]
    public required int Version { get; init; }

    [BsonElement("title")]
    [JsonPropertyName("title")]
    public required string Title { get; init; }

    [BsonElement("destination")]
    [JsonPropertyName("destination")]
    public required string Destination { get; init; }

    [BsonElement("durationDays")]
    [JsonPropertyName("durationDays")]
    public required int DurationDays { get; init; }

    [BsonElement("durationNights")]
    [JsonPropertyName("durationNights")]
    public required int DurationNights { get; init; }

    [BsonElement("profile")]
    [JsonPropertyName("profile")]
    public required string Profile { get; init; }

    [BsonElement("stops")]
    [JsonPropertyName("stops")]
    public required IReadOnlyList<ItineraryStopDocument> Stops { get; init; }

    [BsonElement("route")]
    [JsonPropertyName("route")]
    public required ItineraryRouteDocument Route { get; init; }

    [BsonElement("distanceMeters")]
    [JsonPropertyName("distanceMeters")]
    public required double DistanceMeters { get; init; }

    [BsonElement("durationSeconds")]
    [JsonPropertyName("durationSeconds")]
    public required double DurationSeconds { get; init; }
}

public sealed record ConversationTurnInput(
    string TurnId,
    string UserContent,
    string AssistantContent,
    IReadOnlyList<ConversationSourceDocument>? Sources = null,
    IReadOnlyList<ConversationPlaceDocument>? Places = null,
    ConversationItinerarySnapshot? Itinerary = null);

public sealed record ConversationDetails(
    ConversationDocument Conversation,
    IReadOnlyList<MessageDocument> Messages);
