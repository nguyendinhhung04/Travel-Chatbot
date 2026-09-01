using Microsoft.Extensions.Options;
using MongoDB.Driver;

namespace Backend.Itineraries;

public sealed class MongoItineraryRepository : IItineraryRepository
{
    private readonly IMongoCollection<ItineraryDocument> _collection;
    private readonly SemaphoreSlim _indexLock = new(1, 1);
    private bool _indexesReady;

    public MongoItineraryRepository(IMongoClient client, IOptions<MongoDbOptions> options)
    {
        var value = options.Value;
        _collection = client
            .GetDatabase(value.DatabaseName)
            .GetCollection<ItineraryDocument>(value.ItinerariesCollection);
    }

    public async Task InsertAsync(
        ItineraryDocument itinerary,
        CancellationToken cancellationToken)
    {
        await EnsureIndexesAsync(cancellationToken);
        await _collection.InsertOneAsync(itinerary, cancellationToken: cancellationToken);
    }

    public async Task<ItineraryDocument?> GetAsync(
        string userId,
        string id,
        CancellationToken cancellationToken)
    {
        await EnsureIndexesAsync(cancellationToken);
        return await _collection.Find(item => item.UserId == userId && item.Id == id)
            .FirstOrDefaultAsync(cancellationToken);
    }

    public async Task<ItineraryDocument?> GetLatestAsync(
        string userId,
        CancellationToken cancellationToken)
    {
        await EnsureIndexesAsync(cancellationToken);
        return await _collection.Find(item => item.UserId == userId)
            .SortByDescending(item => item.UpdatedAt)
            .FirstOrDefaultAsync(cancellationToken);
    }

    public async Task<bool> ReplaceAsync(
        ItineraryDocument itinerary,
        int expectedVersion,
        CancellationToken cancellationToken)
    {
        await EnsureIndexesAsync(cancellationToken);
        var result = await _collection.ReplaceOneAsync(
            item => item.UserId == itinerary.UserId
                    && item.Id == itinerary.Id
                    && item.Version == expectedVersion,
            itinerary,
            cancellationToken: cancellationToken);
        return result.ModifiedCount == 1;
    }

    private async Task EnsureIndexesAsync(CancellationToken cancellationToken)
    {
        if (_indexesReady)
        {
            return;
        }
        await _indexLock.WaitAsync(cancellationToken);
        try
        {
            if (_indexesReady)
            {
                return;
            }
            var keys = Builders<ItineraryDocument>.IndexKeys
                .Ascending(item => item.UserId)
                .Descending(item => item.UpdatedAt);
            await _collection.Indexes.CreateOneAsync(
                new CreateIndexModel<ItineraryDocument>(keys),
                cancellationToken: cancellationToken);
            _indexesReady = true;
        }
        finally
        {
            _indexLock.Release();
        }
    }
}
