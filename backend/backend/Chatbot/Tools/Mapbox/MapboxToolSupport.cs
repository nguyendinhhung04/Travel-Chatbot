using System.ComponentModel.DataAnnotations;
using System.Text.Json;
using Backend.Chatbot.Tools;
using Backend.Mapbox;

namespace Backend.Chatbot.Tools.Mapbox;

internal static class MapboxToolSupport
{
    public static string? ValidateInput(object input)
    {
        var validationResults = new List<ValidationResult>();
        var context = new ValidationContext(input);
        if (Validator.TryValidateObject(input, context, validationResults, validateAllProperties: true))
        {
            return null;
        }

        return string.Join(
            " ",
            validationResults
                .Select(result => result.ErrorMessage)
                .Where(message => !string.IsNullOrWhiteSpace(message))
                .Distinct(StringComparer.Ordinal));
    }

    public static async Task<ToolResult<T>> ExecuteAsync<T>(
        Func<CancellationToken, Task<MapboxRawResponse>> request,
        Func<string, T> parse,
        CancellationToken cancellationToken)
        where T : class
    {
        try
        {
            var response = await request(cancellationToken);
            if (!response.IsSuccessStatusCode)
            {
                return ToolResult<T>.Failed(
                    "mapbox_http_error",
                    $"Mapbox API trả về HTTP {response.StatusCode}.");
            }

            return ToolResult<T>.Succeeded(parse(response.Body));
        }
        catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
        {
            return ToolResult<T>.Failed(
                "mapbox_timeout",
                "Mapbox API hết thời gian phản hồi.");
        }
        catch (HttpRequestException)
        {
            return ToolResult<T>.Failed(
                "mapbox_unavailable",
                "Không thể kết nối đến Mapbox API.");
        }
        catch (JsonException)
        {
            return ToolResult<T>.Failed(
                "mapbox_invalid_response",
                "Mapbox API trả về dữ liệu không hợp lệ.");
        }
    }
}
