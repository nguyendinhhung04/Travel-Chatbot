using System.ComponentModel.DataAnnotations;
using System.Text.Json.Serialization;
using Backend.Mapbox;

namespace Backend.Chatbot.Tools.Mapbox;

public sealed record MapboxForwardSearchToolHttpRequest
{
    [JsonPropertyName("q")]
    public string? Query { get; init; }

    [JsonPropertyName("language")]
    public string? Language { get; init; }

    [JsonPropertyName("limit")]
    public int? Limit { get; init; }

    [JsonPropertyName("proximity")]
    public string? Proximity { get; init; }

    [JsonPropertyName("near")]
    public string? Near { get; init; }

    [JsonPropertyName("bbox")]
    public string? BoundingBox { get; init; }

    [JsonPropertyName("radius")]
    public double? Radius { get; init; }

    [JsonPropertyName("country")]
    public string? Country { get; init; }

    [JsonPropertyName("types")]
    public string? Types { get; init; }

    [JsonPropertyName("poi_category")]
    public string? PoiCategory { get; init; }

    [JsonPropertyName("poi_category_exclusions")]
    public string? PoiCategoryExclusions { get; init; }

    [JsonPropertyName("show_closed_pois")]
    public bool? ShowClosedPois { get; init; }

    [JsonPropertyName("open_now")]
    public bool? OpenNow { get; init; }

    [JsonPropertyName("minimum_rating")]
    public double? MinimumRating { get; init; }

    [JsonPropertyName("price_levels")]
    public string? PriceLevels { get; init; }

    [JsonPropertyName("exclude_fields")]
    public string? ExcludeFields { get; init; }

    [JsonPropertyName("rank_strategy")]
    public string? RankStrategy { get; init; }

    [JsonPropertyName("auto_complete")]
    public bool? AutoComplete { get; init; }

    public MapboxForwardSearchRequest ToMapboxRequest() => new()
    {
        Query = Query,
        Language = Language,
        Limit = Limit,
        Proximity = Proximity,
        Near = Near,
        BoundingBox = BoundingBox,
        Radius = Radius,
        Country = Country,
        Types = Types,
        PoiCategory = PoiCategory,
        PoiCategoryExclusions = PoiCategoryExclusions,
        ShowClosedPois = ShowClosedPois,
        OpenNow = OpenNow,
        MinimumRating = MinimumRating,
        PriceLevels = PriceLevels,
        ExcludeFields = ExcludeFields,
        RankStrategy = RankStrategy,
        AutoComplete = AutoComplete
    };
}

public sealed record MapboxCategorySearchToolHttpRequest
{
    [JsonPropertyName("category_id")]
    public string? CategoryId { get; init; }

    [JsonPropertyName("language")]
    public string? Language { get; init; }

    [JsonPropertyName("limit")]
    public int? Limit { get; init; }

    [JsonPropertyName("proximity")]
    public string? Proximity { get; init; }

    [JsonPropertyName("near")]
    public string? Near { get; init; }

    [JsonPropertyName("bbox")]
    public string? BoundingBox { get; init; }

    [JsonPropertyName("radius")]
    public double? Radius { get; init; }

    [JsonPropertyName("country")]
    public string? Country { get; init; }

    [JsonPropertyName("types")]
    public string? Types { get; init; }

    [JsonPropertyName("poi_category_exclusions")]
    public string? PoiCategoryExclusions { get; init; }

    [JsonPropertyName("show_closed_pois")]
    public bool? ShowClosedPois { get; init; }

    [JsonPropertyName("exclude_fields")]
    public string? ExcludeFields { get; init; }

    [JsonPropertyName("minimum_rating")]
    [Range(0, 5)]
    public double? MinimumRating { get; init; }

    public MapboxCategorySearchRequest ToMapboxRequest() => new()
    {
        Language = Language,
        Limit = Limit,
        Proximity = Proximity,
        Near = Near,
        BoundingBox = BoundingBox,
        Radius = Radius,
        Country = Country,
        Types = Types,
        PoiCategoryExclusions = PoiCategoryExclusions,
        ShowClosedPois = ShowClosedPois,
        ExcludeFields = ExcludeFields
    };
}

public sealed record MapboxReverseLookupToolHttpRequest
{
    [JsonPropertyName("longitude")]
    public double? Longitude { get; init; }

    [JsonPropertyName("latitude")]
    public double? Latitude { get; init; }

    [JsonPropertyName("language")]
    public string? Language { get; init; }

    [JsonPropertyName("limit")]
    public int? Limit { get; init; }

    [JsonPropertyName("country")]
    public string? Country { get; init; }

    [JsonPropertyName("types")]
    public string? Types { get; init; }

    [JsonPropertyName("show_closed_pois")]
    public bool? ShowClosedPois { get; init; }

    public MapboxReverseLookupRequest ToMapboxRequest() => new()
    {
        Longitude = Longitude,
        Latitude = Latitude,
        Language = Language,
        Limit = Limit,
        Country = Country,
        Types = Types,
        ShowClosedPois = ShowClosedPois
    };
}

public sealed record MapboxCandidateResolveToolHttpRequest
{
    [JsonPropertyName("longitude")]
    public double? Longitude { get; init; }

    [JsonPropertyName("latitude")]
    public double? Latitude { get; init; }

    [JsonPropertyName("candidates")]
    public IReadOnlyList<MapboxCandidateHttpInput>? Candidates { get; init; }

    [JsonPropertyName("categoryId")]
    public string? CategoryId { get; init; }

    [JsonPropertyName("minimumRating")]
    public double? MinimumRating { get; init; }

    public MapboxCandidateResolutionRequest ToResolutionRequest() => new(
        Longitude ?? double.NaN,
        Latitude ?? double.NaN,
        (Candidates ?? []).Select(candidate => candidate.ToCandidate()).ToArray(),
        CategoryId,
        MinimumRating);
}

public sealed record MapboxCandidateHttpInput
{
    [JsonPropertyName("candidateId")]
    public string? CandidateId { get; init; }

    [JsonPropertyName("name")]
    public string? Name { get; init; }

    [JsonPropertyName("aliases")]
    public IReadOnlyList<string>? Aliases { get; init; }

    [JsonPropertyName("categoryHints")]
    public IReadOnlyList<string>? CategoryHints { get; init; }

    public MapboxCandidateInput ToCandidate() => new(
        CandidateId ?? string.Empty,
        Name ?? string.Empty,
        Aliases ?? [],
        CategoryHints ?? []);
}
