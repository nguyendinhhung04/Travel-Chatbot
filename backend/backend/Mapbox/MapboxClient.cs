using Microsoft.AspNetCore.WebUtilities;
using Microsoft.Extensions.Options;

namespace Backend.Mapbox;

public sealed class MapboxClient(HttpClient httpClient, IOptions<MapboxOptions> options)
    : IMapboxClient
{
    private const string ForwardPath = "search/searchbox/v1/forward";
    private const string CategoryListPath = "search/searchbox/v1/list/category";
    private const string ReverseLookupPath = "search/searchbox/v1/reverse";
    private readonly MapboxOptions _options = options.Value;

    public Task<MapboxRawResponse> ForwardSearchAsync(
        MapboxForwardSearchRequest request,
        CancellationToken cancellationToken) =>
        GetAsync(ForwardPath, request.ToQueryParameters(), cancellationToken);

    public Task<MapboxRawResponse> ListCategoriesAsync(
        string? language,
        CancellationToken cancellationToken)
    {
        var parameters = new Dictionary<string, string?>(StringComparer.Ordinal);
        if (!string.IsNullOrWhiteSpace(language))
        {
            parameters["language"] = language.Trim();
        }

        return GetAsync(CategoryListPath, parameters, cancellationToken);
    }

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
