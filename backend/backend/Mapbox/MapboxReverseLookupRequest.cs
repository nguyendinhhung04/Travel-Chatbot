using System.ComponentModel.DataAnnotations;
using Microsoft.AspNetCore.Mvc;

namespace Backend.Mapbox;

public sealed class MapboxReverseLookupRequest : IValidatableObject
{
    private static readonly HashSet<string> AllowedTypes = new(StringComparer.OrdinalIgnoreCase)
    {
        "country", "region", "prefecture", "postcode", "district", "place", "city",
        "locality", "oaza", "block", "street", "address", "poi", "category"
    };

    public static readonly IReadOnlySet<string> AllowedQueryParameters = new HashSet<string>(
        ["longitude", "latitude", "language", "limit", "country", "types", "show_closed_pois"],
        StringComparer.OrdinalIgnoreCase);

    [FromQuery(Name = "longitude")]
    [Required]
    [Range(-180d, 180d)]
    public double? Longitude { get; init; }

    [FromQuery(Name = "latitude")]
    [Required]
    [Range(-90d, 90d)]
    public double? Latitude { get; init; }

    [FromQuery(Name = "language")]
    public string? Language { get; init; }

    [FromQuery(Name = "limit")]
    [Range(1, 10)]
    public int? Limit { get; init; }

    [FromQuery(Name = "country")]
    public string? Country { get; init; }

    [FromQuery(Name = "types")]
    public string? Types { get; init; }

    [FromQuery(Name = "show_closed_pois")]
    public bool? ShowClosedPois { get; init; }

    public IEnumerable<ValidationResult> Validate(ValidationContext validationContext)
    {
        if (Longitude.HasValue && !double.IsFinite(Longitude.Value))
        {
            yield return Error("longitude phải là một số hữu hạn.", nameof(Longitude));
        }

        if (Latitude.HasValue && !double.IsFinite(Latitude.Value))
        {
            yield return Error("latitude phải là một số hữu hạn.", nameof(Latitude));
        }

        if (!MapboxForwardSearchRequest.IsCountryList(Country))
        {
            yield return Error("country phải là danh sách mã ISO 3166 alpha-2, phân cách bằng dấu phẩy.", nameof(Country));
        }

        if (!MapboxForwardSearchRequest.IsAllowedList(Types, AllowedTypes))
        {
            yield return Error("types chứa loại địa điểm không được Mapbox Reverse Lookup hỗ trợ.", nameof(Types));
        }
    }

    public Dictionary<string, string?> ToQueryParameters()
    {
        var parameters = new Dictionary<string, string?>(StringComparer.Ordinal);
        MapboxForwardSearchRequest.Add(parameters, "longitude", Longitude);
        MapboxForwardSearchRequest.Add(parameters, "latitude", Latitude);
        MapboxForwardSearchRequest.Add(parameters, "language", Language);
        MapboxForwardSearchRequest.Add(parameters, "limit", Limit);
        MapboxForwardSearchRequest.Add(parameters, "country", Country);
        MapboxForwardSearchRequest.Add(parameters, "types", Types);
        MapboxForwardSearchRequest.Add(parameters, "show_closed_pois", ShowClosedPois);
        return parameters;
    }

    private static ValidationResult Error(string message, string memberName) => new(message, [memberName]);
}
