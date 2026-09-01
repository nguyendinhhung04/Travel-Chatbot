using System.Net;
using System.Text;
using System.Text.Json;
using Backend.Controllers;
using Backend.Speech;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc;
using Microsoft.Extensions.Logging.Abstractions;
using Microsoft.Extensions.Options;

namespace Backend.Tests;

public sealed class SpeechControllerTests
{
    [Fact]
    public void Action_ExposesExpectedPostRoute()
    {
        var controllerRoute = typeof(SpeechController)
            .GetCustomAttributes(typeof(RouteAttribute), inherit: true)
            .Cast<RouteAttribute>()
            .Single();
        var actionRoute = typeof(SpeechController)
            .GetMethod(nameof(SpeechController.CreateEphemeralToken))
            ?.GetCustomAttributes(typeof(HttpPostAttribute), inherit: true)
            .Cast<HttpPostAttribute>()
            .Single();

        Assert.Equal("api/speech", controllerRoute.Template);
        Assert.NotNull(actionRoute);
        Assert.Equal("ephemeral-token", actionRoute.Template);
    }

    [Fact]
    public async Task Client_SendsConstrainedTokenRequestAndParsesToken()
    {
        HttpRequestMessage? capturedRequest = null;
        string? capturedBody = null;
        var handler = new StubHttpMessageHandler(async request =>
        {
            capturedRequest = request;
            capturedBody = await request.Content!.ReadAsStringAsync();
            return new HttpResponseMessage(HttpStatusCode.OK)
            {
                Content = new StringContent(
                    "{\"name\":\"authTokens/test-token\"}",
                    Encoding.UTF8,
                    "application/json"),
            };
        });
        using var httpClient = new HttpClient(handler)
        {
            BaseAddress = new Uri("https://generativelanguage.googleapis.com/"),
        };
        var client = new GeminiEphemeralTokenClient(
            httpClient,
            Options.Create(new GeminiLiveOptions { ApiKey = "test-key" }),
            NullLogger<GeminiEphemeralTokenClient>.Instance);

        var result = await client.CreateAsync(CancellationToken.None);

        Assert.True(result.Success);
        Assert.Equal("authTokens/test-token", result.Token);
        Assert.Equal("gemini-3.5-transcribe-live", result.Model);
        Assert.NotEqual(default, result.ExpiresAt);
        Assert.NotNull(capturedRequest);
        Assert.Equal(HttpMethod.Post, capturedRequest!.Method);
        Assert.Equal("/v1alpha/auth_tokens", capturedRequest.RequestUri!.AbsolutePath);
        Assert.Equal("test-key", capturedRequest.Headers.GetValues("x-goog-api-key").Single());

        var body = JsonDocument.Parse(capturedBody!);
        var root = body.RootElement;
        Assert.Equal(1, root.GetProperty("uses").GetInt32());
        var setup = root.GetProperty("bidiGenerateContentSetup");
        Assert.Equal(
            "models/gemini-3.5-transcribe-live",
            setup.GetProperty("model").GetString());
        Assert.Equal(
            "TEXT",
            setup.GetProperty("generationConfig").GetProperty("responseModalities")[0].GetString());
        Assert.Equal(
            "vi-VN",
            setup.GetProperty("inputAudioTranscription").GetProperty("languageCodes")[0].GetString());
        Assert.Equal(
            "SMART",
            setup.GetProperty("inputAudioTranscription").GetProperty("mode").GetString());
        Assert.True(
            setup.GetProperty("realtimeInputConfig")
                .GetProperty("automaticActivityDetection")
                .GetProperty("disabled")
                .GetBoolean());
    }

    [Fact]
    public async Task Client_ReturnsProviderErrorWithoutLeakingResponseBody()
    {
        var handler = new StubHttpMessageHandler(_ => Task.FromResult(
            new HttpResponseMessage(HttpStatusCode.BadGateway)
            {
                Content = new StringContent("secret-provider-details"),
            }));
        using var httpClient = new HttpClient(handler)
        {
            BaseAddress = new Uri("https://generativelanguage.googleapis.com/"),
        };
        var client = new GeminiEphemeralTokenClient(
            httpClient,
            Options.Create(new GeminiLiveOptions { ApiKey = "test-key" }),
            NullLogger<GeminiEphemeralTokenClient>.Instance);

        var result = await client.CreateAsync(CancellationToken.None);

        Assert.False(result.Success);
        Assert.Equal("provider_error", result.ErrorCode);
        Assert.Null(result.Token);
    }

    [Fact]
    public async Task Controller_ReturnsNoStoreTokenResponse()
    {
        var httpContext = new DefaultHttpContext();
        var controller = new SpeechController(new StubTokenClient(
            GeminiEphemeralTokenResult.Succeeded(
                "authTokens/test-token",
                "gemini-3.5-transcribe-live",
                DateTimeOffset.UtcNow.AddMinutes(10))))
        {
            ControllerContext = new ControllerContext { HttpContext = httpContext },
        };

        var action = await controller.CreateEphemeralToken(CancellationToken.None);

        var result = Assert.IsType<OkObjectResult>(action);
        var token = Assert.IsType<GeminiEphemeralTokenResponse>(result.Value);
        Assert.Equal("authTokens/test-token", token.Token);
        Assert.Equal("no-store", httpContext.Response.Headers.CacheControl.ToString());
    }

    [Fact]
    public async Task Controller_Returns503WhenGeminiKeyIsMissing()
    {
        var controller = new SpeechController(new StubTokenClient(
            GeminiEphemeralTokenResult.Failed("configuration_missing")));

        var action = await controller.CreateEphemeralToken(CancellationToken.None);

        var result = Assert.IsType<ObjectResult>(action);
        Assert.Equal(StatusCodes.Status503ServiceUnavailable, result.StatusCode);
        Assert.Equal(
            "configuration_missing",
            Assert.IsType<SpeechErrorResponse>(result.Value).Error);
    }

    private sealed class StubTokenClient(GeminiEphemeralTokenResult result)
        : IGeminiEphemeralTokenClient
    {
        public Task<GeminiEphemeralTokenResult> CreateAsync(CancellationToken cancellationToken) =>
            Task.FromResult(result);
    }

    private sealed class StubHttpMessageHandler(
        Func<HttpRequestMessage, Task<HttpResponseMessage>> handler) : HttpMessageHandler
    {
        protected override Task<HttpResponseMessage> SendAsync(
            HttpRequestMessage request,
            CancellationToken cancellationToken) => handler(request);
    }
}
