using System.Globalization;
using System.Text;
using System.Text.RegularExpressions;
using Backend.Chatbot.Tools;
using Backend.Mapbox;

namespace Backend.Chatbot.Tools.Mapbox;

public sealed partial class MapboxCandidateResolverTool(
    MapboxForwardSearchTool forwardSearchTool,
    MapboxCategorySearchTool categorySearchTool)
{
    public const int MaximumCandidates = 5;
    public const double MinimumNameSimilarity = 0.88;
    public const double AmbiguousScoreGap = 0.05;
    public const double MinimumDistanceGapMeters = 100.0;

    public async Task<ToolResult<MapboxCandidateResolutionData>> ExecuteAsync(
        MapboxCandidateResolutionRequest request,
        CancellationToken cancellationToken = default)
    {
        var validationError = Validate(request);
        if (validationError is not null)
        {
            return ToolResult<MapboxCandidateResolutionData>.Failed(
                "invalid_input",
                validationError);
        }

        var matches = new List<MapboxCandidateMatch>();
        string? attribution = null;
        string? firstErrorCode = null;
        string? firstErrorMessage = null;
        var matchedMapboxIds = new HashSet<string>(StringComparer.Ordinal);
        var proximity = FormattableString.Invariant($"{request.Longitude},{request.Latitude}");

        foreach (var candidate in request.Candidates)
        {
            var lookup = await forwardSearchTool.ExecuteAsync(
                new MapboxForwardSearchRequest
                {
                    Query = candidate.Name,
                    Language = "vi",
                    Limit = 2,
                    Proximity = proximity,
                    Types = "poi",
                    RankStrategy = "relevance",
                    AutoComplete = false
                },
                cancellationToken);

            if (!lookup.Success || lookup.Data is null)
            {
                firstErrorCode ??= lookup.ErrorCode;
                firstErrorMessage ??= lookup.ErrorMessage;
                matches.Add(new MapboxCandidateMatch(
                    candidate.CandidateId,
                    StatusValue(MapboxCandidateMatchStatus.LookupFailed),
                    null,
                    null));
                continue;
            }

            attribution ??= lookup.Data.Attribution;
            var match = MatchCandidate(candidate, lookup.Data.Results);
            if (match.Status == StatusValue(MapboxCandidateMatchStatus.Matched)
                && match.Place is not null
                && !matchedMapboxIds.Add(match.Place.MapboxId))
            {
                match = match with
                {
                    Status = StatusValue(MapboxCandidateMatchStatus.Duplicate),
                    Place = null
                };
            }
            matches.Add(match);
        }

        IReadOnlyList<MapboxPlaceItem> categoryPlaces = [];
        if (!string.IsNullOrWhiteSpace(request.CategoryId))
        {
            var category = await categorySearchTool.ExecuteAsync(
                request.CategoryId,
                new MapboxCategorySearchRequest
                {
                    Language = "vi",
                    Limit = 10,
                    Proximity = proximity,
                    Types = "poi"
                },
                cancellationToken,
                request.MinimumRating);

            if (category.Success && category.Data is not null)
            {
                attribution ??= category.Data.Attribution;
                categoryPlaces = category.Data.Results;
            }
            else
            {
                firstErrorCode ??= category.ErrorCode;
                firstErrorMessage ??= category.ErrorMessage;
            }
        }

        if (attribution is null)
        {
            return ToolResult<MapboxCandidateResolutionData>.Failed(
                firstErrorCode ?? "mapbox_unavailable",
                firstErrorMessage ?? "Không nhận được dữ liệu từ Mapbox API.");
        }

        var matchedIds = matches
            .Where(match => match.Status == StatusValue(MapboxCandidateMatchStatus.Matched))
            .Select(match => match.Place?.MapboxId)
            .Where(id => id is not null)
            .ToHashSet(StringComparer.Ordinal);
        var additionalPlaces = categoryPlaces
            .Where(place => matchedIds.Add(place.MapboxId))
            .ToArray();

        return ToolResult<MapboxCandidateResolutionData>.Succeeded(
            new MapboxCandidateResolutionData(attribution, matches, additionalPlaces));
    }

    internal static MapboxCandidateMatch MatchCandidate(
        MapboxCandidateInput candidate,
        IReadOnlyList<MapboxPlaceItem> places)
    {
        var names = new[] { candidate.Name }.Concat(candidate.Aliases).ToArray();
        var scored = places
            .Select(place => new ScoredPlace(
                names.Max(name => NameSimilarity(name, place.Name)),
                CategoryMatches(candidate.CategoryHints, place),
                place))
            .Where(item => item.Score >= MinimumNameSimilarity)
            .ToArray();

        if (scored.Length == 0)
        {
            return Match(candidate, MapboxCandidateMatchStatus.NotFound);
        }

        var exactMatches = scored.Where(item => item.Score == 1.0).ToArray();

        if (exactMatches.Length == 1)
        {
            return Match(candidate, MapboxCandidateMatchStatus.Matched, exactMatches[0]);
        }

        if (exactMatches.Length > 1)
        {
            var exactCategoryMatches = exactMatches
                .Where(item => item.CategoryMatches)
                .ToArray();
            var contenders = (exactCategoryMatches.Length > 0
                    ? exactCategoryMatches
                    : exactMatches)
                .OrderBy(item => item.Place.DistanceMeters ?? double.PositiveInfinity)
                .ToArray();
            if (contenders.Length == 1)
            {
                return Match(candidate, MapboxCandidateMatchStatus.Matched, contenders[0]);
            }

            var firstDistance = contenders[0].Place.DistanceMeters;
            var secondDistance = contenders[1].Place.DistanceMeters;
            if (firstDistance.HasValue
                && secondDistance.HasValue
                && secondDistance.Value - firstDistance.Value >= MinimumDistanceGapMeters)
            {
                return Match(candidate, MapboxCandidateMatchStatus.Matched, contenders[0]);
            }

            return Match(candidate, MapboxCandidateMatchStatus.Ambiguous, contenders[0], false);
        }

        var categoryMatches = scored.Where(item => item.CategoryMatches).ToArray();
        var ranked = (categoryMatches.Length > 0 ? categoryMatches : scored)
            .OrderByDescending(item => item.Score)
            .ThenBy(item => item.Place.DistanceMeters ?? double.PositiveInfinity)
            .ToArray();
        if (ranked.Length > 1 && ranked[0].Score - ranked[1].Score < AmbiguousScoreGap)
        {
            return Match(candidate, MapboxCandidateMatchStatus.Ambiguous, ranked[0], false);
        }

        return Match(candidate, MapboxCandidateMatchStatus.Matched, ranked[0]);
    }

    internal static string NormalizeName(string value)
    {
        var decomposed = value.ToLowerInvariant().Replace('đ', 'd')
            .Normalize(NormalizationForm.FormD);
        var withoutMarks = new string(decomposed
            .Where(character => CharUnicodeInfo.GetUnicodeCategory(character)
                                != UnicodeCategory.NonSpacingMark)
            .ToArray());
        return WhitespaceRegex().Replace(NonAlphaNumericRegex().Replace(withoutMarks, " "), " ")
            .Trim();
    }

    internal static double NameSimilarity(string left, string right)
    {
        var normalizedLeft = NormalizeName(left);
        var normalizedRight = NormalizeName(right);
        if (normalizedLeft.Length == 0 || normalizedRight.Length == 0)
        {
            return 0;
        }

        if (normalizedLeft == normalizedRight)
        {
            return 1;
        }

        var ordered = LongestCommonSubsequenceRatio(normalizedLeft, normalizedRight);
        var sortedLeft = string.Join(' ', normalizedLeft.Split(' ').Order(StringComparer.Ordinal));
        var sortedRight = string.Join(' ', normalizedRight.Split(' ').Order(StringComparer.Ordinal));
        return Math.Max(ordered, LongestCommonSubsequenceRatio(sortedLeft, sortedRight));
    }

    private static string? Validate(MapboxCandidateResolutionRequest request)
    {
        if (!double.IsFinite(request.Longitude) || request.Longitude is < -180 or > 180
            || !double.IsFinite(request.Latitude) || request.Latitude is < -90 or > 90)
        {
            return "longitude hoặc latitude không hợp lệ.";
        }

        if (request.Candidates.Count > MaximumCandidates)
        {
            return $"Chỉ được xác minh tối đa {MaximumCandidates} candidate.";
        }

        if (request.Candidates.Count == 0 && string.IsNullOrWhiteSpace(request.CategoryId))
        {
            return "Phải có ít nhất một candidate hoặc categoryId.";
        }

        if (request.MinimumRating is < 0 or > 5)
        {
            return "minimumRating phải nằm trong khoảng 0 đến 5.";
        }

        if (request.Candidates.Any(candidate =>
                string.IsNullOrWhiteSpace(candidate.CandidateId)
                || string.IsNullOrWhiteSpace(candidate.Name)
                || candidate.Aliases.Count > 5
                || candidate.CategoryHints.Count > 5))
        {
            return "Candidate không hợp lệ.";
        }

        if (request.Candidates.Select(candidate => candidate.CandidateId)
            .Distinct(StringComparer.Ordinal).Count() != request.Candidates.Count)
        {
            return "candidateId không được trùng nhau.";
        }

        return null;
    }

    private static MapboxCandidateMatch Match(
        MapboxCandidateInput candidate,
        MapboxCandidateMatchStatus status,
        ScoredPlace? scored = null,
        bool includePlace = true) => new(
            candidate.CandidateId,
            StatusValue(status),
            scored?.Score,
            includePlace ? scored?.Place : null);

    private static string StatusValue(MapboxCandidateMatchStatus status) => status switch
    {
        MapboxCandidateMatchStatus.Matched => "matched",
        MapboxCandidateMatchStatus.Ambiguous => "ambiguous",
        MapboxCandidateMatchStatus.NotFound => "not_found",
        MapboxCandidateMatchStatus.Duplicate => "duplicate",
        _ => "lookup_failed"
    };

    private static bool CategoryMatches(
        IReadOnlyList<string> hints,
        MapboxPlaceItem place)
    {
        var normalizedHints = hints.Select(NormalizeName)
            .Where(value => value.Length > 0)
            .ToHashSet(StringComparer.Ordinal);
        return place.PoiCategories.Concat(place.PoiCategoryIds)
            .Select(NormalizeName)
            .Any(normalizedHints.Contains);
    }

    private static double LongestCommonSubsequenceRatio(string left, string right)
    {
        var previous = new int[right.Length + 1];
        for (var leftIndex = 1; leftIndex <= left.Length; leftIndex++)
        {
            var current = new int[right.Length + 1];
            for (var rightIndex = 1; rightIndex <= right.Length; rightIndex++)
            {
                current[rightIndex] = left[leftIndex - 1] == right[rightIndex - 1]
                    ? previous[rightIndex - 1] + 1
                    : Math.Max(previous[rightIndex], current[rightIndex - 1]);
            }
            previous = current;
        }
        return 2.0 * previous[right.Length] / (left.Length + right.Length);
    }

    private sealed record ScoredPlace(
        double Score,
        bool CategoryMatches,
        MapboxPlaceItem Place);

    [GeneratedRegex("[^a-z0-9]+")]
    private static partial Regex NonAlphaNumericRegex();

    [GeneratedRegex("\\s+")]
    private static partial Regex WhitespaceRegex();
}
