using System.Text.Json;
using Backend.Chatbot.Tools.Mapbox;
using Backend.Mapbox;

namespace Backend.Tests;

public sealed class MapboxToolsTests
{
    private const string Attribution = "© Mapbox";

    [Fact]
    public async Task ForwardSearchTool_ForwardsRequestAndMapsChatbotFields()
    {
        var client = new StubMapboxClient
        {
            Response = JsonResponse(FullPlaceResponse)
        };
        var request = new MapboxForwardSearchRequest
        {
            Query = "coffee",
            Language = "en",
            Limit = 5,
            Proximity = "105.85,21.03",
            Types = "poi",
            PoiCategory = "coffee",
            EtaType = "navigation",
            NavigationProfile = "walking",
            Origin = "105.84,21.02"
        };

        var result = await new MapboxForwardSearchTool(client)
            .ExecuteAsync(request, CancellationToken.None);

        Assert.True(result.Success);
        Assert.Null(result.ErrorCode);
        Assert.Same(request, client.ForwardRequest);
        var data = Assert.IsType<MapboxPlaceToolData>(result.Data);
        Assert.Equal(Attribution, data.Attribution);
        var place = Assert.Single(data.Results);
        Assert.Equal("mapbox.poi.1", place.MapboxId);
        Assert.Equal("Preferred Coffee", place.Name);
        Assert.Equal("poi", place.FeatureType);
        Assert.Equal("1 Example Street, Example City", place.FullAddress);
        Assert.Equal(105.851, place.Longitude);
        Assert.Equal(21.031, place.Latitude);
        Assert.Equal(["Coffee Shop", "Cafe"], place.PoiCategories);
        Assert.Equal(["coffee", "cafe"], place.PoiCategoryIds);
        Assert.Equal("active", place.OperationalStatus);
        Assert.Equal(125.5, place.DistanceMeters);
        Assert.Equal(3.2, place.EtaMinutes);
        Assert.Equal(4.7, place.Rating);
        Assert.Equal(0.91, place.Popularity);
        var serialized = JsonSerializer.Serialize(data);
        Assert.DoesNotContain("rawResponse", serialized);
        Assert.DoesNotContain("ignored", serialized);
    }

    [Fact]
    public async Task ForwardSearchTool_AllowsMissingOptionalFieldsAndEmptyResults()
    {
        var client = new StubMapboxClient
        {
            Response = JsonResponse(MinimalPlaceResponse)
        };

        var result = await new MapboxForwardSearchTool(client).ExecuteAsync(
            new MapboxForwardSearchRequest { Query = "Example" });

        Assert.True(result.Success);
        var place = Assert.Single(Assert.IsType<MapboxPlaceToolData>(result.Data).Results);
        Assert.Equal("Example", place.Name);
        Assert.Equal("Example City", place.FullAddress);
        Assert.Equal(105.8, place.Longitude);
        Assert.Equal(21.0, place.Latitude);
        Assert.Empty(place.PoiCategories);
        Assert.Empty(place.PoiCategoryIds);
        Assert.Null(place.DistanceMeters);

        client.Response = JsonResponse($$"""
            {"type":"FeatureCollection","features":[],"attribution":"{{Attribution}}"}
            """);

        var emptyResult = await new MapboxForwardSearchTool(client).ExecuteAsync(
            new MapboxForwardSearchRequest { Query = "No result" });

        Assert.True(emptyResult.Success);
        Assert.Empty(Assert.IsType<MapboxPlaceToolData>(emptyResult.Data).Results);
    }

    [Fact]
    public async Task CategorySearchTool_ForwardsCategoryAndCompleteRequest()
    {
        var client = new StubMapboxClient { Response = JsonResponse(MinimalPlaceResponse) };
        var request = new MapboxCategorySearchRequest
        {
            Language = "en",
            Limit = 25,
            Proximity = "105.85,21.03",
            Country = "VN",
            ShowClosedPois = false,
            EtaType = "navigation",
            NavigationProfile = "walking",
            Origin = "105.84,21.02"
        };

        var result = await new MapboxCategorySearchTool(client)
            .ExecuteAsync("restaurant", request, CancellationToken.None);

        Assert.True(result.Success);
        Assert.Equal("restaurant", client.CategoryId);
        Assert.Same(request, client.CategoryRequest);
    }

    [Fact]
    public async Task CategorySearchTool_FiltersRatingSortsPopularityAndReturnsTopFive()
    {
        var client = new StubMapboxClient
        {
            Response = JsonResponse(CategoryRankingResponse)
        };

        var result = await new MapboxCategorySearchTool(client).ExecuteAsync(
            "restaurant",
            new MapboxCategorySearchRequest { Limit = 10, Types = "poi" },
            CancellationToken.None,
            minimumRating: 4.0);

        Assert.True(result.Success);
        var data = Assert.IsType<MapboxPlaceToolData>(result.Data);
        Assert.Equal(
            ["poi-c", "poi-e", "poi-f", "poi-a", "poi-g"],
            data.Results.Select(place => place.MapboxId));
        Assert.Null(data.Results[0].Rating);
        Assert.Equal(0.9, data.Results[0].Popularity);
    }

    [Fact]
    public async Task CategorySearchTool_RejectsInvalidInternalRatingWithoutCallingMapbox()
    {
        var client = new StubMapboxClient();

        var result = await new MapboxCategorySearchTool(client).ExecuteAsync(
            "restaurant",
            new MapboxCategorySearchRequest(),
            CancellationToken.None,
            minimumRating: 5.1);

        Assert.False(result.Success);
        Assert.Equal("invalid_input", result.ErrorCode);
        Assert.Equal(0, client.CallCount);
    }

    [Fact]
    public async Task ReverseLookupTool_ForwardsCompleteRequest()
    {
        var client = new StubMapboxClient { Response = JsonResponse(MinimalPlaceResponse) };
        var request = new MapboxReverseLookupRequest
        {
            Longitude = 105.85,
            Latitude = 21.03,
            Language = "en",
            Limit = 5,
            Country = "VN",
            Types = "address"
        };

        var result = await new MapboxReverseLookupTool(client)
            .ExecuteAsync(request, CancellationToken.None);

        Assert.True(result.Success);
        Assert.Same(request, client.ReverseRequest);
    }

    [Fact]
    public async Task Tools_ReturnInvalidInputWithoutCallingMapbox()
    {
        var client = new StubMapboxClient();

        var forward = await new MapboxForwardSearchTool(client).ExecuteAsync(
            new MapboxForwardSearchRequest { Query = " " });
        var category = await new MapboxCategorySearchTool(client).ExecuteAsync(
            " ",
            new MapboxCategorySearchRequest());
        var reverse = await new MapboxReverseLookupTool(client).ExecuteAsync(
            new MapboxReverseLookupRequest());

        Assert.False(forward.Success);
        Assert.Equal("invalid_input", forward.ErrorCode);
        Assert.False(category.Success);
        Assert.Equal("invalid_input", category.ErrorCode);
        Assert.False(reverse.Success);
        Assert.Equal("invalid_input", reverse.ErrorCode);
        Assert.Equal(0, client.CallCount);
    }

    [Fact]
    public async Task Tool_ReturnsSafeErrorForMapboxHttpFailure()
    {
        var client = new StubMapboxClient
        {
            Response = new MapboxRawResponse(
                401,
                "{\"message\":\"token=secret-provider-message\"}",
                "application/json")
        };

        var result = await new MapboxForwardSearchTool(client).ExecuteAsync(
            new MapboxForwardSearchRequest { Query = "Example" });

        Assert.False(result.Success);
        Assert.Equal("mapbox_http_error", result.ErrorCode);
        Assert.Contains("401", result.ErrorMessage);
        Assert.DoesNotContain("secret", result.ErrorMessage);
        Assert.Null(result.Data);
    }

    [Theory]
    [InlineData("timeout", "mapbox_timeout")]
    [InlineData("network", "mapbox_unavailable")]
    public async Task Tool_MapsTransportFailures(string failure, string expectedCode)
    {
        var client = new StubMapboxClient
        {
            Exception = failure == "timeout"
                ? new TaskCanceledException("provider details")
                : new HttpRequestException("provider details")
        };

        var result = await new MapboxForwardSearchTool(client).ExecuteAsync(
            new MapboxForwardSearchRequest { Query = "Example" });

        Assert.False(result.Success);
        Assert.Equal(expectedCode, result.ErrorCode);
        Assert.DoesNotContain("provider details", result.ErrorMessage);
    }

    [Theory]
    [InlineData("not-json")]
    [InlineData("{\"type\":\"FeatureCollection\"}")]
    [InlineData("{\"type\":\"FeatureCollection\",\"features\":[{}],\"attribution\":\"Mapbox\"}")]
    public async Task Tool_ReturnsInvalidResponseForMalformedMapboxData(string body)
    {
        var client = new StubMapboxClient { Response = JsonResponse(body) };

        var result = await new MapboxForwardSearchTool(client).ExecuteAsync(
            new MapboxForwardSearchRequest { Query = "Example" });

        Assert.False(result.Success);
        Assert.Equal("mapbox_invalid_response", result.ErrorCode);
        Assert.Null(result.Data);
    }

    private static MapboxRawResponse JsonResponse(string body) =>
        new(200, body, "application/json");

    private const string FullPlaceResponse = $$"""
        {
          "type": "FeatureCollection",
          "features": [
            {
              "geometry": { "type": "Point", "coordinates": [105.85, 21.03] },
              "properties": {
                "name": "Coffee",
                "name_preferred": "Preferred Coffee",
                "mapbox_id": "mapbox.poi.1",
                "feature_type": "poi",
                "address": "1 Example Street",
                "full_address": "1 Example Street, Example City",
                "place_formatted": "Example City",
                "coordinates": { "longitude": 105.851, "latitude": 21.031 },
                "poi_category": ["Coffee Shop", "Cafe"],
                "poi_category_ids": ["coffee", "cafe"],
                "operational_status": "active",
                "distance": 125.5,
                "eta": 3.2,
                "metadata": { "ignored": true, "rating": 4.7, "popularity": 0.91 }
              }
            }
          ],
          "attribution": "{{Attribution}}",
          "response_id": "ignored"
        }
        """;

    private const string CategoryRankingResponse = $$"""
        {
          "type": "FeatureCollection",
          "features": [
            { "geometry": { "coordinates": [105.80, 21.00] }, "properties": { "name": "A", "mapbox_id": "poi-a", "feature_type": "poi", "metadata": { "rating": 4.5, "popularity": 0.6 } } },
            { "geometry": { "coordinates": [105.81, 21.01] }, "properties": { "name": "B", "mapbox_id": "poi-b", "feature_type": "poi", "metadata": { "rating": 3.9, "popularity": 1.0 } } },
            { "geometry": { "coordinates": [105.82, 21.02] }, "properties": { "name": "C", "mapbox_id": "poi-c", "feature_type": "poi", "metadata": { "popularity": 0.9 } } },
            { "geometry": { "coordinates": [105.83, 21.03] }, "properties": { "name": "D", "mapbox_id": "poi-d", "feature_type": "poi", "metadata": { "rating": 4.2 } } },
            { "geometry": { "coordinates": [105.84, 21.04] }, "properties": { "name": "E", "mapbox_id": "poi-e", "feature_type": "poi", "metadata": { "rating": 4.0, "popularity": 0.8 } } },
            { "geometry": { "coordinates": [105.85, 21.05] }, "properties": { "name": "F", "mapbox_id": "poi-f", "feature_type": "poi", "metadata": { "rating": 5.0, "popularity": 0.7 } } },
            { "geometry": { "coordinates": [105.86, 21.06] }, "properties": { "name": "G", "mapbox_id": "poi-g", "feature_type": "poi", "metadata": { "rating": 4.7, "popularity": 0.5 } } },
            { "geometry": { "coordinates": [105.87, 21.07] }, "properties": { "name": "H", "mapbox_id": "poi-h", "feature_type": "poi", "metadata": { "rating": 4.9, "popularity": 0.4 } } }
          ],
          "attribution": "{{Attribution}}"
        }
        """;

    private const string MinimalPlaceResponse = $$"""
        {
          "type": "FeatureCollection",
          "features": [
            {
              "geometry": { "type": "Point", "coordinates": [105.8, 21.0] },
              "properties": {
                "name": "Example",
                "mapbox_id": "mapbox.place.1",
                "feature_type": "place",
                "place_formatted": "Example City"
              }
            }
          ],
          "attribution": "{{Attribution}}"
        }
        """;

    private sealed class StubMapboxClient : IMapboxClient
    {
        public int CallCount { get; private set; }
        public MapboxForwardSearchRequest? ForwardRequest { get; private set; }
        public string? Language { get; private set; }
        public string? CategoryId { get; private set; }
        public MapboxCategorySearchRequest? CategoryRequest { get; private set; }
        public MapboxReverseLookupRequest? ReverseRequest { get; private set; }
        public MapboxRawResponse Response { get; set; } = JsonResponse(MinimalPlaceResponse);
        public Exception? Exception { get; init; }

        public Task<MapboxRawResponse> ForwardSearchAsync(
            MapboxForwardSearchRequest request,
            CancellationToken cancellationToken)
        {
            ForwardRequest = request;
            return Complete();
        }

        public Task<MapboxRawResponse> ListCategoriesAsync(
            string? language,
            CancellationToken cancellationToken)
        {
            Language = language;
            return Complete();
        }

        public Task<MapboxRawResponse> SearchCategoryAsync(
            string categoryId,
            MapboxCategorySearchRequest request,
            CancellationToken cancellationToken)
        {
            CategoryId = categoryId;
            CategoryRequest = request;
            return Complete();
        }

        public Task<MapboxRawResponse> ReverseLookupAsync(
            MapboxReverseLookupRequest request,
            CancellationToken cancellationToken)
        {
            ReverseRequest = request;
            return Complete();
        }

        private Task<MapboxRawResponse> Complete()
        {
            CallCount++;
            return Exception is null
                ? Task.FromResult(Response)
                : Task.FromException<MapboxRawResponse>(Exception);
        }
    }
}
