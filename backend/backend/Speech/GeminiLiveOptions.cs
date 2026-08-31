using System.ComponentModel.DataAnnotations;

namespace Backend.Speech;

public sealed class GeminiLiveOptions
{
    public const string SectionName = "GeminiLive";

    [Required]
    public string ApiKey { get; set; } = string.Empty;

    public string BaseUrl { get; set; } = "https://generativelanguage.googleapis.com/";

    public string Model { get; set; } = "gemini-3.5-transcribe-live";
}
