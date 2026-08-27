namespace Backend.Mapbox;

public interface IMapboxClient
{
    Task<MapboxRawResponse> ForwardSearchAsync(
        MapboxForwardSearchRequest request,
        CancellationToken cancellationToken);

    Task<MapboxRawResponse> SearchCategoryAsync(
        string categoryId,
        MapboxCategorySearchRequest request,
        CancellationToken cancellationToken);

    Task<MapboxRawResponse> ReverseLookupAsync(
        MapboxReverseLookupRequest request,
        CancellationToken cancellationToken);
}
