using Backend.Itineraries;
using Microsoft.Extensions.Options;
using MongoDB.Driver;

namespace Backend.Conversations;

public sealed class MongoConversationRepository(
    IMongoClient client,
    IMongoDatabase database,
    MongoDbIndexes indexes,
    IOptions<MongoDbOptions> options) : IConversationRepository
{
    private readonly IMongoCollection<ConversationDocument> _conversations =
        database.GetCollection<ConversationDocument>(options.Value.ConversationsCollection);
    private readonly IMongoCollection<MessageDocument> _messages =
        database.GetCollection<MessageDocument>(options.Value.MessagesCollection);

    public async Task<ConversationDocument> CreateAsync(
        ConversationDocument conversation,
        CancellationToken cancellationToken)
    {
        await indexes.EnsureAsync(cancellationToken);
        await _conversations.InsertOneAsync(conversation, cancellationToken: cancellationToken);
        return conversation;
    }

    public async Task<ConversationDocument?> GetAsync(
        string userId,
        string conversationId,
        CancellationToken cancellationToken)
    {
        await indexes.EnsureAsync(cancellationToken);
        return await _conversations
            .Find(item => item.UserId == userId && item.Id == conversationId)
            .FirstOrDefaultAsync(cancellationToken);
    }

    public async Task<IReadOnlyList<ConversationDocument>> ListAsync(
        string userId,
        CancellationToken cancellationToken)
    {
        await indexes.EnsureAsync(cancellationToken);
        return await _conversations
            .Find(item => item.UserId == userId)
            .SortByDescending(item => item.UpdatedAt)
            .ToListAsync(cancellationToken);
    }

    public async Task<bool> DeleteAsync(
        string userId,
        string conversationId,
        CancellationToken cancellationToken)
    {
        await indexes.EnsureAsync(cancellationToken);
        using var session = await client.StartSessionAsync(cancellationToken: cancellationToken);
        session.StartTransaction();
        try
        {
            var conversationResult = await _conversations.DeleteOneAsync(
                session,
                item => item.UserId == userId && item.Id == conversationId,
                cancellationToken: cancellationToken);
            if (conversationResult.DeletedCount == 0)
            {
                await session.AbortTransactionAsync(cancellationToken);
                return false;
            }

            await _messages.DeleteManyAsync(
                session,
                item => item.UserId == userId && item.ConversationId == conversationId,
                cancellationToken: cancellationToken);
            await session.CommitTransactionAsync(cancellationToken);
            return true;
        }
        catch
        {
            await session.AbortTransactionAsync(CancellationToken.None);
            throw;
        }
    }

    public async Task<ConversationWriteResult> CreateWithTurnAsync(
        ConversationDocument conversation,
        IReadOnlyList<MessageDocument> messages,
        CancellationToken cancellationToken)
    {
        await indexes.EnsureAsync(cancellationToken);
        var existingMessage = await _messages
            .Find(item => item.UserId == conversation.UserId
                          && item.TurnId == messages[0].TurnId)
            .FirstOrDefaultAsync(cancellationToken);
        if (existingMessage is not null)
        {
            var existingConversation = await GetAsync(
                conversation.UserId, existingMessage.ConversationId, cancellationToken);
            return new(ConversationWriteStatus.AlreadyApplied, existingConversation);
        }

        using var session = await client.StartSessionAsync(cancellationToken: cancellationToken);
        session.StartTransaction();
        try
        {
            await _conversations.InsertOneAsync(
                session, conversation, cancellationToken: cancellationToken);
            await _messages.InsertManyAsync(
                session, messages, cancellationToken: cancellationToken);
            await session.CommitTransactionAsync(cancellationToken);
            return new(ConversationWriteStatus.Created, conversation);
        }
        catch (MongoWriteException error) when (error.WriteError?.Code == 11000)
        {
            await session.AbortTransactionAsync(CancellationToken.None);
            var duplicateMessage = await _messages
                .Find(item => item.UserId == conversation.UserId
                              && item.TurnId == messages[0].TurnId)
                .FirstOrDefaultAsync(cancellationToken);
            if (duplicateMessage is not null)
            {
                var existingConversation = await GetAsync(
                    conversation.UserId, duplicateMessage.ConversationId, cancellationToken);
                return new(ConversationWriteStatus.AlreadyApplied, existingConversation);
            }
            throw;
        }
        catch
        {
            await session.AbortTransactionAsync(CancellationToken.None);
            throw;
        }
    }

    public async Task<ConversationWriteResult> AppendTurnAsync(
        string userId,
        string conversationId,
        ConversationDocument updatedConversation,
        IReadOnlyList<MessageDocument> messages,
        CancellationToken cancellationToken)
    {
        await indexes.EnsureAsync(cancellationToken);

        var existingMessage = await _messages
            .Find(item => item.UserId == userId
                          && item.ConversationId == conversationId
                          && item.TurnId == messages[0].TurnId)
            .FirstOrDefaultAsync(cancellationToken);
        if (existingMessage is not null)
        {
            var existingConversation = await GetAsync(userId, conversationId, cancellationToken);
            return new(ConversationWriteStatus.AlreadyApplied, existingConversation);
        }

        using var session = await client.StartSessionAsync(cancellationToken: cancellationToken);
        session.StartTransaction();
        try
        {
            var current = await _conversations
                .Find(session, item => item.UserId == userId && item.Id == conversationId)
                .FirstOrDefaultAsync(cancellationToken);
            if (current is null)
            {
                await session.AbortTransactionAsync(cancellationToken);
                return new(ConversationWriteStatus.NotFound);
            }
            if (updatedConversation.LastTurnIndex != current.LastTurnIndex + 1)
            {
                await session.AbortTransactionAsync(cancellationToken);
                return new(ConversationWriteStatus.Conflict, current);
            }

            await _messages.InsertManyAsync(
                session, messages, cancellationToken: cancellationToken);
            var replaceResult = await _conversations.ReplaceOneAsync(
                session,
                item => item.UserId == userId
                        && item.Id == conversationId
                        && item.LastTurnIndex == current.LastTurnIndex,
                updatedConversation,
                cancellationToken: cancellationToken);
            if (replaceResult.ModifiedCount != 1)
            {
                await session.AbortTransactionAsync(cancellationToken);
                return new(ConversationWriteStatus.Conflict, current);
            }

            await session.CommitTransactionAsync(cancellationToken);
            return new(ConversationWriteStatus.Appended, updatedConversation);
        }
        catch
        {
            await session.AbortTransactionAsync(CancellationToken.None);
            throw;
        }
    }

    public async Task<IReadOnlyList<MessageDocument>> GetMessagesAsync(
        string userId,
        string conversationId,
        CancellationToken cancellationToken)
    {
        await indexes.EnsureAsync(cancellationToken);
        return await _messages
            .Find(item => item.UserId == userId && item.ConversationId == conversationId)
            .SortBy(item => item.TurnIndex)
            .ThenByDescending(item => item.Role)
            .ToListAsync(cancellationToken);
    }
}
