using System.Text.Json.Serialization;
using MongoDB.Bson;
using MongoDB.Bson.Serialization.Attributes;

namespace Backend.Users;

public sealed class UserDocument
{
    [BsonId]
    [BsonRepresentation(BsonType.ObjectId)]
    [JsonPropertyName("id")]
    public required string Id { get; init; }

    [BsonElement("email")]
    [JsonPropertyName("email")]
    public required string Email { get; init; }

    [BsonElement("normalizedEmail")]
    [JsonPropertyName("normalizedEmail")]
    public required string NormalizedEmail { get; init; }

    [BsonElement("displayName")]
    [JsonPropertyName("displayName")]
    public required string DisplayName { get; init; }

    [BsonElement("passwordHash")]
    [JsonIgnore]
    public required string PasswordHash { get; init; }

    [BsonElement("createdAt")]
    [BsonDateTimeOptions(Kind = DateTimeKind.Utc)]
    [JsonPropertyName("createdAt")]
    public required DateTime CreatedAt { get; init; }
}
