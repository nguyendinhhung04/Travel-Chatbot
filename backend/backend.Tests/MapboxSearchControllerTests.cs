using Backend.Controllers;
using Backend.Mapbox;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc;
using Microsoft.Extensions.Logging.Abstractions;

namespace Backend.Tests;

public sealed class MapboxSearchControllerTests
{
    [Fact]
    public async Task Search_RejectsAccessTokenFromCaller()
    {
        var client = new StubMapboxClient();
        var controller = CreateController(client, "?q=Paris&access_token=caller-token");

        var result = await controller.Search(
            new MapboxForwardSearchRequest { Query = "Paris" },
            CancellationToken.None);

        var error = Assert.IsType<BadRequestObjectResult>(result);
        var details = Assert.IsType<ValidationProblemDetails>(error.Value);
        Assert.Equal(StatusCodes.Status400BadRequest, details.Status);
        Assert.Equal(0, client.CallCount);
    }

    [Fact]
    public async Task Search_PreservesMapboxStatusBodyAndContentType()
    {
        var client = new StubMapboxClient
        {
            Response = new MapboxRawResponse(403, "{\"message\":\"Forbidden\"}", "application/json")
        };
        var controller = CreateController(client, "?q=Paris");

        var result = await controller.Search(
            new MapboxForwardSearchRequest { Query = "Paris" },
            CancellationToken.None);

        var content = Assert.IsType<ContentResult>(result);
        Assert.Equal(403, content.StatusCode);
        Assert.Equal("{\"message\":\"Forbidden\"}", content.Content);
        Assert.Equal("application/json", content.ContentType);
    }

    [Fact]
    public async Task Search_ReturnsBadGatewayWhenMapboxCannotBeReached()
    {
        var client = new StubMapboxClient { Exception = new HttpRequestException("offline") };
        var controller = CreateController(client, "?q=Paris");

        var result = await controller.Search(
            new MapboxForwardSearchRequest { Query = "Paris" },
            CancellationToken.None);

        var problem = Assert.IsType<ObjectResult>(result);
        Assert.Equal(StatusCodes.Status502BadGateway, problem.StatusCode);
    }

    [Fact]
    public async Task Search_ReturnsGatewayTimeoutWhenMapboxTimesOut()
    {
        var client = new StubMapboxClient { Exception = new TaskCanceledException("timeout") };
        var controller = CreateController(client, "?q=Paris");

        var result = await controller.Search(
            new MapboxForwardSearchRequest { Query = "Paris" },
            CancellationToken.None);

        var problem = Assert.IsType<ObjectResult>(result);
        Assert.Equal(StatusCodes.Status504GatewayTimeout, problem.StatusCode);
    }

    private static MapboxSearchController CreateController(
        IMapboxClient client,
        string queryString)
    {
        var controller = new MapboxSearchController(
            client,
            NullLogger<MapboxSearchController>.Instance);
        controller.ControllerContext = new ControllerContext
        {
            HttpContext = new DefaultHttpContext()
        };
        controller.Request.QueryString = new QueryString(queryString);
        return controller;
    }

    private sealed class StubMapboxClient : IMapboxClient
    {
        public int CallCount { get; private set; }
        public MapboxRawResponse Response { get; init; } =
            new(200, "{\"type\":\"FeatureCollection\",\"features\":[]}", "application/geo+json");
        public Exception? Exception { get; init; }

        public Task<MapboxRawResponse> ForwardSearchAsync(
            MapboxForwardSearchRequest request,
            CancellationToken cancellationToken)
        {
            CallCount++;
            return Exception is null
                ? Task.FromResult(Response)
                : Task.FromException<MapboxRawResponse>(Exception);
        }

        public Task<MapboxRawResponse> ListCategoriesAsync(
            string? language,
            CancellationToken cancellationToken) => Task.FromResult(Response);

        public Task<MapboxRawResponse> SearchCategoryAsync(
            string categoryId,
            MapboxCategorySearchRequest request,
            CancellationToken cancellationToken) => Task.FromResult(Response);

        public Task<MapboxRawResponse> ReverseLookupAsync(
            MapboxReverseLookupRequest request,
            CancellationToken cancellationToken) => Task.FromResult(Response);
    }
}
