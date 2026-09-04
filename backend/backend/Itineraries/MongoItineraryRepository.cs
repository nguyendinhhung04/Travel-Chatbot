using Microsoft.Extensions.Options;
using MongoDB.Driver;

namespace Backend.Itineraries;

public sealed class MongoItineraryRepository : IItineraryRepository
{
    private readonly IMongoCollection<ItineraryDocument> _collection;
    private readonly MongoDbIndexes _indexes;

    public MongoItineraryRepository(
        IMongoDatabase database,
        MongoDbIndexes indexes,
        IOptions<MongoDbOptions> options)
    {
        var value = options.Value;
        _collection = database.GetCollection<ItineraryDocument>(value.ItinerariesCollection);
        _indexes = indexes;
    }

    public async Task InsertAsync(
        ItineraryDocument itinerary,
        CancellationToken cancellationToken)
    {
        await _indexes.EnsureAsync(cancellationToken);
        await _collection.InsertOneAsync(itinerary, cancellationToken: cancellationToken);
    }

    public async Task<ItineraryDocument?> GetAsync(
        string userId,
        string id,
        CancellationToken cancellationToken)
    {
        await _indexes.EnsureAsync(cancellationToken);
        return await _collection.Find(item => item.UserId == userId && item.Id == id)
            .FirstOrDefaultAsync(cancellationToken);
    }

    public async Task<ItineraryDocument?> GetLatestAsync(
        string userId,
        CancellationToken cancellationToken)
    {
        await _indexes.EnsureAsync(cancellationToken);
        return await _collection.Find(item => item.UserId == userId)
            .SortByDescending(item => item.UpdatedAt)
            .FirstOrDefaultAsync(cancellationToken);
    }

    public async Task<bool> ReplaceAsync(
        ItineraryDocument itinerary,
        int expectedVersion,
        CancellationToken cancellationToken)
    {
        await _indexes.EnsureAsync(cancellationToken);
        var result = await _collection.ReplaceOneAsync(
            item => item.UserId == itinerary.UserId
                    && item.Id == itinerary.Id
                    && item.Version == expectedVersion,
            itinerary,
            cancellationToken: cancellationToken);
        return result.ModifiedCount == 1;
    }
}
