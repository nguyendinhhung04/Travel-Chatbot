using Backend.Itineraries;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;

namespace Backend.Controllers;

[ApiController]
[Authorize]
[Route("api/itineraries")]
[Route("api/users/admin/itineraries")]
[Produces("application/json")]
public sealed class ItinerariesController(ItineraryService service) : ControllerBase
{
    [HttpPost]
    public async Task<IActionResult> Create(
        [FromBody] CreateItineraryRequest request,
        CancellationToken cancellationToken) =>
        ToActionResult(await service.CreateAsync(CurrentUserId(), request, cancellationToken));

    [HttpGet("latest")]
    public async Task<IActionResult> Latest(CancellationToken cancellationToken) =>
        ToActionResult(await service.GetLatestAsync(CurrentUserId(), cancellationToken));

    [HttpGet("{id}")]
    public async Task<IActionResult> Get(string id, CancellationToken cancellationToken) =>
        ToActionResult(await service.GetAsync(CurrentUserId(), id, cancellationToken));

    [HttpPost("{id}/stops")]
    public async Task<IActionResult> AddStop(
        string id,
        [FromBody] AddItineraryStopRequest request,
        CancellationToken cancellationToken) =>
        ToActionResult(await service.AddStopAsync(CurrentUserId(), id, request, cancellationToken));

    private string CurrentUserId() =>
        User.FindFirstValue(ClaimTypes.NameIdentifier)
        ?? User.FindFirstValue(JwtRegisteredClaimNames.Sub)
        ?? User.FindFirstValue("sub")
        ?? string.Empty;

    private ObjectResult ToActionResult(ItineraryOperationResult result) =>
        result.Success
            ? StatusCode(result.StatusCode, result.Data)
            : StatusCode(
                result.StatusCode,
                new ApiErrorResponse(
                    result.ErrorCode ?? "unknown_error",
                    result.ErrorMessage ?? "Yêu cầu không thành công."));
}
