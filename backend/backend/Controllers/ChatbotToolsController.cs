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
    MapboxReverseLookupTool reverseLookupTool,
    MapboxCandidateResolverTool candidateResolverTool) : ControllerBase
{
    [HttpPost("mapbox-forward-search")]
    [ProducesResponseType<ToolResult<MapboxPlaceSummaryData>>(StatusCodes.Status200OK)]
    [ProducesResponseType<ToolResult<MapboxPlaceSummaryData>>(StatusCodes.Status400BadRequest)]
    [ProducesResponseType<ToolResult<MapboxPlaceSummaryData>>(StatusCodes.Status502BadGateway)]
    [ProducesResponseType<ToolResult<MapboxPlaceSummaryData>>(StatusCodes.Status504GatewayTimeout)]
    public async Task<IActionResult> ForwardSearch(
        [FromBody] MapboxForwardSearchToolHttpRequest request,
        CancellationToken cancellationToken)
    {
        var result = await forwardSearchTool.ExecuteAsync(
            request.ToMapboxRequest(),
            cancellationToken);
        return ToActionResult(ToSummaryResult(result));
    }

    [HttpPost("mapbox-category-search")]
    [ProducesResponseType<ToolResult<MapboxPlaceSummaryData>>(StatusCodes.Status200OK)]
    [ProducesResponseType<ToolResult<MapboxPlaceSummaryData>>(StatusCodes.Status400BadRequest)]
    [ProducesResponseType<ToolResult<MapboxPlaceSummaryData>>(StatusCodes.Status502BadGateway)]
    [ProducesResponseType<ToolResult<MapboxPlaceSummaryData>>(StatusCodes.Status504GatewayTimeout)]
    public async Task<IActionResult> CategorySearch(
        [FromBody] MapboxCategorySearchToolHttpRequest request,
        CancellationToken cancellationToken)
    {
        var result = await categorySearchTool.ExecuteAsync(
            request.CategoryId ?? string.Empty,
            request.ToMapboxRequest(),
            cancellationToken,
            request.MinimumRating);
        return ToActionResult(ToSummaryResult(result));
    }

    [HttpPost("mapbox-reverse-lookup")]
    [ProducesResponseType<ToolResult<MapboxPlaceSummaryData>>(StatusCodes.Status200OK)]
    [ProducesResponseType<ToolResult<MapboxPlaceSummaryData>>(StatusCodes.Status400BadRequest)]
    [ProducesResponseType<ToolResult<MapboxPlaceSummaryData>>(StatusCodes.Status502BadGateway)]
    [ProducesResponseType<ToolResult<MapboxPlaceSummaryData>>(StatusCodes.Status504GatewayTimeout)]
    public async Task<IActionResult> ReverseLookup(
        [FromBody] MapboxReverseLookupToolHttpRequest request,
        CancellationToken cancellationToken)
    {
        var result = await reverseLookupTool.ExecuteAsync(
            request.ToMapboxRequest(),
            cancellationToken);
        return ToActionResult(ToSummaryResult(result));
    }

    [HttpPost("mapbox-resolve-candidates")]
    [ProducesResponseType<ToolResult<MapboxCandidateResolutionData>>(StatusCodes.Status200OK)]
    [ProducesResponseType<ToolResult<MapboxCandidateResolutionData>>(StatusCodes.Status400BadRequest)]
    [ProducesResponseType<ToolResult<MapboxCandidateResolutionData>>(StatusCodes.Status502BadGateway)]
    [ProducesResponseType<ToolResult<MapboxCandidateResolutionData>>(StatusCodes.Status504GatewayTimeout)]
    public async Task<IActionResult> ResolveCandidates(
        [FromBody] MapboxCandidateResolveToolHttpRequest request,
        CancellationToken cancellationToken)
    {
        var result = await candidateResolverTool.ExecuteAsync(
            request.ToResolutionRequest(),
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

    private static ToolResult<MapboxPlaceSummaryData> ToSummaryResult(
        ToolResult<MapboxPlaceToolData> result)
    {
        if (result.Success && result.Data is not null)
        {
            return ToolResult<MapboxPlaceSummaryData>.Succeeded(
                MapboxPlaceSummaryData.From(result.Data));
        }

        return ToolResult<MapboxPlaceSummaryData>.Failed(
            result.ErrorCode ?? "mapbox_invalid_response",
            result.ErrorMessage ?? "Mapbox tool trả về dữ liệu không hợp lệ.");
    }
}
