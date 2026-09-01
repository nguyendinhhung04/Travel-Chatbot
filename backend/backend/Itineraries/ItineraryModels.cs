using System.Text.Json.Serialization;
using Backend.Chatbot.Tools.Mapbox;
using MongoDB.Bson;
using MongoDB.Bson.Serialization.Attributes;

namespace Backend.Itineraries;

public sealed class ItineraryDocument
{
    [BsonId]
    [BsonRepresentation(BsonType.ObjectId)]
    [JsonPropertyName("id")]
    public required string Id { get; init; }

    [BsonElement("userId")]
    [JsonPropertyName("userId")]
    public required string UserId { get; init; }

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

    [BsonElement("provider")]
    [JsonPropertyName("provider")]
    public string Provider { get; init; } = "mapbox";

    [BsonElement("generatedAt")]
    [BsonDateTimeOptions(Kind = DateTimeKind.Utc)]
    [JsonPropertyName("generatedAt")]
    public required DateTime GeneratedAt { get; init; }

    [BsonElement("createdAt")]
    [BsonDateTimeOptions(Kind = DateTimeKind.Utc)]
    [JsonPropertyName("createdAt")]
    public required DateTime CreatedAt { get; init; }

    [BsonElement("updatedAt")]
    [BsonDateTimeOptions(Kind = DateTimeKind.Utc)]
    [JsonPropertyName("updatedAt")]
    public required DateTime UpdatedAt { get; init; }
}

public sealed class ItineraryStopDocument
{
    [BsonElement("id")]
    [BsonRepresentation(BsonType.ObjectId)]
    [JsonPropertyName("id")]
    public required string Id { get; init; }

    [BsonElement("order")]
    [JsonPropertyName("order")]
    public required int Order { get; init; }

    [BsonElement("inputIndex")]
    [JsonPropertyName("inputIndex")]
    public required int InputIndex { get; init; }

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
}

public sealed class ItineraryRouteDocument
{
    [BsonElement("type")]
    [JsonPropertyName("type")]
    public required string Type { get; init; }

    [BsonElement("coordinates")]
    [JsonPropertyName("coordinates")]
    public required IReadOnlyList<IReadOnlyList<double>> Coordinates { get; init; }

}

public sealed record AddItineraryStopRequest(
    [property: JsonPropertyName("stop")] MapboxOptimizationStop Stop,
    [property: JsonPropertyName("expectedVersion")] int ExpectedVersion,
    [property: JsonPropertyName("position")] string Position = "optimized");

public sealed record CreateItineraryRequest(
    [property: JsonPropertyName("title")] string Title,
    [property: JsonPropertyName("destination")] string Destination,
    [property: JsonPropertyName("durationDays")] int DurationDays,
    [property: JsonPropertyName("durationNights")] int DurationNights,
    [property: JsonPropertyName("profile")] string Profile,
    [property: JsonPropertyName("stops")] IReadOnlyList<MapboxOptimizationStop> Stops);

public sealed record ApiErrorResponse(
    [property: JsonPropertyName("errorCode")] string ErrorCode,
    [property: JsonPropertyName("error")] string Error);
