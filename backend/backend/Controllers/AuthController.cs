using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using Backend.Auth;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace Backend.Controllers;

[ApiController]
[Route("api/auth")]
[Produces("application/json")]
public sealed class AuthController(AuthService service) : ControllerBase
{
    [AllowAnonymous]
    [HttpPost("register")]
    public async Task<IActionResult> Register(
        [FromBody] RegisterRequest? request,
        CancellationToken cancellationToken) =>
        ToActionResult(await service.RegisterAsync(request, cancellationToken));

    [AllowAnonymous]
    [HttpPost("login")]
    public async Task<IActionResult> Login(
        [FromBody] LoginRequest? request,
        CancellationToken cancellationToken) =>
        ToActionResult(await service.LoginAsync(request, cancellationToken));

    [Authorize]
    [HttpGet("me")]
    public async Task<IActionResult> Me(CancellationToken cancellationToken)
    {
        var userId = User.FindFirstValue(JwtRegisteredClaimNames.Sub)
                     ?? User.FindFirstValue(ClaimTypes.NameIdentifier);
        return ToActionResult(await service.GetCurrentUserAsync(userId, cancellationToken));
    }

    private ObjectResult ToActionResult(AuthOperationResult result)
    {
        if (!result.Success)
        {
            return StatusCode(
                result.StatusCode,
                new AuthErrorResponse(
                    result.ErrorCode ?? "unknown_error",
                    result.ErrorMessage ?? "Yêu cầu không thành công."));
        }

        if (result.AccessToken is not null && result.User is not null)
        {
            return StatusCode(result.StatusCode, new LoginResponse(result.AccessToken, result.User));
        }

        return StatusCode(result.StatusCode, result.User);
    }
}
