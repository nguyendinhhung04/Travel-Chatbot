using System.ComponentModel.DataAnnotations;
using Backend.Mapbox;

namespace Backend.Tests;

public sealed class MapboxForwardSearchRequestTests
{
    [Fact]
    public void Validate_AcceptsAllSupportedParameters()
    {
        var request = new MapboxForwardSearchRequest
        {
            Query = "coffee",
            Language = "en",
            Limit = 10,
            Proximity = "2.2945,48.8584",
            Near = "Paris",
            BoundingBox = "2.0,48.0,3.0,49.0",
            Radius = 1,
            Country = "FR,US",
            Types = "poi,address",
            PoiCategory = "coffee",
            PoiCategoryExclusions = "hotel",
            ShowClosedPois = true,
            OpenNow = true,
            MinimumRating = 4.5,
            PriceLevels = "$,$$",
            ExcludeFields = "photos,reviews",
            RankStrategy = "distance",
            SarType = "isochrone",
            Route = "encoded-route",
            RouteGeometry = "polyline6",
            TimeDeviation = 5,
            AutoComplete = true,
            EtaType = "navigation",
            NavigationProfile = "walking",
            Origin = "2.3,48.8"
        };

        var errors = Validate(request);

        Assert.Empty(errors);
        Assert.Equal(25, request.ToQueryParameters().Count);
    }

    [Theory]
    [InlineData(null, null, null, "Query")]
    [InlineData("Paris", "ip", 1.0, "Radius")]
    [InlineData("Paris", "181,10", null, "Proximity")]
    public void Validate_RejectsInvalidCoreParameters(
        string? query,
        string? proximity,
        double? radius,
        string invalidMember)
    {
        var request = new MapboxForwardSearchRequest
        {
            Query = query,
            Proximity = proximity,
            Radius = radius
        };

        var errors = Validate(request);

        Assert.Contains(errors, error =>
            error.MemberNames.Contains(invalidMember, StringComparer.OrdinalIgnoreCase));
    }

    [Fact]
    public void Validate_RequiresRouteForSearchAlongRoute()
    {
        var request = new MapboxForwardSearchRequest
        {
            Query = "restaurant",
            SarType = "isochrone"
        };

        var errors = Validate(request);

        Assert.Contains(errors, error => error.MemberNames.Contains(nameof(request.Route)));
    }

    [Fact]
    public void Validate_RequiresNavigationProfileAndLocationForEta()
    {
        var request = new MapboxForwardSearchRequest
        {
            Query = "hotel",
            EtaType = "navigation"
        };

        var errors = Validate(request);

        Assert.Contains(errors, error => error.MemberNames.Contains(nameof(request.NavigationProfile)));
        Assert.Contains(errors, error => error.MemberNames.Contains(nameof(request.EtaType)));
    }

    private static IReadOnlyList<ValidationResult> Validate(MapboxForwardSearchRequest request)
    {
        var errors = new List<ValidationResult>();
        Validator.TryValidateObject(request, new ValidationContext(request), errors, validateAllProperties: true);
        return errors;
    }
}
