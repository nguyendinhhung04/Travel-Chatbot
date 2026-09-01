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
        using var document = JsonDocument.Parse(json);
        var providerResponse = document.RootElement.Clone();
        var response = providerResponse.Deserialize<FeatureCollectionResponse>(JsonOptions)
                       ?? throw InvalidResponse();

        if (response.Features is null || string.IsNullOrWhiteSpace(response.Attribution))
        {
            throw InvalidResponse();
        }

        var results = response.Features.Select(ParsePlace).ToArray();
        return new MapboxPlaceToolData(response.Attribution, results);
    }

    public static MapboxPlaceToolData ParseCategoryPlaces(
        string json,
        double minimumRating,
        int resultLimit)
    {
        var data = ParsePlaces(json);
        var results = data.Results
            .Where(place => place.Rating is null || place.Rating >= minimumRating)
            .OrderByDescending(place => place.Popularity.HasValue)
            .ThenByDescending(place => place.Popularity)
            .Take(resultLimit)
            .ToArray();

        return data with { Results = results };
    }

    public static MapboxPlacesDetailsData ParsePlaceDetails(string json)
    {
        var response = JsonSerializer.Deserialize<PlacesDetailsResponse>(json, JsonOptions)
                       ?? throw InvalidResponse();
        var results = (response.Results ?? []).Select(place =>
        {
            if (string.IsNullOrWhiteSpace(place.MapboxId)
                || string.IsNullOrWhiteSpace(place.Name)
                || place.Coordinates?.Longitude is null
                || place.Coordinates.Latitude is null)
            {
                throw InvalidResponse();
            }

            var photos = (place.Photos ?? [])
                .Where(photo => !string.IsNullOrWhiteSpace(photo.Url))
                .Select(photo => new MapboxPlacePhoto(
                    photo.Url!, photo.Width, photo.Height, photo.Source))
                .ToArray();
            return new MapboxPlaceDetailsItem(
                place.MapboxId,
                place.Name,
                place.FullAddress,
                place.Brand,
                place.PrimaryCategory,
                place.Categories ?? [],
                place.OpeningHours,
                place.PermanentlyClosed,
                place.Phone,
                place.Website,
                place.Status,
                place.Coordinates.Longitude.Value,
                place.Coordinates.Latitude.Value,
                place.Score?.Popularity,
                photos);
        }).ToArray();

        return new MapboxPlacesDetailsData(
            results,
            response.Missing ?? [],
            response.Unprocessed ?? []);
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
            properties.Eta,
            properties.Metadata?.Rating,
            properties.Metadata?.Popularity);
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

        [JsonPropertyName("metadata")]
        public FeatureMetadata? Metadata { get; init; }
    }

    private sealed class FeatureMetadata
    {
        [JsonPropertyName("rating")]
        public double? Rating { get; init; }

        [JsonPropertyName("popularity")]
        public double? Popularity { get; init; }
    }

    private sealed class Coordinates
    {
        [JsonPropertyName("longitude")]
        public double? Longitude { get; init; }

        [JsonPropertyName("latitude")]
        public double? Latitude { get; init; }
    }

    private sealed class PlacesDetailsResponse
    {
        [JsonPropertyName("results")]
        public List<PlaceDetails>? Results { get; init; }

        [JsonPropertyName("missing")]
        public List<string>? Missing { get; init; }

        [JsonPropertyName("unprocessed")]
        public List<string>? Unprocessed { get; init; }
    }

    private sealed class PlaceDetails
    {
        [JsonPropertyName("mapbox_id")]
        public string? MapboxId { get; init; }

        [JsonPropertyName("name")]
        public string? Name { get; init; }

        [JsonPropertyName("full_address")]
        public string? FullAddress { get; init; }

        [JsonPropertyName("brand")]
        public string? Brand { get; init; }

        [JsonPropertyName("primary_category")]
        public string? PrimaryCategory { get; init; }

        [JsonPropertyName("categories")]
        public List<string>? Categories { get; init; }

        [JsonPropertyName("opening_hours")]
        public string? OpeningHours { get; init; }

        [JsonPropertyName("permanently_closed")]
        public bool? PermanentlyClosed { get; init; }

        [JsonPropertyName("phone")]
        public string? Phone { get; init; }

        [JsonPropertyName("website")]
        public string? Website { get; init; }

        [JsonPropertyName("status")]
        public string? Status { get; init; }

        [JsonPropertyName("coordinates")]
        public Coordinates? Coordinates { get; init; }

        [JsonPropertyName("score")]
        public PlaceScore? Score { get; init; }

        [JsonPropertyName("photos")]
        public List<PlacePhoto>? Photos { get; init; }
    }

    private sealed class PlaceScore
    {
        [JsonPropertyName("popularity")]
        public double? Popularity { get; init; }
    }

    private sealed class PlacePhoto
    {
        [JsonPropertyName("url")]
        public string? Url { get; init; }

        [JsonPropertyName("width")]
        public int? Width { get; init; }

        [JsonPropertyName("height")]
        public int? Height { get; init; }

        [JsonPropertyName("source")]
        public string? Source { get; init; }
    }

}
