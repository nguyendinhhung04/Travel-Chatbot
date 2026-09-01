using System.ComponentModel.DataAnnotations;

namespace Backend.Mapbox;

public sealed class MapboxOptions
{
    public const string SectionName = "Mapbox";

    [Required]
    [Url]
    public string BaseUrl { get; init; } = "https://api.mapbox.com/";

    [Required]
    public string AccessToken { get; init; } = string.Empty;

    [Range(1, 60)]
    public int TimeoutSeconds { get; init; } = 10;
}
