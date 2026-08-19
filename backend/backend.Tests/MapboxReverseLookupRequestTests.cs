using System.ComponentModel.DataAnnotations;
using Backend.Mapbox;

namespace Backend.Tests;

public sealed class MapboxReverseLookupRequestTests
{
    [Fact]
    public void Validate_AcceptsAllSupportedParameters()
    {
        var request = new MapboxReverseLookupRequest
        {
            Longitude = -118.471383,
            Latitude = 34.023653,
            Language = "en",
            Limit = 10,
            Country = "US,CA",
            Types = "country,region,prefecture,postcode,district,place,city,locality,oaza,block,street,address,poi,category",
            ShowClosedPois = true
        };

        var errors = Validate(request);

        Assert.Empty(errors);
        Assert.Equal(7, request.ToQueryParameters().Count);
    }

    [Theory]
    [InlineData(-181, 0, "Longitude")]
    [InlineData(181, 0, "Longitude")]
    [InlineData(0, -91, "Latitude")]
    [InlineData(0, 91, "Latitude")]
    public void Validate_RejectsCoordinatesOutsideMapboxRange(
        double longitude,
        double latitude,
        string invalidMember)
    {
        var errors = Validate(new MapboxReverseLookupRequest
        {
            Longitude = longitude,
            Latitude = latitude
        });

        Assert.Contains(errors, error => error.MemberNames.Contains(invalidMember));
    }

    [Fact]
    public void Validate_RequiresBothCoordinates()
    {
        var errors = Validate(new MapboxReverseLookupRequest());

        Assert.Contains(errors, error => error.MemberNames.Contains(nameof(MapboxReverseLookupRequest.Longitude)));
        Assert.Contains(errors, error => error.MemberNames.Contains(nameof(MapboxReverseLookupRequest.Latitude)));
    }

    [Fact]
    public void Validate_RejectsUnsupportedReverseType()
    {
        var errors = Validate(new MapboxReverseLookupRequest
        {
            Longitude = 2,
            Latitude = 48,
            Types = "neighborhood"
        });

        Assert.Contains(errors, error => error.MemberNames.Contains(nameof(MapboxReverseLookupRequest.Types)));
    }

    private static IReadOnlyList<ValidationResult> Validate(MapboxReverseLookupRequest request)
    {
        var errors = new List<ValidationResult>();
        Validator.TryValidateObject(request, new ValidationContext(request), errors, validateAllProperties: true);
        return errors;
    }
}
