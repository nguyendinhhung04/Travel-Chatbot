using System.Text.Json.Serialization;

namespace Backend.Chatbot.Tools.Mapbox;

public sealed record MapboxCandidateResolutionRequest(
    double Longitude,
    double Latitude,
    IReadOnlyList<MapboxCandidateInput> Candidates,
    string? CategoryId,
    double? MinimumRating);

public sealed record MapboxCandidateInput(
    string CandidateId,
    string Name,
    IReadOnlyList<string> Aliases,
    IReadOnlyList<string> CategoryHints);

public enum MapboxCandidateMatchStatus
{
    Matched,
    Ambiguous,
    NotFound,
    LookupFailed,
    Duplicate
}

public sealed record MapboxCandidateMatch(
    [property: JsonPropertyName("candidateId")] string CandidateId,
    [property: JsonPropertyName("status")] string Status,
    [property: JsonPropertyName("similarity")] double? Similarity,
    [property: JsonPropertyName("place")] MapboxPlaceItem? Place);

public sealed record MapboxCandidateResolutionData(
    [property: JsonPropertyName("attribution")] string Attribution,
    [property: JsonPropertyName("results")] IReadOnlyList<MapboxCandidateMatch> Results,
    [property: JsonPropertyName("additionalPlaces")] IReadOnlyList<MapboxPlaceItem> AdditionalPlaces);
