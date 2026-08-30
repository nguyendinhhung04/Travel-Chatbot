using System.ComponentModel;
using System.Text.Json;
using Backend.Chatbot.Tools;
using Backend.Mapbox;

namespace Backend.Chatbot.Tools.Mapbox;

[Description("Tối ưu thứ tự và tính tuyến đường qua các địa điểm đã được xác minh.")]
public sealed class MapboxOptimizationTool(IMapboxOptimizationClient client)
{
    public const string Name = "mapbox_optimize_route";
    public const int MinimumStops = 2;
    public const int MaximumStops = 12;

    private static readonly HashSet<string> SupportedProfiles =
        ["driving", "walking", "cycling"];

    [Description("Tối ưu một tuyến đường qua từ 2 đến 12 địa điểm đã có tọa độ.")]
    public Task<ToolResult<MapboxOptimizedRouteData>> ExecuteAsync(
        [Description("Profile di chuyển và danh sách địa điểm đã được Mapbox xác minh.")]
        MapboxOptimizationRequest request,
        CancellationToken cancellationToken = default)
    {
        var validationError = Validate(request);
        if (validationError is not null)
        {
            return Task.FromResult(
                ToolResult<MapboxOptimizedRouteData>.Failed(
                    "invalid_input",
                    validationError));
        }

        var profile = request.Profile.Trim().ToLowerInvariant();
        var coordinates = request.Stops
            .Select(stop => (stop.Longitude, stop.Latitude))
            .ToArray();
        return MapboxToolSupport.ExecuteAsync(
            token => client.OptimizeAsync(profile, coordinates, token),
            json => Parse(json, profile, request.Stops),
            cancellationToken);
    }

    internal static MapboxOptimizedRouteData Parse(
        string json,
        string profile,
        IReadOnlyList<MapboxOptimizationStop> inputStops)
    {
        using var document = JsonDocument.Parse(json);
        var root = document.RootElement;
        var code = RequiredString(root, "code");
        if (!string.Equals(code, "Ok", StringComparison.Ordinal))
        {
            throw ProviderFailure(code);
        }

        var waypoints = RequiredArray(root, "waypoints");
        var trips = RequiredArray(root, "trips");
        if (waypoints.GetArrayLength() != inputStops.Count
            || trips.GetArrayLength() != 1)
        {
            throw new JsonException("Mapbox optimization response is incomplete.");
        }

        var orderedStops = new List<MapboxOptimizedStop>(inputStops.Count);
        var waypointOrders = new HashSet<int>();
        var inputIndex = 0;
        foreach (var waypoint in waypoints.EnumerateArray())
        {
            if (waypoint.ValueKind != JsonValueKind.Object
                || !waypoint.TryGetProperty("waypoint_index", out var orderElement)
                || !orderElement.TryGetInt32(out var zeroBasedOrder)
                || zeroBasedOrder < 0
                || zeroBasedOrder >= inputStops.Count
                || !waypointOrders.Add(zeroBasedOrder))
            {
                throw new JsonException("Mapbox waypoint order is invalid.");
            }

            var stop = inputStops[inputIndex];
            orderedStops.Add(new MapboxOptimizedStop(
                zeroBasedOrder + 1,
                inputIndex,
                stop.MapboxId,
                stop.Name,
                stop.Longitude,
                stop.Latitude));
            inputIndex++;
        }
        orderedStops.Sort((left, right) => left.Order.CompareTo(right.Order));

        var trip = trips[0];
        if (trip.ValueKind != JsonValueKind.Object)
        {
            throw new JsonException("Mapbox trip is invalid.");
        }
        var geometry = ParseGeometry(trip);
        var distance = RequiredNonNegativeFiniteNumber(trip, "distance");
        var duration = RequiredNonNegativeFiniteNumber(trip, "duration");

        return new MapboxOptimizedRouteData(
            profile,
            orderedStops,
            geometry,
            distance,
            duration);
    }

    private static string? Validate(MapboxOptimizationRequest request)
    {
        if (request is null)
        {
            return "Yêu cầu tối ưu tuyến đường là bắt buộc.";
        }
        if (string.IsNullOrWhiteSpace(request.Profile)
            || !SupportedProfiles.Contains(request.Profile.Trim().ToLowerInvariant()))
        {
            return "profile phải là driving, walking hoặc cycling.";
        }
        if (request.Stops is null
            || request.Stops.Count is < MinimumStops or > MaximumStops)
        {
            return $"Tuyến đường phải có từ {MinimumStops} đến {MaximumStops} địa điểm.";
        }
        if (request.Stops.Any(stop =>
                stop is null
                || string.IsNullOrWhiteSpace(stop.MapboxId)
                || string.IsNullOrWhiteSpace(stop.Name)
                || !double.IsFinite(stop.Longitude)
                || stop.Longitude is < -180 or > 180
                || !double.IsFinite(stop.Latitude)
                || stop.Latitude is < -90 or > 90))
        {
            return "Thông tin địa điểm không hợp lệ.";
        }
        if (request.Stops
            .Select(stop => stop.MapboxId)
            .Distinct(StringComparer.Ordinal)
            .Count() != request.Stops.Count)
        {
            return "mapboxId của các địa điểm không được trùng nhau.";
        }
        return null;
    }

    private static GeoJsonLineString ParseGeometry(JsonElement trip)
    {
        if (!trip.TryGetProperty("geometry", out var geometry)
            || geometry.ValueKind != JsonValueKind.Object
            || !string.Equals(
                RequiredString(geometry, "type"),
                "LineString",
                StringComparison.Ordinal)
            || !geometry.TryGetProperty("coordinates", out var coordinates)
            || coordinates.ValueKind != JsonValueKind.Array
            || coordinates.GetArrayLength() < 2)
        {
            throw new JsonException("Mapbox route geometry is invalid.");
        }

        var parsedCoordinates = new List<IReadOnlyList<double>>();
        foreach (var pair in coordinates.EnumerateArray())
        {
            if (pair.ValueKind != JsonValueKind.Array || pair.GetArrayLength() != 2)
            {
                throw new JsonException("Mapbox route coordinate is invalid.");
            }
            var longitude = pair[0].GetDouble();
            var latitude = pair[1].GetDouble();
            if (!double.IsFinite(longitude)
                || longitude is < -180 or > 180
                || !double.IsFinite(latitude)
                || latitude is < -90 or > 90)
            {
                throw new JsonException("Mapbox route coordinate is out of range.");
            }
            parsedCoordinates.Add([longitude, latitude]);
        }
        return new GeoJsonLineString("LineString", parsedCoordinates);
    }

    private static JsonElement RequiredArray(JsonElement parent, string propertyName)
    {
        if (!parent.TryGetProperty(propertyName, out var value)
            || value.ValueKind != JsonValueKind.Array)
        {
            throw new JsonException($"Mapbox response is missing {propertyName}.");
        }
        return value;
    }

    private static string RequiredString(JsonElement parent, string propertyName)
    {
        if (!parent.TryGetProperty(propertyName, out var value)
            || value.ValueKind != JsonValueKind.String
            || string.IsNullOrWhiteSpace(value.GetString()))
        {
            throw new JsonException($"Mapbox response is missing {propertyName}.");
        }
        return value.GetString()!;
    }

    private static double RequiredNonNegativeFiniteNumber(
        JsonElement parent,
        string propertyName)
    {
        if (!parent.TryGetProperty(propertyName, out var value)
            || value.ValueKind != JsonValueKind.Number
            || !value.TryGetDouble(out var number)
            || !double.IsFinite(number)
            || number < 0)
        {
            throw new JsonException($"Mapbox response has invalid {propertyName}.");
        }
        return number;
    }

    private static MapboxToolFailureException ProviderFailure(string code) => code switch
    {
        "NoRoute" => new(
            "mapbox_no_route",
            "Mapbox không tìm thấy tuyến đường qua các địa điểm đã chọn."),
        "NoTrips" => new(
            "mapbox_no_trips",
            "Mapbox không thể tạo hành trình qua các địa điểm đã chọn."),
        "NoSegment" => new(
            "mapbox_no_segment",
            "Một hoặc nhiều địa điểm không nằm gần đoạn đường có thể định tuyến."),
        "NotImplemented" => new(
            "mapbox_not_implemented",
            "Mapbox không hỗ trợ tổ hợp tham số tối ưu tuyến đường này."),
        _ => new(
            "mapbox_invalid_response",
            "Mapbox API trả về trạng thái tối ưu tuyến đường không hợp lệ.")
    };
}
