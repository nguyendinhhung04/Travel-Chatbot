using Backend.Chatbot.Tools.Mapbox;
using Backend.Mapbox;
using System.Text.Json;

namespace Backend.Tests;

public sealed class MapboxOptimizationToolTests
{
    [Fact]
    public async Task ExecuteAsync_ValidatesCallsMapboxAndReturnsOrderedRoute()
    {
        var client = new StubOptimizationClient
        {
            Response = JsonResponse(ValidOptimizationResponse)
        };
        var stops = ValidStops();

        var result = await new MapboxOptimizationTool(client).ExecuteAsync(
            new MapboxOptimizationRequest(" Driving ", stops),
            CancellationToken.None);

        Assert.True(result.Success);
        Assert.Equal("driving", client.Profile);
        Assert.Equal(
            stops.Select(stop => (stop.Longitude, stop.Latitude)),
            client.Coordinates);
        var data = Assert.IsType<MapboxOptimizedRouteData>(result.Data);
        Assert.Equal("driving", data.Profile);
        Assert.Equal(12000.5, data.DistanceMeters);
        Assert.Equal(3600.25, data.DurationSeconds);
        Assert.Equal("LineString", data.Geometry.Type);
        Assert.Equal(3, data.Geometry.Coordinates.Count);
        Assert.Collection(
            data.OrderedStops,
            stop =>
            {
                Assert.Equal(1, stop.Order);
                Assert.Equal(1, stop.InputIndex);
                Assert.Equal("mapbox.poi.2", stop.MapboxId);
            },
            stop =>
            {
                Assert.Equal(2, stop.Order);
                Assert.Equal(2, stop.InputIndex);
                Assert.Equal("mapbox.poi.3", stop.MapboxId);
            },
            stop =>
            {
                Assert.Equal(3, stop.Order);
                Assert.Equal(0, stop.InputIndex);
                Assert.Equal("mapbox.poi.1", stop.MapboxId);
            });
        var serialized = JsonSerializer.Serialize(data);
        Assert.Contains("\"orderedStops\"", serialized);
        Assert.Contains("\"order\":1", serialized);
        Assert.Contains("\"inputIndex\":1", serialized);
        Assert.Contains("\"geometry\":{\"type\":\"LineString\"", serialized);
        Assert.DoesNotContain("access_token", serialized);
    }

    [Fact]
    public async Task ExecuteAsync_RejectsInvalidRequestsWithoutCallingMapbox()
    {
        var validStops = ValidStops();
        var invalidRequests = new MapboxOptimizationRequest[]
        {
            new("driving-traffic", validStops),
            new("driving", validStops.Take(1).ToArray()),
            new("driving", Enumerable.Range(1, 13)
                .Select(index => new MapboxOptimizationStop(
                    $"mapbox.poi.{index}",
                    $"Place {index}",
                    105 + index / 100d,
                    21 + index / 100d))
                .ToArray()),
            new("driving", [validStops[0], validStops[0]]),
            new("driving", [
                validStops[0],
                new MapboxOptimizationStop(" ", "Place", 105.8, 21.0)
            ]),
            new("driving", [
                validStops[0],
                new MapboxOptimizationStop("mapbox.poi.bad", "Place", 181, 21.0)
            ]),
            new("driving", [
                validStops[0],
                new MapboxOptimizationStop("mapbox.poi.nan", "Place", double.NaN, 21.0)
            ])
        };

        foreach (var request in invalidRequests)
        {
            var client = new StubOptimizationClient();
            var result = await new MapboxOptimizationTool(client).ExecuteAsync(request);

            Assert.False(result.Success);
            Assert.Equal("invalid_input", result.ErrorCode);
            Assert.Equal(0, client.CallCount);
        }
    }

    [Theory]
    [InlineData("NoRoute", "mapbox_no_route")]
    [InlineData("NoTrips", "mapbox_no_trips")]
    [InlineData("NoSegment", "mapbox_no_segment")]
    [InlineData("NotImplemented", "mapbox_not_implemented")]
    [InlineData("UnknownProviderCode", "mapbox_invalid_response")]
    public async Task ExecuteAsync_MapsProviderCodes(string code, string expectedErrorCode)
    {
        var client = new StubOptimizationClient
        {
            Response = JsonResponse($$"""{"code":"{{code}}"}""")
        };

        var result = await new MapboxOptimizationTool(client).ExecuteAsync(
            new MapboxOptimizationRequest("driving", ValidStops()));

        Assert.False(result.Success);
        Assert.Equal(expectedErrorCode, result.ErrorCode);
        Assert.Null(result.Data);
    }

    [Theory]
    [InlineData("not-json")]
    [InlineData("{\"code\":\"Ok\",\"waypoints\":[],\"trips\":[]}")]
    [InlineData("""
        {
          "code":"Ok",
          "waypoints":[{"waypoint_index":0},{"waypoint_index":0},{"waypoint_index":2}],
          "trips":[{"geometry":{"type":"LineString","coordinates":[[105,21],[106,22]]},"distance":1,"duration":1}]
        }
        """)]
    [InlineData("""
        {
          "code":"Ok",
          "waypoints":[{"waypoint_index":0},{"waypoint_index":1},{"waypoint_index":2}],
          "trips":[{"geometry":{"type":"Point","coordinates":[105,21]},"distance":1,"duration":1}]
        }
        """)]
    [InlineData("""
        {
          "code":"Ok",
          "waypoints":[{"waypoint_index":0},{"waypoint_index":1},{"waypoint_index":2}],
          "trips":[{"geometry":{"type":"LineString","coordinates":[[105,21],[106,22]]},"distance":-1,"duration":1}]
        }
        """)]
    public async Task ExecuteAsync_RejectsMalformedProviderData(string body)
    {
        var client = new StubOptimizationClient { Response = JsonResponse(body) };

        var result = await new MapboxOptimizationTool(client).ExecuteAsync(
            new MapboxOptimizationRequest("driving", ValidStops()));

        Assert.False(result.Success);
        Assert.Equal("mapbox_invalid_response", result.ErrorCode);
        Assert.Null(result.Data);
    }

    [Theory]
    [InlineData("http", "mapbox_http_error")]
    [InlineData("network", "mapbox_unavailable")]
    [InlineData("timeout", "mapbox_timeout")]
    public async Task ExecuteAsync_MapsHttpAndTransportFailures(
        string failure,
        string expectedErrorCode)
    {
        var client = new StubOptimizationClient();
        switch (failure)
        {
            case "http":
                client.Response = new MapboxRawResponse(401, "secret", "text/plain");
                break;
            case "network":
                client.Exception = new HttpRequestException("provider details");
                break;
            case "timeout":
                client.Exception = new TaskCanceledException("provider details");
                break;
        }

        var result = await new MapboxOptimizationTool(client).ExecuteAsync(
            new MapboxOptimizationRequest("driving", ValidStops()));

        Assert.False(result.Success);
        Assert.Equal(expectedErrorCode, result.ErrorCode);
        Assert.DoesNotContain("secret", result.ErrorMessage);
        Assert.DoesNotContain("provider details", result.ErrorMessage);
    }

    private static MapboxOptimizationStop[] ValidStops() =>
    [
        new("mapbox.poi.1", "Place 1", 105.81, 21.01),
        new("mapbox.poi.2", "Place 2", 105.82, 21.02),
        new("mapbox.poi.3", "Place 3", 105.83, 21.03)
    ];

    private static MapboxRawResponse JsonResponse(string body) =>
        new(200, body, "application/json");

    private sealed class StubOptimizationClient : IMapboxOptimizationClient
    {
        public int CallCount { get; private set; }
        public string? Profile { get; private set; }
        public IReadOnlyList<(double Longitude, double Latitude)>? Coordinates { get; private set; }
        public MapboxRawResponse Response { get; set; } = JsonResponse(ValidOptimizationResponse);
        public Exception? Exception { get; set; }

        public Task<MapboxRawResponse> OptimizeAsync(
            string profile,
            IReadOnlyList<(double Longitude, double Latitude)> coordinates,
            CancellationToken cancellationToken)
        {
            CallCount++;
            Profile = profile;
            Coordinates = coordinates;
            return Exception is null
                ? Task.FromResult(Response)
                : Task.FromException<MapboxRawResponse>(Exception);
        }
    }

    private const string ValidOptimizationResponse = """
        {
          "code": "Ok",
          "waypoints": [
            {"waypoint_index": 2, "trips_index": 0},
            {"waypoint_index": 0, "trips_index": 0},
            {"waypoint_index": 1, "trips_index": 0}
          ],
          "trips": [{
            "geometry": {
              "type": "LineString",
              "coordinates": [[105.82,21.02],[105.83,21.03],[105.81,21.01]]
            },
            "distance": 12000.5,
            "duration": 3600.25
          }]
        }
        """;
}
