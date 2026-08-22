using System.ComponentModel.DataAnnotations;
using System.Globalization;
using Microsoft.AspNetCore.Mvc;

namespace Backend.Mapbox;

public sealed class MapboxForwardSearchRequest : IValidatableObject
{
    internal static readonly HashSet<string> AllowedTypes = new(StringComparer.OrdinalIgnoreCase)
    {
        "country", "region", "postcode", "district", "place", "city", "locality",
        "neighborhood", "block", "street", "address", "poi", "category"
    };

    public static readonly IReadOnlySet<string> AllowedQueryParameters = new HashSet<string>(
        [
            "q", "language", "limit", "proximity", "near", "bbox", "radius", "country",
            "types", "poi_category", "poi_category_exclusions", "show_closed_pois", "open_now",
            "minimum_rating", "price_levels", "exclude_fields", "rank_strategy", "sar_type",
            "route", "route_geometry", "time_deviation", "auto_complete", "eta_type",
            "navigation_profile", "origin"
        ],
        StringComparer.OrdinalIgnoreCase);

    [FromQuery(Name = "q")]
    [Required]
    [StringLength(256)]
    public string? Query { get; init; }

    [FromQuery(Name = "language")]
    public string? Language { get; init; }

    [FromQuery(Name = "limit")]
    [Range(1, 10)]
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

    [FromQuery(Name = "poi_category")]
    public string? PoiCategory { get; init; }

    [FromQuery(Name = "poi_category_exclusions")]
    public string? PoiCategoryExclusions { get; init; }

    [FromQuery(Name = "show_closed_pois")]
    public bool? ShowClosedPois { get; init; }

    [FromQuery(Name = "open_now")]
    public bool? OpenNow { get; init; }

    [FromQuery(Name = "minimum_rating")]
    public double? MinimumRating { get; init; }

    [FromQuery(Name = "price_levels")]
    public string? PriceLevels { get; init; }

    [FromQuery(Name = "exclude_fields")]
    public string? ExcludeFields { get; init; }

    [FromQuery(Name = "rank_strategy")]
    public string? RankStrategy { get; init; }

    [FromQuery(Name = "sar_type")]
    public string? SarType { get; init; }

    [FromQuery(Name = "route")]
    public string? Route { get; init; }

    [FromQuery(Name = "route_geometry")]
    public string? RouteGeometry { get; init; }

    [FromQuery(Name = "time_deviation")]
    public double? TimeDeviation { get; init; }

    [FromQuery(Name = "auto_complete")]
    public bool? AutoComplete { get; init; }

    [FromQuery(Name = "eta_type")]
    public string? EtaType { get; init; }

    [FromQuery(Name = "navigation_profile")]
    public string? NavigationProfile { get; init; }

    [FromQuery(Name = "origin")]
    public string? Origin { get; init; }

    public IEnumerable<ValidationResult> Validate(ValidationContext validationContext)
    {
        if (string.IsNullOrWhiteSpace(Query))
        {
            yield return Error("q là tham số bắt buộc.", nameof(Query));
        }

        if (!string.IsNullOrWhiteSpace(Proximity)
            && !Proximity.Equals("ip", StringComparison.OrdinalIgnoreCase)
            && !IsCoordinatePair(Proximity))
        {
            yield return Error("proximity phải là 'ip' hoặc cặp longitude,latitude hợp lệ.", nameof(Proximity));
        }

        if (!string.IsNullOrWhiteSpace(BoundingBox) && !IsBoundingBox(BoundingBox))
        {
            yield return Error(
                "bbox phải có dạng minLongitude,minLatitude,maxLongitude,maxLatitude và không cắt kinh tuyến 180°.",
                nameof(BoundingBox));
        }

        if (Radius is < 0.00001 or > 10)
        {
            yield return Error("radius phải nằm trong khoảng 0.00001 đến 10 độ.", nameof(Radius));
        }

        if (Radius.HasValue && !IsCoordinatePair(Proximity))
        {
            yield return Error("radius yêu cầu proximity là một cặp longitude,latitude.", nameof(Radius));
        }

        if (!IsCountryList(Country))
        {
            yield return Error("country phải là danh sách mã ISO 3166 alpha-2, phân cách bằng dấu phẩy.", nameof(Country));
        }

        if (!IsAllowedList(Types, AllowedTypes))
        {
            yield return Error("types chứa loại địa điểm không được Mapbox hỗ trợ.", nameof(Types));
        }

        if (MinimumRating is < 0 or > 5)
        {
            yield return Error("minimum_rating phải nằm trong khoảng 0 đến 5.", nameof(MinimumRating));
        }

        if (!IsAllowedList(PriceLevels, ["$", "$$", "$$$", "$$$$"]))
        {
            yield return Error("price_levels chỉ chấp nhận $, $$, $$$ hoặc $$$$.", nameof(PriceLevels));
        }

        if (!IsAllowedList(ExcludeFields, ["photos", "reviews"]))
        {
            yield return Error("exclude_fields chỉ chấp nhận photos hoặc reviews.", nameof(ExcludeFields));
        }

        if (!IsOneOf(RankStrategy, "distance", "relevance"))
        {
            yield return Error("rank_strategy chỉ chấp nhận distance hoặc relevance.", nameof(RankStrategy));
        }

        if (!IsOneOf(SarType, "isochrone"))
        {
            yield return Error("sar_type chỉ chấp nhận isochrone.", nameof(SarType));
        }

        if (!IsOneOf(RouteGeometry, "polyline", "polyline6"))
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

        if (!IsOneOf(EtaType, "navigation"))
        {
            yield return Error("eta_type chỉ chấp nhận navigation.", nameof(EtaType));
        }

        if (!IsOneOf(NavigationProfile, "driving", "walking", "cycling"))
        {
            yield return Error(
                "navigation_profile chỉ chấp nhận driving, walking hoặc cycling.",
                nameof(NavigationProfile));
        }

        if (!string.IsNullOrWhiteSpace(Origin) && !IsCoordinatePair(Origin))
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
        var parameters = new Dictionary<string, string?>(StringComparer.Ordinal)
        {
            ["q"] = Query?.Trim()
        };

        Add(parameters, "language", Language);
        Add(parameters, "limit", Limit);
        Add(parameters, "proximity", Proximity);
        Add(parameters, "near", Near);
        Add(parameters, "bbox", BoundingBox);
        Add(parameters, "radius", Radius);
        Add(parameters, "country", Country);
        Add(parameters, "types", Types);
        Add(parameters, "poi_category", PoiCategory);
        Add(parameters, "poi_category_exclusions", PoiCategoryExclusions);
        Add(parameters, "show_closed_pois", ShowClosedPois);
        Add(parameters, "open_now", OpenNow);
        Add(parameters, "minimum_rating", MinimumRating);
        Add(parameters, "price_levels", PriceLevels);
        Add(parameters, "exclude_fields", ExcludeFields);
        Add(parameters, "rank_strategy", RankStrategy);
        Add(parameters, "sar_type", SarType);
        Add(parameters, "route", Route);
        Add(parameters, "route_geometry", RouteGeometry);
        Add(parameters, "time_deviation", TimeDeviation);
        Add(parameters, "auto_complete", AutoComplete);
        Add(parameters, "eta_type", EtaType);
        Add(parameters, "navigation_profile", NavigationProfile);
        Add(parameters, "origin", Origin);

        return parameters;
    }

    internal static void Add(Dictionary<string, string?> parameters, string name, string? value)
    {
        if (!string.IsNullOrWhiteSpace(value))
        {
            parameters[name] = value.Trim();
        }
    }

    internal static void Add<T>(Dictionary<string, string?> parameters, string name, T? value)
        where T : struct
    {
        if (!value.HasValue)
        {
            return;
        }

        parameters[name] = value.Value switch
        {
            bool boolean => boolean ? "true" : "false",
            IFormattable formattable => formattable.ToString(null, CultureInfo.InvariantCulture),
            _ => value.Value.ToString()
        };
    }

    private static ValidationResult Error(string message, string memberName) => new(message, [memberName]);

    internal static bool IsOneOf(string? value, params string[] allowed) =>
        string.IsNullOrWhiteSpace(value)
        || allowed.Contains(value.Trim(), StringComparer.OrdinalIgnoreCase);

    internal static bool IsAllowedList(string? value, IEnumerable<string> allowed)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return true;
        }

        var allowedValues = allowed.ToHashSet(StringComparer.OrdinalIgnoreCase);
        var values = value.Split(',', StringSplitOptions.TrimEntries);
        return values.Length > 0 && values.All(item => item.Length > 0 && allowedValues.Contains(item));
    }

    internal static bool IsCountryList(string? value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return true;
        }

        var countries = value.Split(',', StringSplitOptions.TrimEntries);
        return countries.All(code => code.Length == 2 && code.All(char.IsAsciiLetter));
    }

    internal static bool IsCoordinatePair(string? value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return false;
        }

        var values = value.Split(',', StringSplitOptions.TrimEntries);
        return values.Length == 2
               && TryCoordinate(values[0], -180, 180, out _)
               && TryCoordinate(values[1], -90, 90, out _);
    }

    internal static bool IsBoundingBox(string value)
    {
        var values = value.Split(',', StringSplitOptions.TrimEntries);
        if (values.Length != 4
            || !TryCoordinate(values[0], -180, 180, out var minLongitude)
            || !TryCoordinate(values[1], -90, 90, out var minLatitude)
            || !TryCoordinate(values[2], -180, 180, out var maxLongitude)
            || !TryCoordinate(values[3], -90, 90, out var maxLatitude))
        {
            return false;
        }

        return minLongitude <= maxLongitude && minLatitude <= maxLatitude;
    }

    private static bool TryCoordinate(string value, double minimum, double maximum, out double coordinate) =>
        double.TryParse(value, NumberStyles.Float, CultureInfo.InvariantCulture, out coordinate)
        && double.IsFinite(coordinate)
        && coordinate >= minimum
        && coordinate <= maximum;
}
