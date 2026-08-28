using Microsoft.AspNetCore.WebUtilities;
using Microsoft.Extensions.Options;
using System.Net.Http.Json;

namespace Backend.Mapbox;

public sealed class MapboxClient(
    HttpClient httpClient,
    IOptions<MapboxOptions> options,
    ILogger<MapboxClient> logger)
    : IMapboxClient
{
    private const string ForwardPath = "search/searchbox/v1/forward";
    private const string ReverseLookupPath = "search/searchbox/v1/reverse";
    private const string PlacesDetailsPath = "places/v1/details/retrieve";
    private readonly MapboxOptions _options = options.Value;

    public Task<MapboxRawResponse> ForwardSearchAsync(
        MapboxForwardSearchRequest request,
        CancellationToken cancellationToken) =>
        GetAsync(ForwardPath, request.ToQueryParameters(), cancellationToken);

    public Task<MapboxRawResponse> SearchCategoryAsync(
        string categoryId,
        MapboxCategorySearchRequest request,
        CancellationToken cancellationToken)
    {
        var path = $"search/searchbox/v1/category/{Uri.EscapeDataString(categoryId.Trim())}";
        return GetAsync(path, request.ToQueryParameters(), cancellationToken);
    }

    public Task<MapboxRawResponse> ReverseLookupAsync(
        MapboxReverseLookupRequest request,
        CancellationToken cancellationToken) =>
        GetAsync(ReverseLookupPath, request.ToQueryParameters(), cancellationToken);

    public async Task<MapboxRawResponse> RetrievePlacesAsync(
        IReadOnlyList<string> mapboxIds,
        CancellationToken cancellationToken)
    {
        var requestUri = QueryHelpers.AddQueryString(
            PlacesDetailsPath,
            "access_token",
            _options.AccessToken);
        using var response = await httpClient.PostAsJsonAsync(
            requestUri,
            new { ids = mapboxIds },
            cancellationToken);
        var body = await response.Content.ReadAsStringAsync(cancellationToken);
        var contentType = response.Content.Headers.ContentType?.ToString() ?? "application/json";

        logger.LogInformation(
            "Mapbox Retrieve multiple Places response: StatusCode={StatusCode}, ContentType={ContentType}, Body={ResponseBody}",
            (int)response.StatusCode,
            contentType,
            body);

        return new MapboxRawResponse((int)response.StatusCode, body, contentType);
    }

    private async Task<MapboxRawResponse> GetAsync(
        string path,
        Dictionary<string, string?> parameters,
        CancellationToken cancellationToken)
    {
        parameters["access_token"] = _options.AccessToken;
        var requestUri = QueryHelpers.AddQueryString(path, parameters);

        using var response = await httpClient.GetAsync(
            requestUri,
            HttpCompletionOption.ResponseHeadersRead,
            cancellationToken);
        var body = await response.Content.ReadAsStringAsync(cancellationToken);
        var contentType = response.Content.Headers.ContentType?.ToString() ?? "application/json";

        return new MapboxRawResponse((int)response.StatusCode, body, contentType);
    }
}
