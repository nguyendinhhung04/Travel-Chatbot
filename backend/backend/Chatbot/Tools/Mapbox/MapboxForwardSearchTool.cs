using System.ComponentModel;
using Backend.Chatbot.Tools;
using Backend.Mapbox;

namespace Backend.Chatbot.Tools.Mapbox;

[Description("Tìm địa điểm, địa chỉ hoặc POI bằng văn bản qua Mapbox Forward Search.")]
public sealed class MapboxForwardSearchTool(IMapboxClient mapboxClient)
{
    public const string Name = "mapbox_forward_search";

    [Description("Tìm địa điểm theo toàn bộ tham số Mapbox Forward Search được backend hỗ trợ.")]
    public Task<ToolResult<MapboxPlaceToolData>> ExecuteAsync(
        [Description("Các tham số tìm kiếm, bao gồm q và các bộ lọc tùy chọn.")]
        MapboxForwardSearchRequest request,
        CancellationToken cancellationToken = default)
    {
        var validationError = MapboxToolSupport.ValidateInput(request);
        if (validationError is not null)
        {
            return Task.FromResult(ToolResult<MapboxPlaceToolData>.Failed(
                "invalid_input",
                validationError));
        }

        return MapboxToolSupport.ExecuteAsync(
            token => mapboxClient.ForwardSearchAsync(request, token),
            MapboxToolResponseParser.ParsePlaces,
            cancellationToken);
    }
}
