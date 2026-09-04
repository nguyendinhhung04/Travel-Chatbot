using Backend.Speech;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace Backend.Controllers;

[ApiController]
[Authorize]
[Route("api/speech")]
[Produces("application/json")]
public sealed class SpeechController(IGeminiEphemeralTokenClient tokenClient) : ControllerBase
{
    [HttpPost("ephemeral-token")]
    [ProducesResponseType<GeminiEphemeralTokenResponse>(StatusCodes.Status200OK)]
    [ProducesResponseType<SpeechErrorResponse>(StatusCodes.Status502BadGateway)]
    [ProducesResponseType<SpeechErrorResponse>(StatusCodes.Status503ServiceUnavailable)]
    public async Task<IActionResult> CreateEphemeralToken(CancellationToken cancellationToken)
    {
        var result = await tokenClient.CreateAsync(cancellationToken);
        if (ControllerContext.HttpContext is not null)
        {
            Response.Headers.CacheControl = "no-store";
        }

        if (result.Success && result.Token is not null)
        {
            return Ok(new GeminiEphemeralTokenResponse(
                result.Token,
                result.Model,
                result.ExpiresAt));
        }

        var statusCode = result.ErrorCode == "configuration_missing"
            ? StatusCodes.Status503ServiceUnavailable
            : StatusCodes.Status502BadGateway;
        return StatusCode(
            statusCode,
            new SpeechErrorResponse(result.ErrorCode ?? "speech_token_unavailable"));
    }
}

public sealed record GeminiEphemeralTokenResponse(
    string Token,
    string Model,
    DateTimeOffset ExpiresAt);

public sealed record SpeechErrorResponse(string Error);
