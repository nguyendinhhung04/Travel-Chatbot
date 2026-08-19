using System.Text.Json;
using System.Text.Json.Serialization;

namespace Backend.Chatbot.Tools.Mapbox;

public sealed record MapboxPlaceToolData(
    [property: JsonPropertyName("attribution")] string Attribution,
    [property: JsonPropertyName("results")] IReadOnlyList<MapboxPlaceItem> Results,
    [property: JsonPropertyName("rawResponse")] JsonElement RawResponse);

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
    [property: JsonPropertyName("etaMinutes")] double? EtaMinutes);

public sealed record MapboxCategoryToolData(
    [property: JsonPropertyName("attribution")] string Attribution,
    [property: JsonPropertyName("categories")] IReadOnlyList<MapboxCategoryItem> Categories,
    [property: JsonPropertyName("rawResponse")] JsonElement RawResponse);

public sealed record MapboxCategoryItem(
    [property: JsonPropertyName("canonicalId")] string CanonicalId,
    [property: JsonPropertyName("name")] string Name);
