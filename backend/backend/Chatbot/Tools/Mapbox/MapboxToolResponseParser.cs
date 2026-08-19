using System.Text.Json;
using System.Text.Json.Serialization;

namespace Backend.Chatbot.Tools.Mapbox;

internal static class MapboxToolResponseParser
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNameCaseInsensitive = true
    };

    public static MapboxPlaceToolData ParsePlaces(string json)
    {
        var response = JsonSerializer.Deserialize<FeatureCollectionResponse>(json, JsonOptions)
                       ?? throw InvalidResponse();

        if (response.Features is null || string.IsNullOrWhiteSpace(response.Attribution))
        {
            throw InvalidResponse();
        }

        var results = response.Features.Select(ParsePlace).ToArray();
        return new MapboxPlaceToolData(response.Attribution, results);
    }

    public static MapboxCategoryToolData ParseCategories(string json)
    {
        var response = JsonSerializer.Deserialize<CategoryListResponse>(json, JsonOptions)
                       ?? throw InvalidResponse();

        if (response.ListItems is null || string.IsNullOrWhiteSpace(response.Attribution))
        {
            throw InvalidResponse();
        }

        var categories = response.ListItems.Select(item =>
        {
            if (string.IsNullOrWhiteSpace(item.CanonicalId) || string.IsNullOrWhiteSpace(item.Name))
            {
                throw InvalidResponse();
            }

            return new MapboxCategoryItem(item.CanonicalId, item.Name);
        }).ToArray();

        return new MapboxCategoryToolData(response.Attribution, categories);
    }

    private static MapboxPlaceItem ParsePlace(Feature feature)
    {
        var properties = feature.Properties ?? throw InvalidResponse();
        var coordinates = properties.Coordinates;
        var geometryCoordinates = feature.Geometry?.Coordinates;
        var geometryLongitude = geometryCoordinates is { Length: >= 2 }
            ? geometryCoordinates[0]
            : (double?)null;
        var geometryLatitude = geometryCoordinates is { Length: >= 2 }
            ? geometryCoordinates[1]
            : (double?)null;
        var longitude = coordinates?.Longitude ?? geometryLongitude;
        var latitude = coordinates?.Latitude ?? geometryLatitude;

        if (string.IsNullOrWhiteSpace(properties.Name)
            || string.IsNullOrWhiteSpace(properties.MapboxId)
            || string.IsNullOrWhiteSpace(properties.FeatureType)
            || longitude is null
            || latitude is null)
        {
            throw InvalidResponse();
        }

        var name = string.IsNullOrWhiteSpace(properties.PreferredName)
            ? properties.Name
            : properties.PreferredName;
        var fullAddress = FirstNotEmpty(
            properties.FullAddress,
            properties.Address,
            properties.PlaceFormatted);

        return new MapboxPlaceItem(
            properties.MapboxId,
            name,
            properties.FeatureType,
            fullAddress,
            longitude.Value,
            latitude.Value,
            properties.PoiCategories ?? [],
            properties.PoiCategoryIds ?? [],
            properties.OperationalStatus,
            properties.Distance,
            properties.Eta);
    }

    private static string? FirstNotEmpty(params string?[] values) =>
        values.FirstOrDefault(value => !string.IsNullOrWhiteSpace(value));

    private static JsonException InvalidResponse() =>
        new("Mapbox returned an invalid response.");

    private sealed class FeatureCollectionResponse
    {
        [JsonPropertyName("features")]
        public List<Feature>? Features { get; init; }

        [JsonPropertyName("attribution")]
        public string? Attribution { get; init; }
    }

    private sealed class Feature
    {
        [JsonPropertyName("geometry")]
        public Geometry? Geometry { get; init; }

        [JsonPropertyName("properties")]
        public FeatureProperties? Properties { get; init; }
    }

    private sealed class Geometry
    {
        [JsonPropertyName("coordinates")]
        public double[]? Coordinates { get; init; }
    }

    private sealed class FeatureProperties
    {
        [JsonPropertyName("name")]
        public string? Name { get; init; }

        [JsonPropertyName("name_preferred")]
        public string? PreferredName { get; init; }

        [JsonPropertyName("mapbox_id")]
        public string? MapboxId { get; init; }

        [JsonPropertyName("feature_type")]
        public string? FeatureType { get; init; }

        [JsonPropertyName("address")]
        public string? Address { get; init; }

        [JsonPropertyName("full_address")]
        public string? FullAddress { get; init; }

        [JsonPropertyName("place_formatted")]
        public string? PlaceFormatted { get; init; }

        [JsonPropertyName("coordinates")]
        public Coordinates? Coordinates { get; init; }

        [JsonPropertyName("poi_category")]
        public List<string>? PoiCategories { get; init; }

        [JsonPropertyName("poi_category_ids")]
        public List<string>? PoiCategoryIds { get; init; }

        [JsonPropertyName("operational_status")]
        public string? OperationalStatus { get; init; }

        [JsonPropertyName("distance")]
        public double? Distance { get; init; }

        [JsonPropertyName("eta")]
        public double? Eta { get; init; }
    }

    private sealed class Coordinates
    {
        [JsonPropertyName("longitude")]
        public double? Longitude { get; init; }

        [JsonPropertyName("latitude")]
        public double? Latitude { get; init; }
    }

    private sealed class CategoryListResponse
    {
        [JsonPropertyName("listItems")]
        public List<Category>? ListItems { get; init; }

        [JsonPropertyName("attribution")]
        public string? Attribution { get; init; }
    }

    private sealed class Category
    {
        [JsonPropertyName("canonical_id")]
        public string? CanonicalId { get; init; }

        [JsonPropertyName("name")]
        public string? Name { get; init; }
    }
}
