using System.ComponentModel.DataAnnotations;

namespace Backend.Itineraries;

public sealed class MongoDbOptions
{
    public const string SectionName = "MongoDb";

    public string ConnectionString { get; init; } = string.Empty;

    [Required]
    public string DatabaseName { get; init; } = "travel_chatbot";

    [Required]
    public string ItinerariesCollection { get; init; } = "itineraries";
}
