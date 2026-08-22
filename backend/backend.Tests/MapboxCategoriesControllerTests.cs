using Backend.Controllers;
using Backend.Mapbox;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc;
using Microsoft.Extensions.Logging.Abstractions;

namespace Backend.Tests;

public sealed class MapboxCategoriesControllerTests
{
    [Fact]
    public async Task ListCategories_ForwardsLanguageAndPreservesResponse()
    {
        var client = new StubMapboxClient
        {
            Response = new MapboxRawResponse(
                200,
                "{\"listItems\":[{\"canonical_id\":\"restaurant\"}]}",
                "application/json")
        };
        var controller = CreateController(client, "?language=en");

        var result = await controller.ListCategories("en", CancellationToken.None);

        var content = Assert.IsType<ContentResult>(result);
        Assert.Equal(200, content.StatusCode);
        Assert.Contains("restaurant", content.Content);
        Assert.Equal("en", client.Language);
    }

    [Fact]
    public async Task ListCategories_RejectsAccessTokenFromCaller()
    {
        var client = new StubMapboxClient();
        var controller = CreateController(client, "?language=en&access_token=caller-token");

        var result = await controller.ListCategories("en", CancellationToken.None);

        var error = Assert.IsType<BadRequestObjectResult>(result);
        var details = Assert.IsType<ValidationProblemDetails>(error.Value);
        Assert.Equal(StatusCodes.Status400BadRequest, details.Status);
        Assert.Equal(0, client.CallCount);
    }

    [Fact]
    public async Task SearchCategory_ForwardsCategoryRequestAndPreservesGeoJson()
    {
        var client = new StubMapboxClient
        {
            Response = new MapboxRawResponse(
                200,
                "{\"type\":\"FeatureCollection\",\"features\":[]}",
                "application/geo+json")
        };
        var controller = CreateController(client, "?language=en&limit=10");
        var request = new MapboxCategorySearchRequest { Language = "en", Limit = 10 };

        var result = await controller.SearchCategory(
            "restaurant",
            request,
            CancellationToken.None);

        var content = Assert.IsType<ContentResult>(result);
        Assert.Equal(200, content.StatusCode);
        Assert.Equal("application/geo+json", content.ContentType);
        Assert.Equal("restaurant", client.CategoryId);
        Assert.Same(request, client.CategoryRequest);
    }

    [Fact]
    public async Task SearchCategory_RejectsAccessTokenFromCaller()
    {
        var client = new StubMapboxClient();
        var controller = CreateController(client, "?proximity=2,48&access_token=caller-token");

        var result = await controller.SearchCategory(
            "restaurant",
            new MapboxCategorySearchRequest { Proximity = "2,48" },
            CancellationToken.None);

        var error = Assert.IsType<BadRequestObjectResult>(result);
        var details = Assert.IsType<ValidationProblemDetails>(error.Value);
        Assert.Equal(StatusCodes.Status400BadRequest, details.Status);
        Assert.Equal(0, client.CallCount);
    }

    private static MapboxCategoriesController CreateController(
        IMapboxClient client,
        string queryString)
    {
        var controller = new MapboxCategoriesController(
            client,
            NullLogger<MapboxCategoriesController>.Instance)
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
        public string? Language { get; private set; }
        public string? CategoryId { get; private set; }
        public MapboxCategorySearchRequest? CategoryRequest { get; private set; }
        public MapboxRawResponse Response { get; init; } =
            new(200, "{\"listItems\":[]}", "application/json");

        public Task<MapboxRawResponse> ForwardSearchAsync(
            MapboxForwardSearchRequest request,
            CancellationToken cancellationToken) => Task.FromResult(Response);

        public Task<MapboxRawResponse> ListCategoriesAsync(
            string? language,
            CancellationToken cancellationToken)
        {
            CallCount++;
            Language = language;
            return Task.FromResult(Response);
        }

        public Task<MapboxRawResponse> SearchCategoryAsync(
            string categoryId,
            MapboxCategorySearchRequest request,
            CancellationToken cancellationToken)
        {
            CallCount++;
            CategoryId = categoryId;
            CategoryRequest = request;
            return Task.FromResult(Response);
        }

        public Task<MapboxRawResponse> ReverseLookupAsync(
            MapboxReverseLookupRequest request,
            CancellationToken cancellationToken) => Task.FromResult(Response);
    }
}
