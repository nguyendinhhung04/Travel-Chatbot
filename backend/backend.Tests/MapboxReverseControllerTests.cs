using Backend.Controllers;
using Backend.Mapbox;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc;
using Microsoft.Extensions.Logging.Abstractions;

namespace Backend.Tests;

public sealed class MapboxReverseControllerTests
{
    [Fact]
    public async Task ReverseLookup_ForwardsRequestAndPreservesGeoJson()
    {
        var client = new StubMapboxClient
        {
            Response = new MapboxRawResponse(
                200,
                "{\"type\":\"FeatureCollection\",\"features\":[]}",
                "application/geo+json")
        };
        var controller = CreateController(client, "?longitude=2&latitude=48");
        var request = new MapboxReverseLookupRequest { Longitude = 2, Latitude = 48 };

        var result = await controller.ReverseLookup(request, CancellationToken.None);

        var content = Assert.IsType<ContentResult>(result);
        Assert.Equal(200, content.StatusCode);
        Assert.Equal("application/geo+json", content.ContentType);
        Assert.Same(request, client.ReverseRequest);
    }

    [Fact]
    public async Task ReverseLookup_RejectsAccessTokenFromCaller()
    {
        var client = new StubMapboxClient();
        var controller = CreateController(
            client,
            "?longitude=2&latitude=48&access_token=caller-token");

        var result = await controller.ReverseLookup(
            new MapboxReverseLookupRequest { Longitude = 2, Latitude = 48 },
            CancellationToken.None);

        var error = Assert.IsType<BadRequestObjectResult>(result);
        var details = Assert.IsType<ValidationProblemDetails>(error.Value);
        Assert.Equal(StatusCodes.Status400BadRequest, details.Status);
        Assert.Equal(0, client.CallCount);
    }

    private static MapboxReverseController CreateController(
        IMapboxClient client,
        string queryString)
    {
        var controller = new MapboxReverseController(
            client,
            NullLogger<MapboxReverseController>.Instance)
        {
            ControllerContext = new ControllerContext
            {
                HttpContext = new DefaultHttpContext()
            }
        };
        controller.Request.QueryString = new QueryString(queryString);
        return controller;
    }

    private sealed class StubMapboxClient : IMapboxClient
    {
        public int CallCount { get; private set; }
        public MapboxReverseLookupRequest? ReverseRequest { get; private set; }
        public MapboxRawResponse Response { get; init; } =
            new(200, "{\"type\":\"FeatureCollection\",\"features\":[]}", "application/geo+json");

        public Task<MapboxRawResponse> ForwardSearchAsync(
            MapboxForwardSearchRequest request,
            CancellationToken cancellationToken) => Task.FromResult(Response);

        public Task<MapboxRawResponse> ListCategoriesAsync(
            string? language,
            CancellationToken cancellationToken) => Task.FromResult(Response);

        public Task<MapboxRawResponse> SearchCategoryAsync(
            string categoryId,
            MapboxCategorySearchRequest request,
            CancellationToken cancellationToken) => Task.FromResult(Response);

        public Task<MapboxRawResponse> ReverseLookupAsync(
            MapboxReverseLookupRequest request,
            CancellationToken cancellationToken)
        {
            CallCount++;
            ReverseRequest = request;
            return Task.FromResult(Response);
        }
    }
}
