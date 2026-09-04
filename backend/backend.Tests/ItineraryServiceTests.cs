using Backend.Chatbot.Tools.Mapbox;
using Backend.Itineraries;
using Backend.Mapbox;
using MongoDB.Bson;

namespace Backend.Tests;

public sealed class ItineraryServiceTests
{
    private const string UserId = "507f1f77bcf86cd799439014";
    [Fact]
    public async Task Create_OptimizesBeforeInsertAndStartsAtVersionOne()
    {
        var repository = new StubRepository(Current());
        var optimizationClient = new StubOptimizationClient(ValidOptimizationResponse);
        var service = new ItineraryService(
            repository,
            new MapboxOptimizationTool(optimizationClient));

        var result = await service.CreateAsync(
            UserId,
            new CreateItineraryRequest(
                "HĂ  Ná»™i 3 ngĂ y 2 Ä‘Ăªm",
                "HĂ  Ná»™i",
                3,
                2,
                "driving",
                [
                    new("poi-a", "Äiá»ƒm A", 105.8, 21.0),
                    new("poi-b", "Äiá»ƒm B", 105.9, 21.1),
                    new("poi-c", "Äiá»ƒm C", 105.88, 20.96)
                ]),
            CancellationToken.None);

        Assert.True(result.Success);
        Assert.Equal(201, result.StatusCode);
        Assert.True(ObjectId.TryParse(result.Data!.Id, out _));
        Assert.Equal(1, result.Data.Version);
        Assert.Equal(3, result.Data.Stops.Count);
        Assert.Equal(1, optimizationClient.CallCount);
        Assert.Equal(1, repository.InsertCount);
    }

    [Fact]
    public async Task Create_DoesNotInsertWhenOptimizationFails()
    {
        var repository = new StubRepository(Current());
        var optimizationClient = new StubOptimizationClient("""{"code":"NoRoute"}""");
        var service = new ItineraryService(
            repository,
            new MapboxOptimizationTool(optimizationClient));

        var result = await service.CreateAsync(
            UserId,
            new CreateItineraryRequest(
                "HĂ  Ná»™i",
                "HĂ  Ná»™i",
                2,
                1,
                "driving",
                [
                    new("poi-a", "Äiá»ƒm A", 105.8, 21.0),
                    new("poi-b", "Äiá»ƒm B", 105.9, 21.1),
                    new("poi-c", "Äiá»ƒm C", 105.88, 20.96)
                ]),
            CancellationToken.None);

        Assert.False(result.Success);
        Assert.Equal("mapbox_no_route", result.ErrorCode);
        Assert.Equal(0, repository.InsertCount);
    }

    [Fact]
    public async Task Create_RejectsDuplicateStopsBeforeOptimization()
    {
        var repository = new StubRepository(Current());
        var optimizationClient = new StubOptimizationClient(ValidOptimizationResponse);
        var service = new ItineraryService(
            repository,
            new MapboxOptimizationTool(optimizationClient));

        var result = await service.CreateAsync(
            UserId,
            new CreateItineraryRequest(
                "HĂ  Ná»™i",
                "HĂ  Ná»™i",
                2,
                1,
                "driving",
                [
                    new("poi-a", "Äiá»ƒm A", 105.8, 21.0),
                    new("poi-a", "Äiá»ƒm A", 105.8, 21.0)
                ]),
            CancellationToken.None);

        Assert.False(result.Success);
        Assert.Equal("invalid_input", result.ErrorCode);
        Assert.Equal(0, optimizationClient.CallCount);
        Assert.Equal(0, repository.InsertCount);
    }

    [Fact]
    public async Task AddStop_OptimizesBeforeVersionedReplace()
    {
        var repository = new StubRepository(Current());
        var optimizationClient = new StubOptimizationClient(ValidOptimizationResponse);
        var service = new ItineraryService(
            repository,
            new MapboxOptimizationTool(optimizationClient));

        var result = await service.AddStopAsync(
            UserId,
            ItineraryId,
            new AddItineraryStopRequest(
                new MapboxOptimizationStop("poi-yen-so", "Công viên Yên Sở", 105.88, 20.96),
                3),
            CancellationToken.None);

        Assert.True(result.Success);
        Assert.Equal(4, result.Data!.Version);
        Assert.Equal(3, result.Data.Stops.Count);
        Assert.Equal(1, optimizationClient.CallCount);
        Assert.Equal(3, repository.ExpectedVersion);
        Assert.Equal(1, repository.ReplaceCount);
    }

    [Fact]
    public async Task AddStop_DoesNotOptimizeOrWriteForDuplicateOrStaleVersion()
    {
        foreach (var request in new[]
        {
            new AddItineraryStopRequest(
                new MapboxOptimizationStop("poi-a", "Điểm A", 105.8, 21.0), 3),
            new AddItineraryStopRequest(
                new MapboxOptimizationStop("poi-new", "Điểm mới", 105.7, 21.2), 2)
        })
        {
            var repository = new StubRepository(Current());
            var optimizationClient = new StubOptimizationClient(ValidOptimizationResponse);
            var service = new ItineraryService(
                repository,
                new MapboxOptimizationTool(optimizationClient));

            var result = await service.AddStopAsync(
                UserId,
                ItineraryId,
                request,
                CancellationToken.None);

            Assert.False(result.Success);
            Assert.Equal(409, result.StatusCode);
            Assert.Equal(0, optimizationClient.CallCount);
            Assert.Equal(0, repository.ReplaceCount);
        }
    }

    [Fact]
    public async Task AddStop_DoesNotWriteWhenOptimizationFails()
    {
        var repository = new StubRepository(Current());
        var optimizationClient = new StubOptimizationClient("""{"code":"NoRoute"}""");
        var service = new ItineraryService(
            repository,
            new MapboxOptimizationTool(optimizationClient));

        var result = await service.AddStopAsync(
            UserId,
            ItineraryId,
            new AddItineraryStopRequest(
                new MapboxOptimizationStop("poi-new", "Điểm mới", 105.7, 21.2), 3),
            CancellationToken.None);

        Assert.False(result.Success);
        Assert.Equal("mapbox_no_route", result.ErrorCode);
        Assert.Equal(0, repository.ReplaceCount);
    }

    private const string ItineraryId = "507f1f77bcf86cd799439011";

    private static ItineraryDocument Current() => new()
    {
        Id = ItineraryId,
        UserId = UserId,
        Version = 3,
        Title = "Hà Nội 2 ngày 1 đêm",
        Destination = "Hà Nội",
        DurationDays = 2,
        DurationNights = 1,
        Profile = "driving",
        Stops =
        [
            Stop("507f1f77bcf86cd799439012", 1, 0, "poi-a", "Điểm A", 105.8, 21.0),
            Stop("507f1f77bcf86cd799439013", 2, 1, "poi-b", "Điểm B", 105.9, 21.1)
        ],
        Route = new ItineraryRouteDocument
        {
            Type = "LineString",
            Coordinates = [[105.8, 21.0], [105.9, 21.1]]
        },
        DistanceMeters = 2000,
        DurationSeconds = 600,
        GeneratedAt = DateTime.UtcNow,
        CreatedAt = DateTime.UtcNow,
        UpdatedAt = DateTime.UtcNow
    };

    private static ItineraryStopDocument Stop(
        string id,
        int order,
        int inputIndex,
        string mapboxId,
        string name,
        double longitude,
        double latitude) => new()
    {
        Id = id,
        Order = order,
        InputIndex = inputIndex,
        MapboxId = mapboxId,
        Name = name,
        Longitude = longitude,
        Latitude = latitude
    };

    private sealed class StubRepository(ItineraryDocument current) : IItineraryRepository
    {
        public int InsertCount { get; private set; }

        public Task InsertAsync(
            ItineraryDocument itinerary,
            CancellationToken cancellationToken)
        {
            InsertCount++;
            current = itinerary;
            return Task.CompletedTask;
        }

        public int ReplaceCount { get; private set; }
        public int? ExpectedVersion { get; private set; }

        public Task<ItineraryDocument?> GetAsync(
            string userId, string id, CancellationToken cancellationToken) =>
            Task.FromResult<ItineraryDocument?>(current);

        public Task<ItineraryDocument?> GetLatestAsync(
            string userId, CancellationToken cancellationToken) =>
            Task.FromResult<ItineraryDocument?>(current);

        public Task<bool> ReplaceAsync(
            ItineraryDocument itinerary,
            int expectedVersion,
            CancellationToken cancellationToken)
        {
            ReplaceCount++;
            ExpectedVersion = expectedVersion;
            current = itinerary;
            return Task.FromResult(true);
        }
    }

    private sealed class StubOptimizationClient(string response) : IMapboxOptimizationClient
    {
        public int CallCount { get; private set; }

        public Task<MapboxRawResponse> OptimizeAsync(
            string profile,
            IReadOnlyList<(double Longitude, double Latitude)> coordinates,
            CancellationToken cancellationToken)
        {
            CallCount++;
            return Task.FromResult(new MapboxRawResponse(200, response, "application/json"));
        }
    }

    private const string ValidOptimizationResponse = """
        {
          "code": "Ok",
          "waypoints": [
            {"waypoint_index": 0},
            {"waypoint_index": 2},
            {"waypoint_index": 1}
          ],
          "trips": [{
            "geometry": {
              "type": "LineString",
              "coordinates": [[105.8,21.0],[105.9,21.1],[105.88,20.96]]
            },
            "distance": 3500,
            "duration": 900
          }]
        }
        """;
}
