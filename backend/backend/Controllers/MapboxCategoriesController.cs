using Backend.Mapbox;
using Microsoft.AspNetCore.Mvc;

namespace Backend.Controllers;

[ApiController]
[Route("api/mapbox/categories")]
public sealed class MapboxCategoriesController(
    IMapboxClient mapboxClient,
    ILogger<MapboxCategoriesController> logger) : ControllerBase
{
    private static readonly HashSet<string> AllowedQueryParameters =
        new(["language"], StringComparer.OrdinalIgnoreCase);

    [HttpGet]
    [Produces("application/json")]
    [ProducesResponseType(StatusCodes.Status200OK)]
    [ProducesResponseType<ProblemDetails>(StatusCodes.Status400BadRequest)]
    [ProducesResponseType<ProblemDetails>(StatusCodes.Status502BadGateway)]
    [ProducesResponseType<ProblemDetails>(StatusCodes.Status504GatewayTimeout)]
    public async Task<IActionResult> ListCategories(
        [FromQuery] string? language,
        CancellationToken cancellationToken)
    {
        var invalidQueryResult = RejectUnknownQueryParameters(AllowedQueryParameters);
        if (invalidQueryResult is not null)
        {
            return invalidQueryResult;
        }

        try
        {
            var response = await mapboxClient.ListCategoriesAsync(language, cancellationToken);
            return new ContentResult
            {
                StatusCode = response.StatusCode,
                Content = response.Body,
                ContentType = response.ContentType
            };
        }
        catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
        {
            logger.LogWarning("Mapbox Category List API request timed out.");
            return Problem(
                statusCode: StatusCodes.Status504GatewayTimeout,
                title: "Mapbox API hết thời gian phản hồi.");
        }
        catch (HttpRequestException exception)
        {
            logger.LogWarning(
                "Could not connect to Mapbox Category List API. Error type: {ErrorType}",
                exception.GetType().Name);
            return Problem(
                statusCode: StatusCodes.Status502BadGateway,
                title: "Không thể kết nối đến Mapbox API.");
        }
    }

    [HttpGet("{categoryId}")]
    [Produces("application/geo+json", "application/json")]
    [ProducesResponseType(StatusCodes.Status200OK)]
    [ProducesResponseType<ProblemDetails>(StatusCodes.Status400BadRequest)]
    [ProducesResponseType<ProblemDetails>(StatusCodes.Status502BadGateway)]
    [ProducesResponseType<ProblemDetails>(StatusCodes.Status504GatewayTimeout)]
    public async Task<IActionResult> SearchCategory(
        [FromRoute] string categoryId,
        [FromQuery] MapboxCategorySearchRequest request,
        CancellationToken cancellationToken)
    {
        if (string.IsNullOrWhiteSpace(categoryId))
        {
            ModelState.AddModelError(nameof(categoryId), "categoryId là tham số bắt buộc.");
        }

        var invalidQueryResult = RejectUnknownQueryParameters(
            MapboxCategorySearchRequest.AllowedQueryParameters);
        if (!ModelState.IsValid || invalidQueryResult is not null)
        {
            return invalidQueryResult ?? BadRequest(new ValidationProblemDetails(ModelState)
            {
                Status = StatusCodes.Status400BadRequest,
                Title = "Yêu cầu Category Search không hợp lệ."
            });
        }

        try
        {
            var response = await mapboxClient.SearchCategoryAsync(
                categoryId,
                request,
                cancellationToken);
            return new ContentResult
            {
                StatusCode = response.StatusCode,
                Content = response.Body,
                ContentType = response.ContentType
            };
        }
        catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
        {
            logger.LogWarning("Mapbox Category Search API request timed out.");
            return Problem(
                statusCode: StatusCodes.Status504GatewayTimeout,
                title: "Mapbox API hết thời gian phản hồi.");
        }
        catch (HttpRequestException exception)
        {
            logger.LogWarning(
                "Could not connect to Mapbox Category Search API. Error type: {ErrorType}",
                exception.GetType().Name);
            return Problem(
                statusCode: StatusCodes.Status502BadGateway,
                title: "Không thể kết nối đến Mapbox API.");
        }
    }

    private IActionResult? RejectUnknownQueryParameters(IReadOnlySet<string> allowedParameters)
    {
        var unknownParameters = Request.Query.Keys
            .Where(name => !allowedParameters.Contains(name))
            .ToArray();

        if (unknownParameters.Length == 0)
        {
            return null;
        }

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
}
