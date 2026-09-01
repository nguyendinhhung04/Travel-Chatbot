using Backend.Chatbot.Tools;
using Backend.Mapbox;

namespace Backend.Chatbot.Tools.Mapbox;

public sealed class MapboxPlacesDetailsTool(IMapboxClient mapboxClient)
{
    public Task<ToolResult<MapboxPlacesDetailsData>> ExecuteAsync(
        MapboxPlacesDetailsHttpRequest request,
        CancellationToken cancellationToken = default)
    {
        var validationError = MapboxToolSupport.ValidateInput(request);
        if (validationError is not null)
        {
            return Task.FromResult(ToolResult<MapboxPlacesDetailsData>.Failed(
                "invalid_input",
                validationError));
        }

        return MapboxToolSupport.ExecuteAsync(
            token => mapboxClient.RetrievePlacesAsync(request.Ids, token),
            MapboxToolResponseParser.ParsePlaceDetails,
            cancellationToken);
    }
}
