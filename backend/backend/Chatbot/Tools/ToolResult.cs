using System.Text.Json.Serialization;

namespace Backend.Chatbot.Tools;

public sealed record ToolResult<T> where T : class
{
    [JsonPropertyName("success")]
    public required bool Success { get; init; }

    [JsonPropertyName("data")]
    public T? Data { get; init; }

    [JsonPropertyName("errorCode")]
    public string? ErrorCode { get; init; }

    [JsonPropertyName("errorMessage")]
    public string? ErrorMessage { get; init; }

    public static ToolResult<T> Succeeded(T data) => new()
    {
        Success = true,
        Data = data
    };

    public static ToolResult<T> Failed(string errorCode, string errorMessage) => new()
    {
        Success = false,
        ErrorCode = errorCode,
        ErrorMessage = errorMessage
    };
}
