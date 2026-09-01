using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Net;
using System.Text.Json;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;

namespace Backend.Speech;

public interface IGeminiEphemeralTokenClient
{
    Task<GeminiEphemeralTokenResult> CreateAsync(CancellationToken cancellationToken);
}

public sealed record GeminiEphemeralTokenResult(
    bool Success,
    string? Token,
    string Model,
    DateTimeOffset ExpiresAt,
    string? ErrorCode)
{
    public static GeminiEphemeralTokenResult Succeeded(
        string token,
        string model,
        DateTimeOffset expiresAt) =>
        new(true, token, model, expiresAt, null);

    public static GeminiEphemeralTokenResult Failed(string errorCode) =>
        new(false, null, string.Empty, default, errorCode);
}

public sealed class GeminiEphemeralTokenClient(
    HttpClient httpClient,
    IOptions<GeminiLiveOptions> options,
    ILogger<GeminiEphemeralTokenClient> logger) : IGeminiEphemeralTokenClient
{
    private const string ApiVersion = "v1alpha";
    private static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web);
    private static readonly TimeSpan TokenLifetime = TimeSpan.FromMinutes(10);
    private static readonly TimeSpan NewSessionLifetime = TimeSpan.FromMinutes(1);

    public async Task<GeminiEphemeralTokenResult> CreateAsync(
        CancellationToken cancellationToken)
    {
        var settings = options.Value;
        if (string.IsNullOrWhiteSpace(settings.ApiKey))
        {
            return GeminiEphemeralTokenResult.Failed("configuration_missing");
        }

        var now = DateTimeOffset.UtcNow;
        var expiresAt = now.Add(TokenLifetime);
        var newSessionExpiresAt = now.Add(NewSessionLifetime);
        var requestBody = new
        {
            uses = 1,
            expireTime = FormatTimestamp(expiresAt),
            newSessionExpireTime = FormatTimestamp(newSessionExpiresAt),
            bidiGenerateContentSetup = new
            {
                model = $"models/{settings.Model}",
                generationConfig = new
                {
                    responseModalities = new[] { "TEXT" },
                },
                inputAudioTranscription = new
                {
                    languageCodes = new[] { "vi-VN" },
                    mode = "SMART",
                },
                realtimeInputConfig = new
                {
                    automaticActivityDetection = new
                    {
                        disabled = true,
                    },
                },
            },
        };

        using var request = new HttpRequestMessage(HttpMethod.Post, $"{ApiVersion}/auth_tokens")
        {
            Content = JsonContent.Create(requestBody, options: JsonOptions),
        };
        request.Headers.Add("x-goog-api-key", settings.ApiKey);
        request.Headers.Accept.Add(new MediaTypeWithQualityHeaderValue("application/json"));

        try
        {
            using var response = await httpClient.SendAsync(request, cancellationToken);
            if (!response.IsSuccessStatusCode)
            {
                var providerBody = await response.Content.ReadAsStringAsync(cancellationToken);
                logger.LogWarning(
                    "Gemini ephemeral token request failed with HTTP {StatusCode}. Provider body: {ProviderBody}",
                    (int)response.StatusCode,
                    Truncate(providerBody));
                return GeminiEphemeralTokenResult.Failed(MapProviderError(response.StatusCode));
            }

            var payload = await response.Content.ReadFromJsonAsync<GeminiAuthTokenPayload>(
                JsonOptions,
                cancellationToken);
            if (string.IsNullOrWhiteSpace(payload?.Name))
            {
                return GeminiEphemeralTokenResult.Failed("provider_invalid_response");
            }

            return GeminiEphemeralTokenResult.Succeeded(
                payload.Name,
                settings.Model,
                expiresAt);
        }
        catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
        {
            return GeminiEphemeralTokenResult.Failed("provider_timeout");
        }
        catch (HttpRequestException)
        {
            return GeminiEphemeralTokenResult.Failed("provider_unavailable");
        }
        catch (JsonException)
        {
            return GeminiEphemeralTokenResult.Failed("provider_invalid_response");
        }
    }

    private static string FormatTimestamp(DateTimeOffset value) =>
        value.UtcDateTime.ToString("yyyy-MM-dd'T'HH:mm:ss'Z'");

    private static string MapProviderError(HttpStatusCode statusCode) => statusCode switch
    {
        HttpStatusCode.BadRequest => "provider_request_invalid",
        HttpStatusCode.Unauthorized or HttpStatusCode.Forbidden => "provider_auth_error",
        HttpStatusCode.NotFound => "provider_endpoint_or_model_not_found",
        HttpStatusCode.TooManyRequests => "provider_quota_exceeded",
        _ => "provider_error",
    };

    private static string Truncate(string value) =>
        value.Length <= 500 ? value : value[..500];

    private sealed record GeminiAuthTokenPayload(string? Name);
}
