using System.ComponentModel.DataAnnotations;

namespace Backend.Auth;

public sealed class JwtOptions
{
    public const string SectionName = "Jwt";

    [Required]
    public string Issuer { get; init; } = "TravelChatbot";

    [Required]
    public string Audience { get; init; } = "TravelChatbot.Frontend";

    [Required]
    [MinLength(32)]
    public string SigningKey { get; init; } = string.Empty;

    [Range(5, 1440)]
    public int ExpiryMinutes { get; init; } = 60;
}
