using System.Text.Json.Serialization;
using Backend.Users;

namespace Backend.Auth;

public sealed record RegisterRequest(
    [property: JsonPropertyName("email")] string Email,
    [property: JsonPropertyName("password")] string Password,
    [property: JsonPropertyName("displayName")] string DisplayName);

public sealed record LoginRequest(
    [property: JsonPropertyName("email")] string Email,
    [property: JsonPropertyName("password")] string Password);

public sealed record UserResponse(
    [property: JsonPropertyName("id")] string Id,
    [property: JsonPropertyName("email")] string Email,
    [property: JsonPropertyName("displayName")] string DisplayName,
    [property: JsonPropertyName("createdAt")] DateTime CreatedAt);

public sealed record LoginResponse(
    [property: JsonPropertyName("accessToken")] string AccessToken,
    [property: JsonPropertyName("user")] UserResponse User);

public sealed record AuthOperationResult(
    UserResponse? User = null,
    string? AccessToken = null,
    string? ErrorCode = null,
    string? ErrorMessage = null,
    int StatusCode = StatusCodes.Status200OK)
{
    public bool Success => ErrorCode is null;

    public static AuthOperationResult Failed(string code, string message, int statusCode) =>
        new(null, null, code, message, statusCode);

    public static UserResponse ToResponse(UserDocument user) =>
        new(user.Id, user.Email, user.DisplayName, user.CreatedAt);
}

public sealed record AuthErrorResponse(
    [property: JsonPropertyName("errorCode")] string ErrorCode,
    [property: JsonPropertyName("error")] string Error);
