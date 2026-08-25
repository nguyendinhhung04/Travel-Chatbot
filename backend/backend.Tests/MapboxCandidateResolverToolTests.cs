using System.Text.Json;
using Backend.Chatbot.Tools.Mapbox;
using Backend.Mapbox;

namespace Backend.Tests;

public sealed class MapboxCandidateResolverToolTests
{
    [Fact]
    public async Task ResolvesCandidatesAndDeduplicatesCategoryPlaces()
    {
        var client = new StubMapboxClient
        {
            ForwardResponses =
            {
                ["Hồ Xuân Hương"] = Response(
                    Place("mapbox.lake", "Ho Xuan Huong", ["lake"], 902)),
                ["Không tồn tại"] = Response(
                    Place("mapbox.market", "Da Lat Night Market", ["market"], 600))
            },
            CategoryResponse = Response(
                Place("mapbox.lake", "Hồ Xuân Hương", ["lake"], 902),
                Place("mapbox.garden", "Vườn Hoa Thành Phố", ["tourist_attraction"], 1200))
        };
        var tool = CreateTool(client);

        var result = await tool.ExecuteAsync(new MapboxCandidateResolutionRequest(
            108.44,
            11.94,
            [
                new MapboxCandidateInput(
                    "candidate-1",
                    "Hồ Xuân Hương",
                    ["Xuan Huong Lake"],
                    ["lake"]),
                new MapboxCandidateInput(
                    "candidate-2",
                    "Không tồn tại",
                    [],
                    [])
            ],
            "tourist_attraction",
            0));

        Assert.True(result.Success);
        var data = Assert.IsType<MapboxCandidateResolutionData>(result.Data);
        Assert.Equal("matched", data.Results[0].Status);
        Assert.Equal("mapbox.lake", data.Results[0].Place?.MapboxId);
        Assert.Equal("not_found", data.Results[1].Status);
        Assert.Null(data.Results[1].Place);
        Assert.Equal("mapbox.garden", Assert.Single(data.AdditionalPlaces).MapboxId);
        Assert.Equal(2, client.ForwardRequests.Count);
        Assert.Equal("108.44,11.94", client.ForwardRequests[0].Proximity);
        Assert.Equal(2, client.ForwardRequests[0].Limit);
        Assert.Equal("tourist_attraction", client.CategoryId);
    }

    [Theory]
    [InlineData(900, 1100, "matched", "mapbox.near")]
    [InlineData(900, 950, "ambiguous", null)]
    public async Task DuplicateExactNamesUseMeaningfulDistanceGap(
        double nearestDistance,
        double secondDistance,
        string expectedStatus,
        string? expectedMapboxId)
    {
        var client = new StubMapboxClient
        {
            ForwardResponses =
            {
                ["Central Park"] = Response(
                    Place("mapbox.near", "Central Park", ["park"], nearestDistance),
                    Place("mapbox.far", "Central Park", ["park"], secondDistance))
            }
        };

        var result = await CreateTool(client).ExecuteAsync(
            Request(new MapboxCandidateInput(
                "candidate-1",
                "Central Park",
                [],
                ["park"])));

        var match = Assert.Single(Assert.IsType<MapboxCandidateResolutionData>(result.Data).Results);
        Assert.Equal(expectedStatus, match.Status);
        Assert.Equal(expectedMapboxId, match.Place?.MapboxId);
    }

    [Fact]
    public async Task ExactNameHasPriorityOverNearNameWithCategoryHint()
    {
        var client = new StubMapboxClient
        {
            ForwardResponses =
            {
                ["Central Park"] = Response(
                    Place("mapbox.exact", "Central Park", ["cafe"], 1000),
                    Place("mapbox.category", "Central Parks", ["park"], 200))
            }
        };

        var result = await CreateTool(client).ExecuteAsync(
            Request(new MapboxCandidateInput(
                "candidate-1",
                "Central Park",
                [],
                ["park"])));

        var match = Assert.Single(Assert.IsType<MapboxCandidateResolutionData>(result.Data).Results);
        Assert.Equal("matched", match.Status);
        Assert.Equal("mapbox.exact", match.Place?.MapboxId);
    }

    [Fact]
    public async Task CategoryHintBreaksDuplicateExactNameTie()
    {
        var client = new StubMapboxClient
        {
            ForwardResponses =
            {
                ["Central Park"] = Response(
                    Place("mapbox.cafe", "Central Park", ["cafe"], 100),
                    Place("mapbox.park", "Central Park", ["park"], 150))
            }
        };

        var result = await CreateTool(client).ExecuteAsync(
            Request(new MapboxCandidateInput(
                "candidate-1",
                "Central Park",
                [],
                ["park"])));

        var match = Assert.Single(Assert.IsType<MapboxCandidateResolutionData>(result.Data).Results);
        Assert.Equal("matched", match.Status);
        Assert.Equal("mapbox.park", match.Place?.MapboxId);
    }

    [Fact]
    public async Task DeduplicatesSameMapboxPlaceAcrossCandidates()
    {
        var sharedPlace = Response(
            Place("mapbox.shared", "Xuan Huong Lake", ["lake"], 500));
        var client = new StubMapboxClient
        {
            ForwardResponses =
            {
                ["Xuan Huong Lake"] = sharedPlace,
                ["Hồ Xuân Hương"] = sharedPlace
            }
        };

        var result = await CreateTool(client).ExecuteAsync(
            new MapboxCandidateResolutionRequest(
                108.44,
                11.94,
                [
                    new MapboxCandidateInput(
                        "candidate-1",
                        "Xuan Huong Lake",
                        [],
                        ["lake"]),
                    new MapboxCandidateInput(
                        "candidate-2",
                        "Hồ Xuân Hương",
                        ["Xuan Huong Lake"],
                        ["lake"])
                ],
                null,
                null));

        var matches = Assert.IsType<MapboxCandidateResolutionData>(result.Data).Results;
        Assert.Equal("matched", matches[0].Status);
        Assert.Equal("duplicate", matches[1].Status);
        Assert.Null(matches[1].Place);
    }

    [Fact]
    public async Task RejectsMoreThanFiveCandidatesBeforeCallingMapbox()
    {
        var client = new StubMapboxClient();
        var candidates = Enumerable.Range(1, 6)
            .Select(index => new MapboxCandidateInput(
                $"candidate-{index}",
                $"Place {index}",
                [],
                []))
            .ToArray();

        var result = await CreateTool(client).ExecuteAsync(
            new MapboxCandidateResolutionRequest(108.44, 11.94, candidates, null, null));

        Assert.False(result.Success);
        Assert.Equal("invalid_input", result.ErrorCode);
        Assert.Empty(client.ForwardRequests);
    }

    private static MapboxCandidateResolverTool CreateTool(IMapboxClient client) => new(
        new MapboxForwardSearchTool(client),
        new MapboxCategorySearchTool(client));

    private static MapboxCandidateResolutionRequest Request(MapboxCandidateInput candidate) =>
        new(108.44, 11.94, [candidate], null, null);

    private static object Place(
        string mapboxId,
        string name,
        string[] categories,
        double distance) => new
        {
            geometry = new { coordinates = new[] { 108.44, 11.94 } },
            properties = new
            {
                name,
                mapbox_id = mapboxId,
                feature_type = "poi",
                full_address = "Đà Lạt, Lâm Đồng",
                poi_category = categories,
                poi_category_ids = categories,
                distance
            }
        };

    private static MapboxRawResponse Response(params object[] features) => new(
        200,
        JsonSerializer.Serialize(new
        {
            type = "FeatureCollection",
            features,
            attribution = "Mapbox"
        }),
        "application/geo+json");

    private sealed class StubMapboxClient : IMapboxClient
    {
        public Dictionary<string, MapboxRawResponse> ForwardResponses { get; } = [];
        public MapboxRawResponse CategoryResponse { get; init; } = Response();
        public List<MapboxForwardSearchRequest> ForwardRequests { get; } = [];
        public string? CategoryId { get; private set; }

        public Task<MapboxRawResponse> ForwardSearchAsync(
            MapboxForwardSearchRequest request,
            CancellationToken cancellationToken)
        {
            ForwardRequests.Add(request);
            return Task.FromResult(
                ForwardResponses.GetValueOrDefault(request.Query ?? string.Empty, Response()));
        }

        public Task<MapboxRawResponse> SearchCategoryAsync(
            string categoryId,
            MapboxCategorySearchRequest request,
            CancellationToken cancellationToken)
        {
            CategoryId = categoryId;
            return Task.FromResult(CategoryResponse);
        }

        public Task<MapboxRawResponse> ListCategoriesAsync(
            string? language,
            CancellationToken cancellationToken) => Task.FromResult(Response());

        public Task<MapboxRawResponse> ReverseLookupAsync(
            MapboxReverseLookupRequest request,
            CancellationToken cancellationToken) => Task.FromResult(Response());
    }
}
