using System.ComponentModel;
using Backend.Chatbot.Tools;
using Backend.Mapbox;

namespace Backend.Chatbot.Tools.Mapbox;

[Description("Tìm các POI thuộc một canonical category của Mapbox.")]
public sealed class MapboxCategorySearchTool(IMapboxClient mapboxClient)
{
    public const string Name = "mapbox_category_search";

    [Description("Tìm POI theo category ID và toàn bộ bộ lọc Category Search được backend hỗ trợ.")]
    public Task<ToolResult<MapboxPlaceToolData>> ExecuteAsync(
        [Description("Canonical category ID lấy từ tool mapbox_list_categories.")]
        string categoryId,
        [Description("Các tham số lọc Mapbox Category Search.")]
        MapboxCategorySearchRequest request,
        CancellationToken cancellationToken = default)
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

        return MapboxToolSupport.ExecuteAsync(
            token => mapboxClient.SearchCategoryAsync(categoryId, request, token),
            MapboxToolResponseParser.ParsePlaces,
            cancellationToken);
    }
}
