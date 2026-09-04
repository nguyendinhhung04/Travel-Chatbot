using Backend.Chatbot.Tools.Mapbox;
using MongoDB.Bson;
using MongoDB.Driver;

namespace Backend.Itineraries;

public sealed record ItineraryOperationResult(
    ItineraryDocument? Data,
    string? ErrorCode = null,
    string? ErrorMessage = null,
    int StatusCode = StatusCodes.Status200OK)
{
    public bool Success => ErrorCode is null;

    public static ItineraryOperationResult Failed(
        string code,
        string message,
        int statusCode) => new(null, code, message, statusCode);
}

public sealed class ItineraryService(
    IItineraryRepository repository,
    MapboxOptimizationTool optimizationTool)
{
    private static readonly HashSet<string> SupportedProfiles =
        ["driving", "walking", "cycling"];

    public async Task<ItineraryOperationResult> CreateAsync(
        string userId,
        CreateItineraryRequest request,
        CancellationToken cancellationToken)
    {
        if (!ObjectId.TryParse(userId, out _)) return InvalidUser();
        var validationError = ValidateCreateRequest(request);
        if (validationError is not null)
        {
            return ItineraryOperationResult.Failed(
                "invalid_input",
                validationError,
                StatusCodes.Status422UnprocessableEntity);
        }

        var profile = request.Profile.Trim().ToLowerInvariant();
        var stops = request.Stops
            .Select(stop => new MapboxOptimizationStop(
                stop.MapboxId.Trim(),
                stop.Name.Trim(),
                stop.Longitude,
                stop.Latitude))
            .ToArray();
        var optimized = await optimizationTool.ExecuteAsync(
            new MapboxOptimizationRequest(profile, stops),
            cancellationToken);
        if (!optimized.Success || optimized.Data is null)
        {
            var status = optimized.ErrorCode switch
            {
                "invalid_input" => StatusCodes.Status422UnprocessableEntity,
                "mapbox_timeout" => StatusCodes.Status504GatewayTimeout,
                _ => StatusCodes.Status502BadGateway
            };
            return ItineraryOperationResult.Failed(
                optimized.ErrorCode ?? "mapbox_invalid_response",
                optimized.ErrorMessage ?? "KhĂ´ng thá»ƒ tá»‘i Æ°u tuyáº¿n Ä‘Æ°á»ng.",
                status);
        }

        var now = DateTime.UtcNow;
        var itinerary = new ItineraryDocument
        {
            Id = ObjectId.GenerateNewId().ToString(),
            UserId = userId,
            Version = 1,
            Title = request.Title.Trim(),
            Destination = request.Destination.Trim(),
            DurationDays = request.DurationDays,
            DurationNights = request.DurationNights,
            Profile = optimized.Data.Profile,
            Stops = optimized.Data.OrderedStops.Select((stop, index) =>
                new ItineraryStopDocument
                {
                    Id = ObjectId.GenerateNewId().ToString(),
                    Order = index + 1,
                    InputIndex = stop.InputIndex,
                    MapboxId = stop.MapboxId,
                    Name = stop.Name,
                    Longitude = stop.Longitude,
                    Latitude = stop.Latitude
                }).ToArray(),
            Route = new ItineraryRouteDocument
            {
                Type = optimized.Data.Geometry.Type,
                Coordinates = optimized.Data.Geometry.Coordinates
            },
            DistanceMeters = optimized.Data.DistanceMeters,
            DurationSeconds = optimized.Data.DurationSeconds,
            GeneratedAt = now,
            CreatedAt = now,
            UpdatedAt = now
        };

        try
        {
            await repository.InsertAsync(itinerary, cancellationToken);
            return new(itinerary, StatusCode: StatusCodes.Status201Created);
        }
        catch (Exception error) when (
            error is MongoException or ItineraryRepositoryUnavailableException)
        {
            return DatabaseFailure();
        }
    }

    public async Task<ItineraryOperationResult> GetAsync(
        string userId,
        string id,
        CancellationToken cancellationToken)
    {
        if (!ObjectId.TryParse(userId, out _) || !ObjectId.TryParse(id, out _))
        {
            return NotFound();
        }
        try
        {
            var item = await repository.GetAsync(userId, id, cancellationToken);
            return item is null ? NotFound() : new(item);
        }
        catch (Exception error) when (
            error is MongoException or ItineraryRepositoryUnavailableException)
        {
            return DatabaseFailure();
        }
    }

    public async Task<ItineraryOperationResult> GetLatestAsync(
        string userId,
        CancellationToken cancellationToken)
    {
        if (!ObjectId.TryParse(userId, out _)) return InvalidUser();
        try
        {
            var item = await repository.GetLatestAsync(userId, cancellationToken);
            return item is null ? NotFound() : new(item);
        }
        catch (Exception error) when (
            error is MongoException or ItineraryRepositoryUnavailableException)
        {
            return DatabaseFailure();
        }
    }

    public async Task<ItineraryOperationResult> AddStopAsync(
        string userId,
        string id,
        AddItineraryStopRequest request,
        CancellationToken cancellationToken)
    {
        var currentResult = await GetAsync(userId, id, cancellationToken);
        if (!currentResult.Success)
        {
            return currentResult;
        }
        var current = currentResult.Data!;
        if (request.ExpectedVersion < 1 || current.Version != request.ExpectedVersion)
        {
            return Conflict(
                "version_conflict",
                "Lịch trình đã thay đổi. Vui lòng tải phiên bản mới nhất.");
        }
        if (current.Stops.Any(stop => stop.MapboxId == request.Stop.MapboxId))
        {
            return Conflict("duplicate_stop", "Địa điểm đã có trong lịch trình.");
        }

        var stops = current.Stops
            .OrderBy(stop => stop.Order)
            .Select(stop => new MapboxOptimizationStop(
                stop.MapboxId,
                stop.Name,
                stop.Longitude,
                stop.Latitude))
            .ToList();
        switch (request.Position.Trim().ToLowerInvariant())
        {
            case "first":
                stops.Insert(0, request.Stop);
                break;
            case "last":
                stops.Add(request.Stop);
                break;
            case "optimized":
                stops.Insert(Math.Max(stops.Count - 1, 1), request.Stop);
                break;
            default:
                return ItineraryOperationResult.Failed(
                    "invalid_position",
                    "position phải là first, last hoặc optimized.",
                    StatusCodes.Status422UnprocessableEntity);
        }

        var optimized = await optimizationTool.ExecuteAsync(
            new MapboxOptimizationRequest(current.Profile, stops),
            cancellationToken);
        if (!optimized.Success || optimized.Data is null)
        {
            var status = optimized.ErrorCode switch
            {
                "invalid_input" => StatusCodes.Status422UnprocessableEntity,
                "mapbox_timeout" => StatusCodes.Status504GatewayTimeout,
                _ => StatusCodes.Status502BadGateway
            };
            return ItineraryOperationResult.Failed(
                optimized.ErrorCode ?? "mapbox_invalid_response",
                optimized.ErrorMessage ?? "Không thể tối ưu tuyến đường.",
                status);
        }

        var stopIds = current.Stops.ToDictionary(
            stop => stop.MapboxId,
            stop => stop.Id,
            StringComparer.Ordinal);
        var now = DateTime.UtcNow;
        var updated = new ItineraryDocument
        {
            Id = current.Id,
            UserId = current.UserId,
            Version = current.Version + 1,
            Title = current.Title,
            Destination = current.Destination,
            DurationDays = current.DurationDays,
            DurationNights = current.DurationNights,
            Profile = optimized.Data.Profile,
            Stops = optimized.Data.OrderedStops.Select((stop, index) =>
                new ItineraryStopDocument
                {
                    Id = stopIds.GetValueOrDefault(stop.MapboxId)
                         ?? ObjectId.GenerateNewId().ToString(),
                    Order = index + 1,
                    InputIndex = stop.InputIndex,
                    MapboxId = stop.MapboxId,
                    Name = stop.Name,
                    Longitude = stop.Longitude,
                    Latitude = stop.Latitude
                }).ToArray(),
            Route = new ItineraryRouteDocument
            {
                Type = optimized.Data.Geometry.Type,
                Coordinates = optimized.Data.Geometry.Coordinates
            },
            DistanceMeters = optimized.Data.DistanceMeters,
            DurationSeconds = optimized.Data.DurationSeconds,
            GeneratedAt = now,
            CreatedAt = current.CreatedAt,
            UpdatedAt = now
        };

        try
        {
            return await repository.ReplaceAsync(
                updated,
                request.ExpectedVersion,
                cancellationToken)
                ? new(updated)
                : Conflict(
                    "version_conflict",
                    "Lịch trình đã thay đổi. Vui lòng tải phiên bản mới nhất.");
        }
        catch (Exception error) when (
            error is MongoException or ItineraryRepositoryUnavailableException)
        {
            return DatabaseFailure();
        }
    }

    private static ItineraryOperationResult NotFound() =>
        ItineraryOperationResult.Failed(
            "itinerary_not_found",
            "Không tìm thấy lịch trình.",
            StatusCodes.Status404NotFound);

    private static ItineraryOperationResult InvalidUser() =>
        ItineraryOperationResult.Failed(
            "invalid_user", "User ID trong token không hợp lệ.",
            StatusCodes.Status401Unauthorized);

    private static string? ValidateCreateRequest(CreateItineraryRequest request)
    {
        if (request is null)
        {
            return "YĂªu cáº§u táº¡o lá»‹ch trĂ¬nh lĂ  báº¯t buá»™c.";
        }
        if (string.IsNullOrWhiteSpace(request.Title)
            || request.Title.Trim().Length > 200)
        {
            return "title pháº£i cĂ³ tá»« 1 Ä‘áº¿n 200 kĂ½ tá»±.";
        }
        if (string.IsNullOrWhiteSpace(request.Destination)
            || request.Destination.Trim().Length > 200)
        {
            return "destination pháº£i cĂ³ tá»« 1 Ä‘áº¿n 200 kĂ½ tá»±.";
        }
        if (request.DurationDays is < 1 or > 365
            || request.DurationNights is < 0 or > 365)
        {
            return "durationDays/durationNights khĂ´ng há»£p lá»‡.";
        }
        if (string.IsNullOrWhiteSpace(request.Profile)
            || !SupportedProfiles.Contains(request.Profile.Trim().ToLowerInvariant()))
        {
            return "profile pháº£i lĂ  driving, walking hoáº·c cycling.";
        }
        if (request.Stops is null || request.Stops.Count is < 2 or > 12)
        {
            return "Lá»‹ch trĂ¬nh pháº£i cĂ³ tá»« 2 Ä‘áº¿n 12 Ä‘iá»ƒm dừng.";
        }
        var mapboxIds = new HashSet<string>(StringComparer.Ordinal);
        foreach (var stop in request.Stops)
        {
            if (stop is null
                || string.IsNullOrWhiteSpace(stop.MapboxId)
                || string.IsNullOrWhiteSpace(stop.Name)
                || !double.IsFinite(stop.Longitude)
                || stop.Longitude is < -180 or > 180
                || !double.IsFinite(stop.Latitude)
                || stop.Latitude is < -90 or > 90)
            {
                return "Mỗi stop phải có mapboxId, name và tọa độ hợp lệ.";
            }
            if (!mapboxIds.Add(stop.MapboxId.Trim()))
            {
                return "Các stop không được trùng mapboxId.";
            }
        }
        return null;
    }

    private static ItineraryOperationResult Conflict(string code, string message) =>
        ItineraryOperationResult.Failed(code, message, StatusCodes.Status409Conflict);

    private static ItineraryOperationResult DatabaseFailure() =>
        ItineraryOperationResult.Failed(
            "database_unavailable",
            "Không thể kết nối đến MongoDB.",
            StatusCodes.Status503ServiceUnavailable);
}
