using Backend.Auth;
using Backend.Users;
using Microsoft.AspNetCore.Identity;
using Microsoft.Extensions.Options;

namespace Backend.Tests;

public sealed class AuthServiceTests
{
    private static readonly JwtOptions JwtOptions = new()
    {
        Issuer = "TravelChatbot",
        Audience = "TravelChatbot.Tests",
        SigningKey = "test-signing-key-that-is-at-least-32-chars",
        ExpiryMinutes = 60
    };

    [Fact]
    public async Task Register_CreatesNormalizedEmailAndHashesPassword()
    {
        var repository = new StubUserRepository();
        var service = CreateService(repository);

        var result = await service.RegisterAsync(
            new RegisterRequest(" User@Example.com ", "password123", "Nguyễn Văn A"),
            CancellationToken.None);

        Assert.True(result.Success);
        Assert.Equal(201, result.StatusCode);
        Assert.NotNull(repository.Inserted);
        Assert.Equal("user@example.com", repository.Inserted!.Email);
        Assert.Equal("USER@EXAMPLE.COM", repository.Inserted.NormalizedEmail);
        Assert.NotEqual("password123", repository.Inserted.PasswordHash);
    }

    [Fact]
    public async Task Register_RejectsDuplicateEmail()
    {
        var repository = new StubUserRepository { Existing = CreateUser() };
        var service = CreateService(repository);

        var result = await service.RegisterAsync(
            new RegisterRequest("USER@example.com", "password123", "Nguyễn Văn A"),
            CancellationToken.None);

        Assert.False(result.Success);
        Assert.Equal("email_exists", result.ErrorCode);
        Assert.Equal(409, result.StatusCode);
        Assert.Null(repository.Inserted);
    }

    [Fact]
    public async Task Login_WithCorrectPasswordReturnsJwt()
    {
        var hasher = new PasswordHasher<UserDocument>();
        var user = CreateUser();
        user = user.WithPasswordHash(hasher.HashPassword(user, "password123"));
        var service = CreateService(new StubUserRepository { Existing = user });

        var result = await service.LoginAsync(
            new LoginRequest("user@example.com", "password123"),
            CancellationToken.None);

        Assert.True(result.Success);
        Assert.False(string.IsNullOrWhiteSpace(result.AccessToken));
        Assert.Equal(user.Id, result.User!.Id);
    }

    [Fact]
    public async Task Login_WithWrongPasswordReturnsUnauthorized()
    {
        var hasher = new PasswordHasher<UserDocument>();
        var user = CreateUser();
        user = user.WithPasswordHash(hasher.HashPassword(user, "password123"));
        var service = CreateService(new StubUserRepository { Existing = user });

        var result = await service.LoginAsync(
            new LoginRequest("user@example.com", "wrong-password"),
            CancellationToken.None);

        Assert.False(result.Success);
        Assert.Equal("invalid_credentials", result.ErrorCode);
        Assert.Equal(401, result.StatusCode);
    }

    private static AuthService CreateService(StubUserRepository repository) =>
        new(repository, new PasswordHasher<UserDocument>(), Options.Create(JwtOptions));

    private static UserDocument CreateUser() => new()
    {
        Id = "507f1f77bcf86cd799439011",
        Email = "user@example.com",
        NormalizedEmail = "USER@EXAMPLE.COM",
        DisplayName = "Nguyễn Văn A",
        PasswordHash = "",
        CreatedAt = DateTime.UtcNow
    };

    private sealed class StubUserRepository : IUserRepository
    {
        public UserDocument? Existing { get; init; }
        public UserDocument? Inserted { get; private set; }

        public Task InsertAsync(UserDocument user, CancellationToken cancellationToken)
        {
            Inserted = user;
            return Task.CompletedTask;
        }

        public Task<UserDocument?> FindByNormalizedEmailAsync(
            string normalizedEmail,
            CancellationToken cancellationToken) =>
            Task.FromResult(
                Existing?.NormalizedEmail == normalizedEmail ? Existing : null);

        public Task<UserDocument?> FindByIdAsync(
            string id,
            CancellationToken cancellationToken) =>
            Task.FromResult(Existing?.Id == id ? Existing : null);
    }
}

file static class UserDocumentTestExtensions
{
    public static UserDocument WithPasswordHash(this UserDocument user, string passwordHash) =>
        new()
        {
            Id = user.Id,
            Email = user.Email,
            NormalizedEmail = user.NormalizedEmail,
            DisplayName = user.DisplayName,
            PasswordHash = passwordHash,
            CreatedAt = user.CreatedAt
        };
}
