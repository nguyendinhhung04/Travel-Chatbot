using Backend.Mapbox;
using Microsoft.AspNetCore.Mvc;

namespace Backend.Controllers;

[ApiController]
[Route("api/mapbox/search")]
public sealed class MapboxSearchController(
    IMapboxClient mapboxClient,
    ILogger<MapboxSearchController> logger) : ControllerBase
{
    [HttpGet]
    [Produces("application/geo+json", "application/json")]
    [ProducesResponseType(StatusCodes.Status200OK)]
    [ProducesResponseType<ProblemDetails>(StatusCodes.Status400BadRequest)]
    [ProducesResponseType<ProblemDetails>(StatusCodes.Status502BadGateway)]
    [ProducesResponseType<ProblemDetails>(StatusCodes.Status504GatewayTimeout)]
    public async Task<IActionResult> Search(
        [FromQuery] MapboxForwardSearchRequest request,
        CancellationToken cancellationToken)
    {
        var unknownParameters = Request.Query.Keys
            .Where(name => !MapboxForwardSearchRequest.AllowedQueryParameters.Contains(name))
            .ToArray();

        if (unknownParameters.Length > 0)
        {
            foreach (var parameter in unknownParameters)
            {
                ModelState.AddModelError(parameter, $"Tham số query '{parameter}' không được hỗ trợ.");
            }

            return BadRequest(new ValidationProblemDetails(ModelState)
            {
                Status = StatusCodes.Status400BadRequest,
                Title = "Có tham số query không hợp lệ."
            });
        }

        try
        {
            var response = await mapboxClient.ForwardSearchAsync(request, cancellationToken);
            return new ContentResult
            {
                StatusCode = response.StatusCode,
                Content = response.Body,
                ContentType = response.ContentType
            };
        }
        catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
        {
            logger.LogWarning("Mapbox Search Text API request timed out.");
            return Problem(
                statusCode: StatusCodes.Status504GatewayTimeout,
                title: "Mapbox API hết thời gian phản hồi.");
        }
        catch (HttpRequestException exception)
        {
            logger.LogWarning(
                "Could not connect to Mapbox Search Text API. Error type: {ErrorType}",
                exception.GetType().Name);
            return Problem(
                statusCode: StatusCodes.Status502BadGateway,
                title: "Không thể kết nối đến Mapbox API.");
        }
    }
}
