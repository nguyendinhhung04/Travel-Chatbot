using System.Globalization;
using Microsoft.AspNetCore.WebUtilities;
using Microsoft.Extensions.Options;

namespace Backend.Mapbox;

public sealed class MapboxOptimizationClient(
    HttpClient httpClient,
    IOptions<MapboxOptions> options) : IMapboxOptimizationClient
{
    private readonly MapboxOptions _options = options.Value;

    public async Task<MapboxRawResponse> OptimizeAsync(
        string profile,
        IReadOnlyList<(double Longitude, double Latitude)> coordinates,
        CancellationToken cancellationToken)
    {
        var coordinatePath = string.Join(
            ';',
            coordinates.Select(coordinate => string.Create(
                CultureInfo.InvariantCulture,
                $"{coordinate.Longitude},{coordinate.Latitude}")));
        var path = string.Create(
            CultureInfo.InvariantCulture,
            $"optimized-trips/v1/mapbox/{Uri.EscapeDataString(profile)}/{coordinatePath}");
        var requestUri = QueryHelpers.AddQueryString(
            path,
            new Dictionary<string, string?>
            {
                ["roundtrip"] = "false",
                ["source"] = "first",
                ["destination"] = "last",
                ["geometries"] = "geojson",
                ["overview"] = "full",
                ["access_token"] = _options.AccessToken
            });

        using var response = await httpClient.GetAsync(
            requestUri,
            HttpCompletionOption.ResponseHeadersRead,
            cancellationToken);
        var body = await response.Content.ReadAsStringAsync(cancellationToken);
        var contentType = response.Content.Headers.ContentType?.ToString()
            ?? "application/json";
        return new MapboxRawResponse((int)response.StatusCode, body, contentType);
    }
}
