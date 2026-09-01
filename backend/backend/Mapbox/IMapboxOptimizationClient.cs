namespace Backend.Mapbox;

public interface IMapboxOptimizationClient
{
    Task<MapboxRawResponse> OptimizeAsync(
        string profile,
        IReadOnlyList<(double Longitude, double Latitude)> coordinates,
        CancellationToken cancellationToken);
}
