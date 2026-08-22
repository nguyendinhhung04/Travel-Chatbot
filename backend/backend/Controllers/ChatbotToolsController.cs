using Backend.Chatbot.Tools;
using Backend.Chatbot.Tools.Mapbox;
using Microsoft.AspNetCore.Mvc;

namespace Backend.Controllers;

[ApiController]
[Route("api/chatbot/tools")]
[Produces("application/json")]
public sealed class ChatbotToolsController(
    MapboxForwardSearchTool forwardSearchTool,
    MapboxCategorySearchTool categorySearchTool,
    MapboxReverseLookupTool reverseLookupTool) : ControllerBase
{
    [HttpPost("mapbox-forward-search")]
    [ProducesResponseType<ToolResult<MapboxPlaceToolData>>(StatusCodes.Status200OK)]
    [ProducesResponseType<ToolResult<MapboxPlaceToolData>>(StatusCodes.Status400BadRequest)]
    [ProducesResponseType<ToolResult<MapboxPlaceToolData>>(StatusCodes.Status502BadGateway)]
    [ProducesResponseType<ToolResult<MapboxPlaceToolData>>(StatusCodes.Status504GatewayTimeout)]
    public async Task<IActionResult> ForwardSearch(
        [FromBody] MapboxForwardSearchToolHttpRequest request,
        CancellationToken cancellationToken)
    {
        var result = await forwardSearchTool.ExecuteAsync(
            request.ToMapboxRequest(),
            cancellationToken);
        return ToActionResult(result);
    }

    [HttpPost("mapbox-category-search")]
    [ProducesResponseType<ToolResult<MapboxPlaceToolData>>(StatusCodes.Status200OK)]
    [ProducesResponseType<ToolResult<MapboxPlaceToolData>>(StatusCodes.Status400BadRequest)]
    [ProducesResponseType<ToolResult<MapboxPlaceToolData>>(StatusCodes.Status502BadGateway)]
    [ProducesResponseType<ToolResult<MapboxPlaceToolData>>(StatusCodes.Status504GatewayTimeout)]
    public async Task<IActionResult> CategorySearch(
        [FromBody] MapboxCategorySearchToolHttpRequest request,
        CancellationToken cancellationToken)
    {
        var result = await categorySearchTool.ExecuteAsync(
            request.CategoryId ?? string.Empty,
            request.ToMapboxRequest(),
            cancellationToken,
            request.MinimumRating);
        return ToActionResult(result);
    }

    [HttpPost("mapbox-reverse-lookup")]
    [ProducesResponseType<ToolResult<MapboxPlaceToolData>>(StatusCodes.Status200OK)]
    [ProducesResponseType<ToolResult<MapboxPlaceToolData>>(StatusCodes.Status400BadRequest)]
    [ProducesResponseType<ToolResult<MapboxPlaceToolData>>(StatusCodes.Status502BadGateway)]
    [ProducesResponseType<ToolResult<MapboxPlaceToolData>>(StatusCodes.Status504GatewayTimeout)]
    public async Task<IActionResult> ReverseLookup(
        [FromBody] MapboxReverseLookupToolHttpRequest request,
        CancellationToken cancellationToken)
    {
        var result = await reverseLookupTool.ExecuteAsync(
            request.ToMapboxRequest(),
            cancellationToken);
        return ToActionResult(result);
    }

    private ObjectResult ToActionResult<T>(ToolResult<T> result) where T : class
    {
        var statusCode = result.Success
            ? StatusCodes.Status200OK
            : result.ErrorCode switch
            {
                "invalid_input" => StatusCodes.Status400BadRequest,
                "mapbox_timeout" => StatusCodes.Status504GatewayTimeout,
                _ => StatusCodes.Status502BadGateway
            };

        return StatusCode(statusCode, result);
    }
}
