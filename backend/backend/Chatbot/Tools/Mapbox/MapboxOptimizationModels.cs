using System.Text.Json.Serialization;

namespace Backend.Chatbot.Tools.Mapbox;

public sealed record MapboxOptimizationStop(
    [property: JsonPropertyName("mapboxId")] string MapboxId,
    [property: JsonPropertyName("name")] string Name,
    [property: JsonPropertyName("longitude")] double Longitude,
    [property: JsonPropertyName("latitude")] double Latitude);

public sealed record MapboxOptimizationRequest(
    [property: JsonPropertyName("profile")] string Profile,
    [property: JsonPropertyName("stops")] IReadOnlyList<MapboxOptimizationStop> Stops);

public sealed record MapboxOptimizedStop(
    [property: JsonPropertyName("order")] int Order,
    [property: JsonPropertyName("inputIndex")] int InputIndex,
    [property: JsonPropertyName("mapboxId")] string MapboxId,
    [property: JsonPropertyName("name")] string Name,
    [property: JsonPropertyName("longitude")] double Longitude,
    [property: JsonPropertyName("latitude")] double Latitude);

public sealed record GeoJsonLineString(
    [property: JsonPropertyName("type")] string Type,
    [property: JsonPropertyName("coordinates")]
    IReadOnlyList<IReadOnlyList<double>> Coordinates);

public sealed record MapboxOptimizedRouteData(
    [property: JsonPropertyName("profile")] string Profile,
    [property: JsonPropertyName("orderedStops")]
    IReadOnlyList<MapboxOptimizedStop> OrderedStops,
    [property: JsonPropertyName("geometry")] GeoJsonLineString Geometry,
    [property: JsonPropertyName("distanceMeters")] double DistanceMeters,
    [property: JsonPropertyName("durationSeconds")] double DurationSeconds);
