namespace Backend.Itineraries;

public interface IItineraryRepository
{
    Task InsertAsync(
        ItineraryDocument itinerary,
        CancellationToken cancellationToken);

    Task<ItineraryDocument?> GetAsync(
        string userId,
        string id,
        CancellationToken cancellationToken);

    Task<ItineraryDocument?> GetLatestAsync(
        string userId,
        CancellationToken cancellationToken);

    Task<bool> ReplaceAsync(
        ItineraryDocument itinerary,
        int expectedVersion,
        CancellationToken cancellationToken);
}

public sealed class ItineraryRepositoryUnavailableException : Exception
{
    public ItineraryRepositoryUnavailableException()
        : base("Itinerary persistence is not configured.")
    {
    }
}

public sealed class UnavailableItineraryRepository : IItineraryRepository
{
    public Task InsertAsync(
        ItineraryDocument itinerary,
        CancellationToken cancellationToken) => Failed();

    public Task<ItineraryDocument?> GetAsync(
        string userId,
        string id,
        CancellationToken cancellationToken) => Failed<ItineraryDocument?>();

    public Task<ItineraryDocument?> GetLatestAsync(
        string userId,
        CancellationToken cancellationToken) => Failed<ItineraryDocument?>();

    public Task<bool> ReplaceAsync(
        ItineraryDocument itinerary,
        int expectedVersion,
        CancellationToken cancellationToken) => Failed<bool>();

    private static Task<T> Failed<T>() =>
        Task.FromException<T>(new ItineraryRepositoryUnavailableException());

    private static Task Failed() =>
        Task.FromException(new ItineraryRepositoryUnavailableException());
}
