using MongoDB.Bson;
using MongoDB.Driver;

namespace Backend.Conversations;

public sealed record ConversationOperationResult<T>(
    T? Data = default,
    string? ErrorCode = null,
    string? ErrorMessage = null,
    int StatusCode = StatusCodes.Status200OK)
{
    public bool Success => ErrorCode is null;

    public static ConversationOperationResult<T> Failed(
        string code,
        string message,
        int statusCode) => new(default, code, message, statusCode);
}

public sealed class ConversationService(IConversationRepository repository)
{
    private const int MaxContentLength = 20_000;
    private const int PreviewLength = 200;

    public async Task<ConversationOperationResult<ConversationDocument>> CreateAsync(
        string userId,
        string title,
        CancellationToken cancellationToken)
    {
        if (!IsValidUserId(userId) || string.IsNullOrWhiteSpace(title) || title.Trim().Length > 200)
            return Invalid<ConversationDocument>("userId hoặc title không hợp lệ.");

        var now = DateTime.UtcNow;
        var conversation = new ConversationDocument
        {
            Id = ObjectId.GenerateNewId().ToString(), UserId = userId,
            Title = title.Trim(), LastTurnIndex = 0, CreatedAt = now, UpdatedAt = now
        };
        try
        {
            return new(await repository.CreateAsync(conversation, cancellationToken),
                StatusCode: StatusCodes.Status201Created);
        }
        catch (Exception error) when (IsPersistenceFailure(error))
        {
            return DatabaseFailure<ConversationDocument>();
        }
    }

    public async Task<ConversationOperationResult<ConversationDetails>> CreateWithFirstTurnAsync(
        string userId,
        ConversationTurnInput turn,
        CancellationToken cancellationToken)
    {
        var validationError = ValidateTurn(userId, turn);
        if (validationError is not null)
        {
            return Invalid<ConversationDetails>(validationError);
        }

        var now = DateTime.UtcNow;
        var conversation = new ConversationDocument
        {
            Id = ObjectId.GenerateNewId().ToString(),
            UserId = userId,
            Title = TrimTo(turn.UserContent, 80),
            LastMessagePreview = TrimTo(turn.AssistantContent, PreviewLength),
            LastTurnIndex = 1,
            CreatedAt = now,
            UpdatedAt = now
        };
        var messages = BuildMessages(conversation, turn, 1, now);

        try
        {
            var result = await repository.CreateWithTurnAsync(
                conversation, messages, cancellationToken);
            if (result.Status == ConversationWriteStatus.AlreadyApplied
                && result.Conversation is not null)
            {
                var existingMessages = await repository.GetMessagesAsync(
                    userId, result.Conversation.Id, cancellationToken);
                return new(new ConversationDetails(result.Conversation, OrderMessages(existingMessages)));
            }
            if (result.Status != ConversationWriteStatus.Created)
            {
                return DatabaseFailure<ConversationDetails>();
            }
            return new(new ConversationDetails(conversation, messages),
                StatusCode: StatusCodes.Status201Created);
        }
        catch (Exception error) when (IsPersistenceFailure(error))
        {
            return DatabaseFailure<ConversationDetails>();
        }
    }

    public async Task<ConversationOperationResult<IReadOnlyList<ConversationDocument>>> ListAsync(
        string userId,
        CancellationToken cancellationToken)
    {
        if (!IsValidUserId(userId)) return Invalid<IReadOnlyList<ConversationDocument>>("userId không hợp lệ.");
        try
        {
            return new(await repository.ListAsync(userId, cancellationToken));
        }
        catch (Exception error) when (IsPersistenceFailure(error))
        {
            return DatabaseFailure<IReadOnlyList<ConversationDocument>>();
        }
    }

    public async Task<ConversationOperationResult<ConversationDetails>> GetAsync(
        string userId,
        string conversationId,
        CancellationToken cancellationToken)
    {
        if (!IsValidUserId(userId) || !ObjectId.TryParse(conversationId, out _))
            return NotFound<ConversationDetails>();
        try
        {
            var conversation = await repository.GetAsync(userId, conversationId, cancellationToken);
            if (conversation is null) return NotFound<ConversationDetails>();
            var messages = await repository.GetMessagesAsync(userId, conversationId, cancellationToken);
            return new(new ConversationDetails(conversation, OrderMessages(messages)));
        }
        catch (Exception error) when (IsPersistenceFailure(error))
        {
            return DatabaseFailure<ConversationDetails>();
        }
    }

    public async Task<ConversationOperationResult<bool>> DeleteAsync(
        string userId,
        string conversationId,
        CancellationToken cancellationToken)
    {
        if (!IsValidUserId(userId) || !ObjectId.TryParse(conversationId, out _))
            return NotFound<bool>();
        try
        {
            return await repository.DeleteAsync(userId, conversationId, cancellationToken)
                ? new(true, StatusCode: StatusCodes.Status204NoContent)
                : NotFound<bool>();
        }
        catch (Exception error) when (IsPersistenceFailure(error))
        {
            return DatabaseFailure<bool>();
        }
    }

    public async Task<ConversationOperationResult<ConversationDetails>> AppendTurnAsync(
        string userId,
        string conversationId,
        ConversationTurnInput turn,
        CancellationToken cancellationToken)
    {
        var validationError = ValidateTurn(userId, turn);
        if (validationError is not null || !ObjectId.TryParse(conversationId, out _))
            return Invalid<ConversationDetails>(validationError ?? "conversationId không hợp lệ.");

        try
        {
            var current = await repository.GetAsync(userId, conversationId, cancellationToken);
            if (current is null) return NotFound<ConversationDetails>();

            var now = DateTime.UtcNow;
            var updated = new ConversationDocument
            {
                Id = current.Id,
                UserId = current.UserId,
                Title = current.Title,
                LastMessagePreview = TrimTo(turn.AssistantContent, PreviewLength),
                LastTurnIndex = current.LastTurnIndex + 1,
                CreatedAt = current.CreatedAt,
                UpdatedAt = now
            };
            var messages = BuildMessages(updated, turn, updated.LastTurnIndex, now);
            var result = await repository.AppendTurnAsync(
                userId, conversationId, updated, messages, cancellationToken);

            if (result.Status == ConversationWriteStatus.NotFound) return NotFound<ConversationDetails>();
            if (result.Status == ConversationWriteStatus.Conflict)
                return ConversationOperationResult<ConversationDetails>.Failed(
                    "version_conflict", "Cuộc trò chuyện đã thay đổi, vui lòng tải lại.", StatusCodes.Status409Conflict);

            var saved = result.Conversation ?? updated;
            var savedMessages = await repository.GetMessagesAsync(userId, conversationId, cancellationToken);
            return new(new ConversationDetails(saved, OrderMessages(savedMessages)));
        }
        catch (Exception error) when (IsPersistenceFailure(error))
        {
            return DatabaseFailure<ConversationDetails>();
        }
    }

    private static MessageDocument[] BuildMessages(
        ConversationDocument conversation,
        ConversationTurnInput turn,
        int turnIndex,
        DateTime createdAt) =>
        [
            new MessageDocument
            {
                Id = ObjectId.GenerateNewId().ToString(), ConversationId = conversation.Id,
                UserId = conversation.UserId, TurnId = turn.TurnId, TurnIndex = turnIndex,
                Role = "user", Content = turn.UserContent.Trim(), CreatedAt = createdAt
            },
            new MessageDocument
            {
                Id = ObjectId.GenerateNewId().ToString(), ConversationId = conversation.Id,
                UserId = conversation.UserId, TurnId = turn.TurnId, TurnIndex = turnIndex,
                Role = "assistant", Content = turn.AssistantContent.Trim(),
                Sources = turn.Sources ?? [], Places = turn.Places ?? [], Itinerary = turn.Itinerary,
                CreatedAt = createdAt
            }
        ];

    private static IReadOnlyList<MessageDocument> OrderMessages(
        IEnumerable<MessageDocument> messages) =>
        messages
            .OrderBy(message => message.TurnIndex)
            .ThenBy(message => message.Role switch
            {
                "user" => 0,
                "assistant" => 1,
                _ => 2
            })
            .ThenBy(message => message.CreatedAt)
            .ThenBy(message => message.Id, StringComparer.Ordinal)
            .ToArray();

    private static string? ValidateTurn(string userId, ConversationTurnInput turn)
    {
        if (!IsValidUserId(userId)) return "userId không hợp lệ.";
        if (!Guid.TryParse(turn.TurnId, out var turnId) || turnId == Guid.Empty) return "turnId không hợp lệ.";
        if (string.IsNullOrWhiteSpace(turn.UserContent) || turn.UserContent.Length > MaxContentLength)
            return "User message không được rỗng và không vượt quá 20.000 ký tự.";
        if (string.IsNullOrWhiteSpace(turn.AssistantContent) || turn.AssistantContent.Length > MaxContentLength)
            return "Assistant message không được rỗng và không vượt quá 20.000 ký tự.";
        return null;
    }

    private static bool IsValidUserId(string value) => ObjectId.TryParse(value, out _);

    private static string TrimTo(string value, int max) =>
        value.Trim().Length <= max ? value.Trim() : value.Trim()[..max];

    private static bool IsPersistenceFailure(Exception error) =>
        error is MongoException or ConversationRepositoryUnavailableException;

    private static ConversationOperationResult<T> Invalid<T>(string message) =>
        ConversationOperationResult<T>.Failed("invalid_input", message, StatusCodes.Status422UnprocessableEntity);

    private static ConversationOperationResult<T> NotFound<T>() =>
        ConversationOperationResult<T>.Failed("not_found", "Không tìm thấy cuộc trò chuyện.", StatusCodes.Status404NotFound);

    private static ConversationOperationResult<T> DatabaseFailure<T>() =>
        ConversationOperationResult<T>.Failed("database_unavailable", "Không thể truy cập dữ liệu cuộc trò chuyện.", StatusCodes.Status503ServiceUnavailable);
}
