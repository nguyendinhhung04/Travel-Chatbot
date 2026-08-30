using Backend.Itineraries;
using Microsoft.AspNetCore.Mvc;

namespace Backend.Controllers;

[ApiController]
[Route("api/users/admin/itineraries")]
[Produces("application/json")]
public sealed class ItinerariesController(ItineraryService service) : ControllerBase
{
    [HttpPost]
    public async Task<IActionResult> Create(
        [FromBody] CreateItineraryRequest request,
        CancellationToken cancellationToken) =>
        ToActionResult(await service.CreateAsync(request, cancellationToken));

    [HttpGet("latest")]
    public async Task<IActionResult> Latest(CancellationToken cancellationToken) =>
        ToActionResult(await service.GetLatestAsync(cancellationToken));

    [HttpGet("{id}")]
    public async Task<IActionResult> Get(string id, CancellationToken cancellationToken) =>
        ToActionResult(await service.GetAsync(id, cancellationToken));

    [HttpPost("{id}/stops")]
    public async Task<IActionResult> AddStop(
        string id,
        [FromBody] AddItineraryStopRequest request,
        CancellationToken cancellationToken) =>
        ToActionResult(await service.AddStopAsync(id, request, cancellationToken));

    private ObjectResult ToActionResult(ItineraryOperationResult result) =>
        result.Success
            ? StatusCode(result.StatusCode, result.Data)
            : StatusCode(
                result.StatusCode,
                new ApiErrorResponse(
                    result.ErrorCode ?? "unknown_error",
                    result.ErrorMessage ?? "Yêu cầu không thành công."));
}
