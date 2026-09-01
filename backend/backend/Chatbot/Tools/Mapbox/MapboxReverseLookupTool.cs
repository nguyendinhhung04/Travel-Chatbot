using System.ComponentModel;
using Backend.Chatbot.Tools;
using Backend.Mapbox;

namespace Backend.Chatbot.Tools.Mapbox;

[Description("Tra cứu địa điểm và địa chỉ quanh một cặp tọa độ bằng Mapbox Reverse Lookup.")]
public sealed class MapboxReverseLookupTool(IMapboxClient mapboxClient)
{
    public const string Name = "mapbox_reverse_lookup";

    [Description("Tra cứu ngược theo toàn bộ tham số Mapbox Reverse Lookup được backend hỗ trợ.")]
    public Task<ToolResult<MapboxPlaceToolData>> ExecuteAsync(
        [Description("Các tham số tra cứu, bắt buộc có longitude và latitude.")]
        MapboxReverseLookupRequest request,
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
            token => mapboxClient.ReverseLookupAsync(request, token),
            MapboxToolResponseParser.ParsePlaces,
            cancellationToken);
    }
}
