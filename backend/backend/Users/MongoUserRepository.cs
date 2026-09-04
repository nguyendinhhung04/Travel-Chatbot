using Backend.Itineraries;
using Microsoft.Extensions.Options;
using MongoDB.Driver;

namespace Backend.Users;

public sealed class MongoUserRepository(
    IMongoDatabase database,
    MongoDbIndexes indexes,
    IOptions<MongoDbOptions> options) : IUserRepository
{
    private readonly IMongoCollection<UserDocument> _collection =
        database.GetCollection<UserDocument>(options.Value.UsersCollection);

    public async Task InsertAsync(UserDocument user, CancellationToken cancellationToken)
    {
        await indexes.EnsureAsync(cancellationToken);
        await _collection.InsertOneAsync(user, cancellationToken: cancellationToken);
    }

    public async Task<UserDocument?> FindByNormalizedEmailAsync(
        string normalizedEmail,
        CancellationToken cancellationToken)
    {
        await indexes.EnsureAsync(cancellationToken);
        return await _collection
            .Find(user => user.NormalizedEmail == normalizedEmail)
            .FirstOrDefaultAsync(cancellationToken);
    }

    public async Task<UserDocument?> FindByIdAsync(
        string id,
        CancellationToken cancellationToken)
    {
        await indexes.EnsureAsync(cancellationToken);
        return await _collection
            .Find(user => user.Id == id)
            .FirstOrDefaultAsync(cancellationToken);
    }
}
