namespace Backend.Conversations;

public interface IConversationRepository
{
    Task<ConversationDocument> CreateAsync(
        ConversationDocument conversation,
        CancellationToken cancellationToken);

    Task<ConversationDocument?> GetAsync(
        string userId,
        string conversationId,
        CancellationToken cancellationToken);

    Task<IReadOnlyList<ConversationDocument>> ListAsync(
        string userId,
        CancellationToken cancellationToken);

    Task<bool> DeleteAsync(
        string userId,
        string conversationId,
        CancellationToken cancellationToken);

    Task<ConversationWriteResult> CreateWithTurnAsync(
        ConversationDocument conversation,
        IReadOnlyList<MessageDocument> messages,
        CancellationToken cancellationToken);

    Task<ConversationWriteResult> AppendTurnAsync(
        string userId,
        string conversationId,
        ConversationDocument updatedConversation,
        IReadOnlyList<MessageDocument> messages,
        CancellationToken cancellationToken);

    Task<IReadOnlyList<MessageDocument>> GetMessagesAsync(
        string userId,
        string conversationId,
        CancellationToken cancellationToken);
}

public enum ConversationWriteStatus
{
    Created,
    Appended,
    AlreadyApplied,
    NotFound,
    Conflict
}

public sealed record ConversationWriteResult(
    ConversationWriteStatus Status,
    ConversationDocument? Conversation = null);

public sealed class ConversationRepositoryUnavailableException : Exception
{
    public ConversationRepositoryUnavailableException()
        : base("Conversation persistence is not configured.")
    {
    }
}

public sealed class UnavailableConversationRepository : IConversationRepository
{
    public Task<ConversationDocument> CreateAsync(
        ConversationDocument conversation,
        CancellationToken cancellationToken) => Failed<ConversationDocument>();

    public Task<ConversationDocument?> GetAsync(
        string userId,
        string conversationId,
        CancellationToken cancellationToken) => Failed<ConversationDocument?>();

    public Task<IReadOnlyList<ConversationDocument>> ListAsync(
        string userId,
        CancellationToken cancellationToken) => Failed<IReadOnlyList<ConversationDocument>>();

    public Task<bool> DeleteAsync(
        string userId,
        string conversationId,
        CancellationToken cancellationToken) => Failed<bool>();

    public Task<ConversationWriteResult> CreateWithTurnAsync(
        ConversationDocument conversation,
        IReadOnlyList<MessageDocument> messages,
        CancellationToken cancellationToken) => Failed<ConversationWriteResult>();

    public Task<ConversationWriteResult> AppendTurnAsync(
        string userId,
        string conversationId,
        ConversationDocument updatedConversation,
        IReadOnlyList<MessageDocument> messages,
        CancellationToken cancellationToken) => Failed<ConversationWriteResult>();

    public Task<IReadOnlyList<MessageDocument>> GetMessagesAsync(
        string userId,
        string conversationId,
        CancellationToken cancellationToken) => Failed<IReadOnlyList<MessageDocument>>();

    private static Task<T> Failed<T>() =>
        Task.FromException<T>(new ConversationRepositoryUnavailableException());
}
