using System.ComponentModel.DataAnnotations;
using System.Text.Json.Serialization;

namespace Backend.Chatbot.Tools.Mapbox;

public sealed record MapboxPlacesDetailsHttpRequest : IValidatableObject
{
    [JsonPropertyName("ids")]
    public IReadOnlyList<string> Ids { get; init; } = [];

    public IEnumerable<ValidationResult> Validate(ValidationContext validationContext)
    {
        if (Ids.Count is < 1 or > 100)
        {
            yield return new ValidationResult(
                "ids phải chứa từ 1 đến 100 Mapbox ID.",
                [nameof(Ids)]);
            yield break;
        }

        if (Ids.Any(string.IsNullOrWhiteSpace))
        {
            yield return new ValidationResult(
                "ids không được chứa giá trị rỗng.",
                [nameof(Ids)]);
        }

        if (Ids.Distinct(StringComparer.Ordinal).Count() != Ids.Count)
        {
            yield return new ValidationResult(
                "ids không được chứa Mapbox ID trùng lặp.",
                [nameof(Ids)]);
        }
    }
}

public sealed record MapboxPlacesDetailsData(
    [property: JsonPropertyName("results")] IReadOnlyList<MapboxPlaceDetailsItem> Results,
    [property: JsonPropertyName("missing")] IReadOnlyList<string> Missing,
    [property: JsonPropertyName("unprocessed")] IReadOnlyList<string> Unprocessed);

public sealed record MapboxPlaceDetailsItem(
    [property: JsonPropertyName("mapboxId")] string MapboxId,
    [property: JsonPropertyName("name")] string Name,
    [property: JsonPropertyName("fullAddress")] string? FullAddress,
    [property: JsonPropertyName("brand")] string? Brand,
    [property: JsonPropertyName("primaryCategory")] string? PrimaryCategory,
    [property: JsonPropertyName("categories")] IReadOnlyList<string> Categories,
    [property: JsonPropertyName("openingHours")] string? OpeningHours,
    [property: JsonPropertyName("permanentlyClosed")] bool? PermanentlyClosed,
    [property: JsonPropertyName("phone")] string? Phone,
    [property: JsonPropertyName("website")] string? Website,
    [property: JsonPropertyName("status")] string? Status,
    [property: JsonPropertyName("longitude")] double Longitude,
    [property: JsonPropertyName("latitude")] double Latitude,
    [property: JsonPropertyName("popularity")] double? Popularity,
    [property: JsonPropertyName("photos")] IReadOnlyList<MapboxPlacePhoto> Photos);

public sealed record MapboxPlacePhoto(
    [property: JsonPropertyName("url")] string Url,
    [property: JsonPropertyName("width")] int? Width,
    [property: JsonPropertyName("height")] int? Height,
    [property: JsonPropertyName("source")] string? Source);
