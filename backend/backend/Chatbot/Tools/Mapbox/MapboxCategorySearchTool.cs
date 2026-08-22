using System.ComponentModel;
using Backend.Chatbot.Tools;
using Backend.Mapbox;

namespace Backend.Chatbot.Tools.Mapbox;

[Description("Tìm các POI thuộc một canonical category của Mapbox.")]
public sealed class MapboxCategorySearchTool(IMapboxClient mapboxClient)
{
    public const string Name = "mapbox_category_search";
    public const double DefaultMinimumRating = 4.0;
    public const int ResultLimit = 5;

    [Description("Tìm POI theo category ID và toàn bộ bộ lọc Category Search được backend hỗ trợ.")]
    public Task<ToolResult<MapboxPlaceToolData>> ExecuteAsync(
        [Description("Canonical category ID do backend category resolver chọn từ whitelist du lịch.")]
        string categoryId,
        [Description("Các tham số lọc Mapbox Category Search.")]
        MapboxCategorySearchRequest request,
        CancellationToken cancellationToken = default,
        [Description("Ngưỡng rating dùng để lọc kết quả trong backend, không gửi sang Mapbox.")]
        double? minimumRating = null)
    {
        if (string.IsNullOrWhiteSpace(categoryId))
        {
            return Task.FromResult(ToolResult<MapboxPlaceToolData>.Failed(
                "invalid_input",
                "categoryId là tham số bắt buộc."));
        }

        var validationError = MapboxToolSupport.ValidateInput(request);
        if (validationError is not null)
        {
            return Task.FromResult(ToolResult<MapboxPlaceToolData>.Failed(
                "invalid_input",
                validationError));
        }

        var effectiveMinimumRating = minimumRating ?? DefaultMinimumRating;
        if (!double.IsFinite(effectiveMinimumRating)
            || effectiveMinimumRating is < 0 or > 5)
        {
            return Task.FromResult(ToolResult<MapboxPlaceToolData>.Failed(
                "invalid_input",
                "minimumRating phải nằm trong khoảng 0 đến 5."));
        }

        return MapboxToolSupport.ExecuteAsync(
            token => mapboxClient.SearchCategoryAsync(categoryId, request, token),
            json => MapboxToolResponseParser.ParseCategoryPlaces(
                json,
                effectiveMinimumRating,
                ResultLimit),
            cancellationToken);
    }
}
