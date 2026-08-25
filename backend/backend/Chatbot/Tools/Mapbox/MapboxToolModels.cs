using System.Text.Json.Serialization;

namespace Backend.Chatbot.Tools.Mapbox;

public sealed record MapboxPlaceToolData(
    [property: JsonPropertyName("attribution")] string Attribution,
    [property: JsonPropertyName("results")] IReadOnlyList<MapboxPlaceItem> Results);

public sealed record MapboxPlaceItem(
    [property: JsonPropertyName("mapboxId")] string MapboxId,
    [property: JsonPropertyName("name")] string Name,
    [property: JsonPropertyName("featureType")] string FeatureType,
    [property: JsonPropertyName("fullAddress")] string? FullAddress,
    [property: JsonPropertyName("longitude")] double Longitude,
    [property: JsonPropertyName("latitude")] double Latitude,
    [property: JsonPropertyName("poiCategories")] IReadOnlyList<string> PoiCategories,
    [property: JsonPropertyName("poiCategoryIds")] IReadOnlyList<string> PoiCategoryIds,
    [property: JsonPropertyName("operationalStatus")] string? OperationalStatus,
    [property: JsonPropertyName("distanceMeters")] double? DistanceMeters,
    [property: JsonPropertyName("etaMinutes")] double? EtaMinutes,
    [property: JsonPropertyName("rating")] double? Rating,
    [property: JsonPropertyName("popularity")] double? Popularity);
