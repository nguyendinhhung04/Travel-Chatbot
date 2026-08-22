namespace Backend.Mapbox;

public sealed record MapboxRawResponse(int StatusCode, string Body, string ContentType)
{
    public bool IsSuccessStatusCode => StatusCode is >= 200 and <= 299;
}
