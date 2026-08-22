using System.ComponentModel.DataAnnotations;
using Backend.Mapbox;

namespace Backend.Tests;

public sealed class MapboxCategorySearchRequestTests
{
    [Fact]
    public void Validate_AcceptsAllSupportedParameters()
    {
        var request = new MapboxCategorySearchRequest
        {
            Language = "en",
            Limit = 25,
            Proximity = "2.2945,48.8584",
            Near = "Paris",
            BoundingBox = "2.0,48.0,3.0,49.0",
            Radius = 1,
            Country = "FR,US",
            Types = "poi,category",
            PoiCategoryExclusions = "hotel",
            ShowClosedPois = true,
            ExcludeFields = "photos,reviews",
            SarType = "isochrone",
            Route = "encoded-route",
            RouteGeometry = "polyline6",
            TimeDeviation = 5,
            EtaType = "navigation",
            NavigationProfile = "walking",
            Origin = "2.3,48.8"
        };

        var errors = Validate(request);

        Assert.Empty(errors);
        Assert.Equal(18, request.ToQueryParameters().Count);
    }

    [Fact]
    public void Validate_RejectsLimitAboveTwentyFive()
    {
        var errors = Validate(new MapboxCategorySearchRequest { Limit = 26 });

        Assert.Contains(errors, error => error.MemberNames.Contains(nameof(MapboxCategorySearchRequest.Limit)));
    }

    [Fact]
    public void Validate_RequiresCoordinateProximityForRadius()
    {
        var errors = Validate(new MapboxCategorySearchRequest { Proximity = "ip", Radius = 1 });

        Assert.Contains(errors, error => error.MemberNames.Contains(nameof(MapboxCategorySearchRequest.Radius)));
    }

    [Fact]
    public void Validate_RequiresRouteForSearchAlongRoute()
    {
        var errors = Validate(new MapboxCategorySearchRequest { SarType = "isochrone" });

        Assert.Contains(errors, error => error.MemberNames.Contains(nameof(MapboxCategorySearchRequest.Route)));
    }

    private static IReadOnlyList<ValidationResult> Validate(MapboxCategorySearchRequest request)
    {
        var errors = new List<ValidationResult>();
        Validator.TryValidateObject(request, new ValidationContext(request), errors, validateAllProperties: true);
        return errors;
    }
}
