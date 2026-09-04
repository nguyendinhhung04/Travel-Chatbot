using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using Backend.Conversations;
using Backend.Itineraries;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace Backend.Controllers;

[ApiController]
[Authorize]
[Route("api/conversations")]
[Produces("application/json")]
public sealed class ConversationsController(ConversationService service) : ControllerBase
{
    [HttpGet]
    public async Task<IActionResult> List(CancellationToken cancellationToken) =>
        ToActionResult(await service.ListAsync(CurrentUserId(), cancellationToken));

    [HttpPost]
    public async Task<IActionResult> Create(
        [FromBody] ConversationTurnRequest? request,
        CancellationToken cancellationToken) =>
        ToActionResult(await service.CreateWithFirstTurnAsync(
            CurrentUserId(),
            request?.ToDomain() ?? new ConversationTurnInput(string.Empty, string.Empty, string.Empty),
            cancellationToken));

    [HttpGet("{conversationId}")]
    public async Task<IActionResult> Get(string conversationId, CancellationToken cancellationToken) =>
        ToActionResult(await service.GetAsync(CurrentUserId(), conversationId, cancellationToken));

    [HttpDelete("{conversationId}")]
    public async Task<IActionResult> Delete(string conversationId, CancellationToken cancellationToken) =>
        ToActionResult(await service.DeleteAsync(CurrentUserId(), conversationId, cancellationToken));

    [HttpPost("{conversationId}/turns")]
    public async Task<IActionResult> Append(
        string conversationId,
        [FromBody] ConversationTurnRequest? request,
        CancellationToken cancellationToken) =>
        ToActionResult(await service.AppendTurnAsync(
            CurrentUserId(),
            conversationId,
            request?.ToDomain() ?? new ConversationTurnInput(string.Empty, string.Empty, string.Empty),
            cancellationToken));

    private string CurrentUserId() =>
        User.FindFirstValue(ClaimTypes.NameIdentifier)
        ?? User.FindFirstValue(JwtRegisteredClaimNames.Sub)
        ?? User.FindFirstValue("sub")
        ?? string.Empty;

    private ObjectResult ToActionResult<T>(ConversationOperationResult<T> result) =>
        result.Success
            ? StatusCode(result.StatusCode, result.Data)
            : StatusCode(
                result.StatusCode,
                new ApiErrorResponse(
                    result.ErrorCode ?? "unknown_error",
                    result.ErrorMessage ?? "Yêu cầu không thành công."));
}
