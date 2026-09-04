using Microsoft.Extensions.Options;
using MongoDB.Bson;
using MongoDB.Driver;

namespace Backend.Itineraries;

/// <summary>
/// Creates the indexes shared by the MongoDB-backed features.
/// Index creation is lazy to preserve the existing no-Mongo local/test fallback.
/// </summary>
public sealed class MongoDbIndexes(
    IMongoDatabase database,
    IOptions<MongoDbOptions> options)
{
    private readonly SemaphoreSlim _lock = new(1, 1);
    private bool _ready;

    public async Task EnsureAsync(CancellationToken cancellationToken)
    {
        if (_ready)
        {
            return;
        }

        await _lock.WaitAsync(cancellationToken);
        try
        {
            if (_ready)
            {
                return;
            }

            var value = options.Value;
            await CreateUserIndexesAsync(value.UsersCollection, cancellationToken);
            await CreateConversationIndexesAsync(value.ConversationsCollection, cancellationToken);
            await CreateMessageIndexesAsync(value.MessagesCollection, cancellationToken);
            await CreateItineraryIndexesAsync(value.ItinerariesCollection, cancellationToken);
            _ready = true;
        }
        finally
        {
            _lock.Release();
        }
    }

    private async Task CreateUserIndexesAsync(
        string collectionName,
        CancellationToken cancellationToken)
    {
        var collection = database.GetCollection<BsonDocument>(collectionName);
        var keys = Builders<BsonDocument>.IndexKeys.Ascending("normalizedEmail");
        await collection.Indexes.CreateOneAsync(
            new CreateIndexModel<BsonDocument>(
                keys,
                new CreateIndexOptions { Unique = true, Name = "ux_users_normalizedEmail" }),
            cancellationToken: cancellationToken);
    }

    private async Task CreateConversationIndexesAsync(
        string collectionName,
        CancellationToken cancellationToken)
    {
        var collection = database.GetCollection<BsonDocument>(collectionName);
        var keys = Builders<BsonDocument>.IndexKeys
            .Ascending("userId")
            .Descending("updatedAt");
        await collection.Indexes.CreateOneAsync(
            new CreateIndexModel<BsonDocument>(
                keys,
                new CreateIndexOptions { Name = "ix_conversations_userId_updatedAt" }),
            cancellationToken: cancellationToken);
    }

    private async Task CreateMessageIndexesAsync(
        string collectionName,
        CancellationToken cancellationToken)
    {
        var collection = database.GetCollection<BsonDocument>(collectionName);
        var orderKeys = Builders<BsonDocument>.IndexKeys
            .Ascending("conversationId")
            .Ascending("turnIndex")
            .Ascending("createdAt");
        var turnKeys = Builders<BsonDocument>.IndexKeys
            .Ascending("conversationId")
            .Ascending("turnId")
            .Ascending("role");
        var userTurnKeys = Builders<BsonDocument>.IndexKeys
            .Ascending("userId")
            .Ascending("turnId")
            .Ascending("role");

        await collection.Indexes.CreateManyAsync(
            [
                new CreateIndexModel<BsonDocument>(
                    orderKeys,
                    new CreateIndexOptions { Name = "ix_messages_conversation_order" }),
                new CreateIndexModel<BsonDocument>(
                    turnKeys,
                    new CreateIndexOptions { Unique = true, Name = "ux_messages_conversation_turn_role" }),
                new CreateIndexModel<BsonDocument>(
                    userTurnKeys,
                    new CreateIndexOptions { Unique = true, Name = "ux_messages_user_turn_role" })
            ],
            cancellationToken);
    }

    private async Task CreateItineraryIndexesAsync(
        string collectionName,
        CancellationToken cancellationToken)
    {
        var collection = database.GetCollection<BsonDocument>(collectionName);
        var keys = Builders<BsonDocument>.IndexKeys
            .Ascending("userId")
            .Descending("updatedAt");
        await collection.Indexes.CreateOneAsync(
            new CreateIndexModel<BsonDocument>(
                keys,
                new CreateIndexOptions { Name = "ix_itineraries_userId_updatedAt" }),
            cancellationToken: cancellationToken);
    }
}
