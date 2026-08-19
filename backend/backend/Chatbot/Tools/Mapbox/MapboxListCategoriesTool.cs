using System.ComponentModel;
using Backend.Chatbot.Tools;
using Backend.Mapbox;

namespace Backend.Chatbot.Tools.Mapbox;

[Description("Lấy danh sách category Mapbox để chatbot chọn canonical category ID.")]
public sealed class MapboxListCategoriesTool(IMapboxClient mapboxClient)
{
    public const string Name = "mapbox_list_categories";

    [Description("Lấy danh sách category Mapbox theo ngôn ngữ tùy chọn.")]
    public Task<ToolResult<MapboxCategoryToolData>> ExecuteAsync(
        [Description("Mã ngôn ngữ Mapbox; để trống để dùng ngôn ngữ mặc định.")]
        string? language = null,
        CancellationToken cancellationToken = default) =>
        MapboxToolSupport.ExecuteAsync(
            token => mapboxClient.ListCategoriesAsync(language, token),
            MapboxToolResponseParser.ParseCategories,
            cancellationToken);
}
