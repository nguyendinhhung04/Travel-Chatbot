using System.ComponentModel.DataAnnotations;
using Microsoft.AspNetCore.Mvc;

namespace Backend.Mapbox;

public sealed class MapboxCategorySearchRequest : IValidatableObject
{
    public static readonly IReadOnlySet<string> AllowedQueryParameters = new HashSet<string>(
        [
            "language", "limit", "proximity", "near", "bbox", "radius", "country", "types",
            "poi_category_exclusions", "show_closed_pois", "exclude_fields", "sar_type", "route",
            "route_geometry", "time_deviation", "eta_type", "navigation_profile", "origin"
        ],
        StringComparer.OrdinalIgnoreCase);

    [FromQuery(Name = "language")]
    public string? Language { get; init; }

    [FromQuery(Name = "limit")]
    [Range(1, 25)]
    public int? Limit { get; init; }

    [FromQuery(Name = "proximity")]
    public string? Proximity { get; init; }

    [FromQuery(Name = "near")]
    public string? Near { get; init; }

    [FromQuery(Name = "bbox")]
    public string? BoundingBox { get; init; }

    [FromQuery(Name = "radius")]
    public double? Radius { get; init; }

    [FromQuery(Name = "country")]
    public string? Country { get; init; }

    [FromQuery(Name = "types")]
    public string? Types { get; init; }

    [FromQuery(Name = "poi_category_exclusions")]
    public string? PoiCategoryExclusions { get; init; }

    [FromQuery(Name = "show_closed_pois")]
    public bool? ShowClosedPois { get; init; }

    [FromQuery(Name = "exclude_fields")]
    public string? ExcludeFields { get; init; }

    [FromQuery(Name = "sar_type")]
    public string? SarType { get; init; }

    [FromQuery(Name = "route")]
    public string? Route { get; init; }

    [FromQuery(Name = "route_geometry")]
    public string? RouteGeometry { get; init; }

    [FromQuery(Name = "time_deviation")]
    public double? TimeDeviation { get; init; }

    [FromQuery(Name = "eta_type")]
    public string? EtaType { get; init; }

    [FromQuery(Name = "navigation_profile")]
    public string? NavigationProfile { get; init; }

    [FromQuery(Name = "origin")]
    public string? Origin { get; init; }

    public IEnumerable<ValidationResult> Validate(ValidationContext validationContext)
    {
        if (!string.IsNullOrWhiteSpace(Proximity)
            && !Proximity.Equals("ip", StringComparison.OrdinalIgnoreCase)
            && !MapboxForwardSearchRequest.IsCoordinatePair(Proximity))
        {
            yield return Error("proximity phải là 'ip' hoặc cặp longitude,latitude hợp lệ.", nameof(Proximity));
        }

        if (!string.IsNullOrWhiteSpace(BoundingBox)
            && !MapboxForwardSearchRequest.IsBoundingBox(BoundingBox))
        {
            yield return Error(
                "bbox phải có dạng minLongitude,minLatitude,maxLongitude,maxLatitude và không cắt kinh tuyến 180°.",
                nameof(BoundingBox));
        }

        if (Radius is < 0.00001 or > 10)
        {
            yield return Error("radius phải nằm trong khoảng 0.00001 đến 10 độ.", nameof(Radius));
        }

        if (Radius.HasValue && !MapboxForwardSearchRequest.IsCoordinatePair(Proximity))
        {
            yield return Error("radius yêu cầu proximity là một cặp longitude,latitude.", nameof(Radius));
        }

        if (!MapboxForwardSearchRequest.IsCountryList(Country))
        {
            yield return Error("country phải là danh sách mã ISO 3166 alpha-2, phân cách bằng dấu phẩy.", nameof(Country));
        }

        if (!MapboxForwardSearchRequest.IsAllowedList(Types, MapboxForwardSearchRequest.AllowedTypes))
        {
            yield return Error("types chứa loại địa điểm không được Mapbox hỗ trợ.", nameof(Types));
        }

        if (!MapboxForwardSearchRequest.IsAllowedList(ExcludeFields, ["photos", "reviews"]))
        {
            yield return Error("exclude_fields chỉ chấp nhận photos hoặc reviews.", nameof(ExcludeFields));
        }

        if (!MapboxForwardSearchRequest.IsOneOf(SarType, "isochrone"))
        {
            yield return Error("sar_type chỉ chấp nhận isochrone.", nameof(SarType));
        }

        if (!MapboxForwardSearchRequest.IsOneOf(RouteGeometry, "polyline", "polyline6"))
        {
            yield return Error("route_geometry chỉ chấp nhận polyline hoặc polyline6.", nameof(RouteGeometry));
        }

        if (TimeDeviation is < 0)
        {
            yield return Error("time_deviation không được là số âm.", nameof(TimeDeviation));
        }

        var hasSarParameter = !string.IsNullOrWhiteSpace(SarType)
                              || !string.IsNullOrWhiteSpace(Route)
                              || !string.IsNullOrWhiteSpace(RouteGeometry)
                              || TimeDeviation.HasValue;
        if (hasSarParameter && SarType?.Equals("isochrone", StringComparison.OrdinalIgnoreCase) != true)
        {
            yield return Error("Tìm kiếm dọc tuyến đường yêu cầu sar_type=isochrone.", nameof(SarType));
        }

        if (hasSarParameter && string.IsNullOrWhiteSpace(Route))
        {
            yield return Error("Tìm kiếm dọc tuyến đường yêu cầu route.", nameof(Route));
        }

        if (!MapboxForwardSearchRequest.IsOneOf(EtaType, "navigation"))
        {
            yield return Error("eta_type chỉ chấp nhận navigation.", nameof(EtaType));
        }

        if (!MapboxForwardSearchRequest.IsOneOf(NavigationProfile, "driving", "walking", "cycling"))
        {
            yield return Error(
                "navigation_profile chỉ chấp nhận driving, walking hoặc cycling.",
                nameof(NavigationProfile));
        }

        if (!string.IsNullOrWhiteSpace(Origin)
            && !MapboxForwardSearchRequest.IsCoordinatePair(Origin))
        {
            yield return Error("origin phải là cặp longitude,latitude hợp lệ.", nameof(Origin));
        }

        var hasEtaParameter = !string.IsNullOrWhiteSpace(EtaType)
                              || !string.IsNullOrWhiteSpace(NavigationProfile)
                              || !string.IsNullOrWhiteSpace(Origin);
        if (hasEtaParameter && EtaType?.Equals("navigation", StringComparison.OrdinalIgnoreCase) != true)
        {
            yield return Error("Tính ETA yêu cầu eta_type=navigation.", nameof(EtaType));
        }

        if (EtaType?.Equals("navigation", StringComparison.OrdinalIgnoreCase) == true
            && string.IsNullOrWhiteSpace(NavigationProfile))
        {
            yield return Error("Tính ETA yêu cầu navigation_profile.", nameof(NavigationProfile));
        }

        if (EtaType?.Equals("navigation", StringComparison.OrdinalIgnoreCase) == true
            && string.IsNullOrWhiteSpace(Origin)
            && string.IsNullOrWhiteSpace(Proximity))
        {
            yield return Error("Tính ETA yêu cầu origin hoặc proximity.", nameof(EtaType));
        }
    }

    public Dictionary<string, string?> ToQueryParameters()
    {
        var parameters = new Dictionary<string, string?>(StringComparer.Ordinal);
        MapboxForwardSearchRequest.Add(parameters, "language", Language);
        MapboxForwardSearchRequest.Add(parameters, "limit", Limit);
        MapboxForwardSearchRequest.Add(parameters, "proximity", Proximity);
        MapboxForwardSearchRequest.Add(parameters, "near", Near);
        MapboxForwardSearchRequest.Add(parameters, "bbox", BoundingBox);
        MapboxForwardSearchRequest.Add(parameters, "radius", Radius);
        MapboxForwardSearchRequest.Add(parameters, "country", Country);
        MapboxForwardSearchRequest.Add(parameters, "types", Types);
        MapboxForwardSearchRequest.Add(parameters, "poi_category_exclusions", PoiCategoryExclusions);
        MapboxForwardSearchRequest.Add(parameters, "show_closed_pois", ShowClosedPois);
        MapboxForwardSearchRequest.Add(parameters, "exclude_fields", ExcludeFields);
        MapboxForwardSearchRequest.Add(parameters, "sar_type", SarType);
        MapboxForwardSearchRequest.Add(parameters, "route", Route);
        MapboxForwardSearchRequest.Add(parameters, "route_geometry", RouteGeometry);
        MapboxForwardSearchRequest.Add(parameters, "time_deviation", TimeDeviation);
        MapboxForwardSearchRequest.Add(parameters, "eta_type", EtaType);
        MapboxForwardSearchRequest.Add(parameters, "navigation_profile", NavigationProfile);
        MapboxForwardSearchRequest.Add(parameters, "origin", Origin);
        return parameters;
    }

    private static ValidationResult Error(string message, string memberName) => new(message, [memberName]);
}
