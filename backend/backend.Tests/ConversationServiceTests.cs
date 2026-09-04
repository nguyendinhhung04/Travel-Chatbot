using Backend.Conversations;
using MongoDB.Bson;

namespace Backend.Tests;

public sealed class ConversationServiceTests
{
    [Fact]
    public void NestedTurnRequestMapsToDomainTurn()
    {
        var request = new ConversationTurnRequest(
            "11111111-1111-1111-1111-111111111111",
            new ConversationMessageRequest("User question"),
            new ConversationMessageRequest(
                "Assistant answer",
                [new ConversationSourceDocument { Type = "mapbox", Title = "Map", Source = "mapbox", Attribution = "Mapbox" }]));

        var turn = request.ToDomain();

        Assert.Equal(request.TurnId, turn.TurnId);
        Assert.Equal("User question", turn.UserContent);
        Assert.Equal("Assistant answer", turn.AssistantContent);
        Assert.Single(turn.Sources!);
    }

    [Fact]
    public async Task CreateWithFirstTurn_PersistsTwoMessagesAndRichAssistantData()
    {
        var repository = new StubConversationRepository();
        var service = new ConversationService(repository);
        var turn = new ConversationTurnInput(
            Guid.NewGuid().ToString(), "Đi Đà Lạt nên đi đâu?", "Bạn có thể ghé hồ Xuân Hương.",
            [new ConversationSourceDocument { Type = "rag", Title = "Guide", Source = "guide.md" }]);

        var result = await service.CreateWithFirstTurnAsync(
            ObjectId.GenerateNewId().ToString(), turn, CancellationToken.None);

        Assert.True(result.Success);
        Assert.Equal(201, result.StatusCode);
        Assert.Equal(2, repository.Messages.Count);
        Assert.Equal("assistant", repository.Messages[1].Role);
        Assert.Single(repository.Messages[1].Sources);
    }

    [Fact]
    public async Task AppendTurn_UsesNextTurnIndexAndReturnsConflict()
    {
        var userId = ObjectId.GenerateNewId().ToString();
        var conversation = CreateConversation(userId, 1);
        var repository = new StubConversationRepository { Conversation = conversation };
        var service = new ConversationService(repository);

        var result = await service.AppendTurnAsync(
            userId, conversation.Id,
            new ConversationTurnInput(Guid.NewGuid().ToString(), "Tiếp theo?", "Đi chợ Đà Lạt."),
            CancellationToken.None);

        Assert.True(result.Success);
        Assert.Equal(2, repository.LastUpdated!.LastTurnIndex);
        Assert.All(repository.LastMessages!, message => Assert.Equal(2, message.TurnIndex));

        repository.ForceConflict = true;
        var conflict = await service.AppendTurnAsync(
            userId, conversation.Id,
            new ConversationTurnInput(Guid.NewGuid().ToString(), "Còn gì nữa?", "Có thể đi ga Đà Lạt."),
            CancellationToken.None);
        Assert.Equal("version_conflict", conflict.ErrorCode);
        Assert.Equal(409, conflict.StatusCode);
    }

    [Fact]
    public async Task Get_WithDifferentUserReturnsNotFound()
    {
        var owner = ObjectId.GenerateNewId().ToString();
        var repository = new StubConversationRepository { Conversation = CreateConversation(owner, 0) };
        var service = new ConversationService(repository);

        var result = await service.GetAsync(
            ObjectId.GenerateNewId().ToString(), repository.Conversation!.Id, CancellationToken.None);

        Assert.Equal("not_found", result.ErrorCode);
        Assert.Equal(404, result.StatusCode);
    }

    [Fact]
    public async Task Get_OrdersUserBeforeAssistantWhenStoredTurnIsReversed()
    {
        var userId = ObjectId.GenerateNewId().ToString();
        var conversation = CreateConversation(userId, 1);
        var createdAt = DateTime.UtcNow;
        var repository = new StubConversationRepository { Conversation = conversation };
        repository.Messages.AddRange(
        [
            CreateMessage(conversation, "assistant", "Answer", createdAt),
            CreateMessage(conversation, "user", "Question", createdAt)
        ]);
        var service = new ConversationService(repository);

        var result = await service.GetAsync(userId, conversation.Id, CancellationToken.None);

        Assert.True(result.Success);
        Assert.Equal(["user", "assistant"], result.Data!.Messages.Select(message => message.Role));
        Assert.Equal(["Question", "Answer"], result.Data.Messages.Select(message => message.Content));
    }

    private static ConversationDocument CreateConversation(string userId, int lastTurnIndex) => new()
    {
        Id = ObjectId.GenerateNewId().ToString(), UserId = userId, Title = "Đà Lạt",
        LastTurnIndex = lastTurnIndex, CreatedAt = DateTime.UtcNow, UpdatedAt = DateTime.UtcNow
    };

    private static MessageDocument CreateMessage(
        ConversationDocument conversation,
        string role,
        string content,
        DateTime createdAt) => new()
    {
        Id = ObjectId.GenerateNewId().ToString(),
        ConversationId = conversation.Id,
        UserId = conversation.UserId,
        TurnId = "11111111-1111-1111-1111-111111111111",
        TurnIndex = 1,
        Role = role,
        Content = content,
        CreatedAt = createdAt
    };

    private sealed class StubConversationRepository : IConversationRepository
    {
        public ConversationDocument? Conversation { get; set; }
        public List<MessageDocument> Messages { get; } = [];
        public ConversationDocument? LastUpdated { get; private set; }
        public IReadOnlyList<MessageDocument>? LastMessages { get; private set; }
        public bool ForceConflict { get; set; }

        public Task<ConversationDocument> CreateAsync(ConversationDocument conversation, CancellationToken _) =>
            Task.FromResult(conversation);

        public Task<ConversationDocument?> GetAsync(string userId, string conversationId, CancellationToken _) =>
            Task.FromResult(Conversation?.UserId == userId && Conversation.Id == conversationId ? Conversation : null);

        public Task<IReadOnlyList<ConversationDocument>> ListAsync(string userId, CancellationToken _) =>
            Task.FromResult<IReadOnlyList<ConversationDocument>>(
                Conversation?.UserId == userId ? [Conversation] : []);

        public Task<bool> DeleteAsync(string userId, string conversationId, CancellationToken _) =>
            Task.FromResult(Conversation?.UserId == userId && Conversation.Id == conversationId);

        public Task<ConversationWriteResult> CreateWithTurnAsync(
            ConversationDocument conversation, IReadOnlyList<MessageDocument> messages, CancellationToken _)
        {
            Conversation = conversation;
            Messages.AddRange(messages);
            return Task.FromResult(new ConversationWriteResult(ConversationWriteStatus.Created, conversation));
        }

        public Task<ConversationWriteResult> AppendTurnAsync(
            string userId, string conversationId, ConversationDocument updatedConversation,
            IReadOnlyList<MessageDocument> messages, CancellationToken _)
        {
            if (ForceConflict) return Task.FromResult(new ConversationWriteResult(ConversationWriteStatus.Conflict));
            LastUpdated = updatedConversation;
            LastMessages = messages;
            Conversation = updatedConversation;
            Messages.AddRange(messages);
            return Task.FromResult(new ConversationWriteResult(ConversationWriteStatus.Appended, updatedConversation));
        }

        public Task<IReadOnlyList<MessageDocument>> GetMessagesAsync(string userId, string conversationId, CancellationToken _) =>
            Task.FromResult<IReadOnlyList<MessageDocument>>(Messages);
    }
}
