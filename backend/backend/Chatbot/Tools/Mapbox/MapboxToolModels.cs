using System.Text.Json.Serialization;

namespace Backend.Chatbot.Tools.Mapbox;

public sealed record MapboxPlaceToolData(
    [property: JsonPropertyName("attribution")] string Attribution,
    [property: JsonPropertyName("results")] IReadOnlyList<MapboxPlaceItem> Results);

public sealed record MapboxPlaceSummaryData(
    [property: JsonPropertyName("attribution")] string Attribution,
    [property: JsonPropertyName("results")] IReadOnlyList<MapboxPlaceSummaryItem> Results)
{
    public static MapboxPlaceSummaryData From(MapboxPlaceToolData data) => new(
        data.Attribution,
        data.Results.Select(MapboxPlaceSummaryItem.From).ToArray());
}

public sealed record MapboxPlaceSummaryItem(
    [property: JsonPropertyName("mapboxId")] string MapboxId,
    [property: JsonPropertyName("name")] string Name,
    [property: JsonPropertyName("fullAddress")]
    [property: JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    string? FullAddress,
    [property: JsonPropertyName("longitude")] double Longitude,
    [property: JsonPropertyName("latitude")] double Latitude,
    [property: JsonPropertyName("poiCategories")] IReadOnlyList<string> PoiCategories,
    [property: JsonPropertyName("operationalStatus")]
    [property: JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    string? OperationalStatus,
    [property: JsonPropertyName("distanceMeters")]
    [property: JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    double? DistanceMeters,
    [property: JsonPropertyName("etaMinutes")]
    [property: JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    double? EtaMinutes,
    [property: JsonPropertyName("rating")]
    [property: JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    double? Rating)
{
    public static MapboxPlaceSummaryItem From(MapboxPlaceItem place) => new(
        place.MapboxId,
        place.Name,
        place.FullAddress,
        place.Longitude,
        place.Latitude,
        place.PoiCategories,
        place.OperationalStatus,
        place.DistanceMeters,
        place.EtaMinutes,
        place.Rating);
}

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
