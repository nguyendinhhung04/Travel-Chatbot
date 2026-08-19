using System.Reflection;
using System.Text.Json;
using Backend.Chatbot.Tools;
using Backend.Chatbot.Tools.Mapbox;
using Backend.Controllers;
using Backend.Mapbox;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc;

namespace Backend.Tests;

public sealed class ChatbotToolsControllerTests
{
    [Theory]
    [InlineData(nameof(ChatbotToolsController.ForwardSearch), "mapbox-forward-search")]
    [InlineData(nameof(ChatbotToolsController.ListCategories), "mapbox-list-categories")]
    [InlineData(nameof(ChatbotToolsController.CategorySearch), "mapbox-category-search")]
    [InlineData(nameof(ChatbotToolsController.ReverseLookup), "mapbox-reverse-lookup")]
    public void Actions_ExposeExpectedPostRoutes(string actionName, string route)
    {
        var controllerRoute = typeof(ChatbotToolsController)
            .GetCustomAttribute<RouteAttribute>();
        var actionRoute = typeof(ChatbotToolsController)
            .GetMethod(actionName)
            ?.GetCustomAttribute<HttpPostAttribute>();

        Assert.NotNull(controllerRoute);
        Assert.Equal("api/chatbot/tools", controllerRoute.Template);
        Assert.NotNull(actionRoute);
        Assert.Equal(route, actionRoute.Template);
    }

    [Fact]
    public void ForwardSearchRequest_DeserializesSnakeCaseAndMapsEveryField()
    {
        var httpRequest = Deserialize<MapboxForwardSearchToolHttpRequest>("""
            {
              "q": "coffee",
              "language": "vi",
              "limit": 7,
              "proximity": "108.2,16.1",
              "near": "Da Nang",
              "bbox": "107,15,109,17",
              "radius": 2.5,
              "country": "VN",
              "types": "poi",
              "poi_category": "coffee",
              "poi_category_exclusions": "hotel",
              "show_closed_pois": false,
              "open_now": true,
              "minimum_rating": 4.5,
              "price_levels": "$$",
              "exclude_fields": "reviews",
              "rank_strategy": "distance",
              "sar_type": "isochrone",
              "route": "encoded-route",
              "route_geometry": "polyline6",
              "time_deviation": 3,
              "auto_complete": false,
              "eta_type": "navigation",
              "navigation_profile": "walking",
              "origin": "108.1,16.0"
            }
            """);

        var request = httpRequest.ToMapboxRequest();

        Assert.Equal("coffee", request.Query);
        Assert.Equal("vi", request.Language);
        Assert.Equal(7, request.Limit);
        Assert.Equal("108.2,16.1", request.Proximity);
        Assert.Equal("Da Nang", request.Near);
        Assert.Equal("107,15,109,17", request.BoundingBox);
        Assert.Equal(2.5, request.Radius);
        Assert.Equal("VN", request.Country);
        Assert.Equal("poi", request.Types);
        Assert.Equal("coffee", request.PoiCategory);
        Assert.Equal("hotel", request.PoiCategoryExclusions);
        Assert.False(request.ShowClosedPois);
        Assert.True(request.OpenNow);
        Assert.Equal(4.5, request.MinimumRating);
        Assert.Equal("$$", request.PriceLevels);
        Assert.Equal("reviews", request.ExcludeFields);
        Assert.Equal("distance", request.RankStrategy);
        Assert.Equal("isochrone", request.SarType);
        Assert.Equal("encoded-route", request.Route);
        Assert.Equal("polyline6", request.RouteGeometry);
        Assert.Equal(3, request.TimeDeviation);
        Assert.False(request.AutoComplete);
        Assert.Equal("navigation", request.EtaType);
        Assert.Equal("walking", request.NavigationProfile);
        Assert.Equal("108.1,16.0", request.Origin);
    }

    [Fact]
    public void CategorySearchRequest_DeserializesSnakeCaseAndMapsEveryField()
    {
        var httpRequest = Deserialize<MapboxCategorySearchToolHttpRequest>("""
            {
              "category_id": "restaurant",
              "language": "vi",
              "limit": 12,
              "proximity": "107.6,16.4",
              "near": "Hue",
              "bbox": "107,16,108,17",
              "radius": 1.5,
              "country": "VN",
              "types": "poi",
              "poi_category_exclusions": "fast_food",
              "show_closed_pois": false,
              "exclude_fields": "photos",
              "sar_type": "isochrone",
              "route": "encoded-route",
              "route_geometry": "polyline",
              "time_deviation": 4,
              "eta_type": "navigation",
              "navigation_profile": "cycling",
              "origin": "107.5,16.3"
            }
            """);

        var request = httpRequest.ToMapboxRequest();

        Assert.Equal("restaurant", httpRequest.CategoryId);
        Assert.Equal("vi", request.Language);
        Assert.Equal(12, request.Limit);
        Assert.Equal("107.6,16.4", request.Proximity);
        Assert.Equal("Hue", request.Near);
        Assert.Equal("107,16,108,17", request.BoundingBox);
        Assert.Equal(1.5, request.Radius);
        Assert.Equal("VN", request.Country);
        Assert.Equal("poi", request.Types);
        Assert.Equal("fast_food", request.PoiCategoryExclusions);
        Assert.False(request.ShowClosedPois);
        Assert.Equal("photos", request.ExcludeFields);
        Assert.Equal("isochrone", request.SarType);
        Assert.Equal("encoded-route", request.Route);
        Assert.Equal("polyline", request.RouteGeometry);
        Assert.Equal(4, request.TimeDeviation);
        Assert.Equal("navigation", request.EtaType);
        Assert.Equal("cycling", request.NavigationProfile);
        Assert.Equal("107.5,16.3", request.Origin);
    }

    [Fact]
    public void ReverseAndCategoryListRequests_DeserializeSnakeCase()
    {
        var reverseHttpRequest = Deserialize<MapboxReverseLookupToolHttpRequest>("""
            {
              "longitude": 108.2,
              "latitude": 16.1,
              "language": "vi",
              "limit": 6,
              "country": "VN",
              "types": "address,poi",
              "show_closed_pois": false
            }
            """);
        var listRequest = Deserialize<MapboxListCategoriesToolHttpRequest>("{}");
        var reverseRequest = reverseHttpRequest.ToMapboxRequest();

        Assert.Equal(108.2, reverseRequest.Longitude);
        Assert.Equal(16.1, reverseRequest.Latitude);
        Assert.Equal("vi", reverseRequest.Language);
        Assert.Equal(6, reverseRequest.Limit);
        Assert.Equal("VN", reverseRequest.Country);
        Assert.Equal("address,poi", reverseRequest.Types);
        Assert.False(reverseRequest.ShowClosedPois);
        Assert.Null(listRequest.Language);
    }

    [Fact]
    public async Task ForwardSearch_ForwardsMappedRequestAndReturnsTypedSuccess()
    {
        var client = new StubMapboxClient { Response = PlaceResponse };
        var controller = CreateController(client);
        using var cancellationSource = new CancellationTokenSource();

        var actionResult = await controller.ForwardSearch(
            new MapboxForwardSearchToolHttpRequest
            {
                Query = "coffee",
                Language = "vi",
                Limit = 5,
                PoiCategory = "coffee"
            },
            cancellationSource.Token);

        var result = AssertObjectResult<MapboxPlaceToolData>(
            actionResult,
            StatusCodes.Status200OK,
            success: true);
        Assert.Equal("forward", client.LastCall);
        Assert.Equal("coffee", client.ForwardRequest?.Query);
        Assert.Equal("vi", client.ForwardRequest?.Language);
        Assert.Equal(5, client.ForwardRequest?.Limit);
        Assert.Equal("coffee", client.ForwardRequest?.PoiCategory);
        Assert.Equal(cancellationSource.Token, client.CancellationToken);
        Assert.Empty(Assert.IsType<MapboxPlaceToolData>(result.Data).Results);
    }

    [Fact]
    public async Task ListCategories_AllowsEmptyRequestAndReturnsTypedSuccess()
    {
        var client = new StubMapboxClient { Response = CategoryResponse };
        var controller = CreateController(client);

        var actionResult = await controller.ListCategories(
            new MapboxListCategoriesToolHttpRequest(),
            CancellationToken.None);

        var result = AssertObjectResult<MapboxCategoryToolData>(
            actionResult,
            StatusCodes.Status200OK,
            success: true);
        Assert.Equal("categories", client.LastCall);
        Assert.Null(client.Language);
        Assert.Empty(Assert.IsType<MapboxCategoryToolData>(result.Data).Categories);
    }

    [Fact]
    public async Task CategorySearch_ForwardsCategoryAndMappedFilters()
    {
        var client = new StubMapboxClient { Response = PlaceResponse };
        var controller = CreateController(client);

        var actionResult = await controller.CategorySearch(
            new MapboxCategorySearchToolHttpRequest
            {
                CategoryId = "restaurant",
                Language = "vi",
                Limit = 10,
                Proximity = "108.2,16.1"
            },
            CancellationToken.None);

        AssertObjectResult<MapboxPlaceToolData>(
            actionResult,
            StatusCodes.Status200OK,
            success: true);
        Assert.Equal("category-search", client.LastCall);
        Assert.Equal("restaurant", client.CategoryId);
        Assert.Equal("vi", client.CategoryRequest?.Language);
        Assert.Equal(10, client.CategoryRequest?.Limit);
        Assert.Equal("108.2,16.1", client.CategoryRequest?.Proximity);
    }

    [Fact]
    public async Task ReverseLookup_ForwardsMappedCoordinates()
    {
        var client = new StubMapboxClient { Response = PlaceResponse };
        var controller = CreateController(client);

        var actionResult = await controller.ReverseLookup(
            new MapboxReverseLookupToolHttpRequest
            {
                Longitude = 108.2,
                Latitude = 16.1,
                Types = "address"
            },
            CancellationToken.None);

        AssertObjectResult<MapboxPlaceToolData>(
            actionResult,
            StatusCodes.Status200OK,
            success: true);
        Assert.Equal("reverse", client.LastCall);
        Assert.Equal(108.2, client.ReverseRequest?.Longitude);
        Assert.Equal(16.1, client.ReverseRequest?.Latitude);
        Assert.Equal("address", client.ReverseRequest?.Types);
    }

    [Fact]
    public async Task InvalidInput_ReturnsBadRequestToolResultWithoutCallingMapbox()
    {
        var client = new StubMapboxClient();
        var controller = CreateController(client);

        var actionResult = await controller.ForwardSearch(
            new MapboxForwardSearchToolHttpRequest(),
            CancellationToken.None);

        var result = AssertObjectResult<MapboxPlaceToolData>(
            actionResult,
            StatusCodes.Status400BadRequest,
            success: false);
        Assert.Equal("invalid_input", result.ErrorCode);
        Assert.Null(client.LastCall);
    }

    [Theory]
    [InlineData("http", StatusCodes.Status502BadGateway, "mapbox_http_error")]
    [InlineData("network", StatusCodes.Status502BadGateway, "mapbox_unavailable")]
    [InlineData("invalid-json", StatusCodes.Status502BadGateway, "mapbox_invalid_response")]
    [InlineData("timeout", StatusCodes.Status504GatewayTimeout, "mapbox_timeout")]
    public async Task ToolFailures_ReturnExpectedStatusAndTypedEnvelope(
        string failure,
        int expectedStatus,
        string expectedErrorCode)
    {
        var client = new StubMapboxClient();
        switch (failure)
        {
            case "http":
                client.Response = new MapboxRawResponse(429, "{}", "application/json");
                break;
            case "network":
                client.Exception = new HttpRequestException("offline");
                break;
            case "invalid-json":
                client.Response = new MapboxRawResponse(200, "not-json", "application/json");
                break;
            case "timeout":
                client.Exception = new TaskCanceledException("timeout");
                break;
        }
        var controller = CreateController(client);

        var actionResult = await controller.ForwardSearch(
            new MapboxForwardSearchToolHttpRequest { Query = "coffee" },
            CancellationToken.None);

        var result = AssertObjectResult<MapboxPlaceToolData>(
            actionResult,
            expectedStatus,
            success: false);
        Assert.Equal(expectedErrorCode, result.ErrorCode);
        Assert.Null(result.Data);
    }

    private static T Deserialize<T>(string json) where T : class =>
        JsonSerializer.Deserialize<T>(json)
        ?? throw new InvalidOperationException("Expected JSON to deserialize.");

    private static ToolResult<T> AssertObjectResult<T>(
        IActionResult actionResult,
        int expectedStatus,
        bool success)
        where T : class
    {
        var objectResult = Assert.IsType<ObjectResult>(actionResult);
        Assert.Equal(expectedStatus, objectResult.StatusCode);
        var toolResult = Assert.IsType<ToolResult<T>>(objectResult.Value);
        Assert.Equal(success, toolResult.Success);
        return toolResult;
    }

    private static ChatbotToolsController CreateController(StubMapboxClient client) => new(
        new MapboxForwardSearchTool(client),
        new MapboxListCategoriesTool(client),
        new MapboxCategorySearchTool(client),
        new MapboxReverseLookupTool(client));

    private sealed class StubMapboxClient : IMapboxClient
    {
        public string? LastCall { get; private set; }
        public CancellationToken CancellationToken { get; private set; }
        public MapboxForwardSearchRequest? ForwardRequest { get; private set; }
        public string? Language { get; private set; }
        public string? CategoryId { get; private set; }
        public MapboxCategorySearchRequest? CategoryRequest { get; private set; }
        public MapboxReverseLookupRequest? ReverseRequest { get; private set; }
        public MapboxRawResponse Response { get; set; } = PlaceResponse;
        public Exception? Exception { get; set; }

        public Task<MapboxRawResponse> ForwardSearchAsync(
            MapboxForwardSearchRequest request,
            CancellationToken cancellationToken)
        {
            LastCall = "forward";
            ForwardRequest = request;
            CancellationToken = cancellationToken;
            return Complete();
        }

        public Task<MapboxRawResponse> ListCategoriesAsync(
            string? language,
            CancellationToken cancellationToken)
        {
            LastCall = "categories";
            Language = language;
            CancellationToken = cancellationToken;
            return Complete();
        }

        public Task<MapboxRawResponse> SearchCategoryAsync(
            string categoryId,
            MapboxCategorySearchRequest request,
            CancellationToken cancellationToken)
        {
            LastCall = "category-search";
            CategoryId = categoryId;
            CategoryRequest = request;
            CancellationToken = cancellationToken;
            return Complete();
        }

        public Task<MapboxRawResponse> ReverseLookupAsync(
            MapboxReverseLookupRequest request,
            CancellationToken cancellationToken)
        {
            LastCall = "reverse";
            ReverseRequest = request;
            CancellationToken = cancellationToken;
            return Complete();
        }

        private Task<MapboxRawResponse> Complete() => Exception is null
            ? Task.FromResult(Response)
            : Task.FromException<MapboxRawResponse>(Exception);
    }

    private static readonly MapboxRawResponse PlaceResponse = new(
        200,
        """
        {
          "type": "FeatureCollection",
          "features": [],
          "attribution": "Mapbox"
        }
        """,
        "application/geo+json");

    private static readonly MapboxRawResponse CategoryResponse = new(
        200,
        """
        {
          "listItems": [],
          "attribution": "Mapbox"
        }
        """,
        "application/json");
}
