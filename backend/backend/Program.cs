using Backend.Chatbot.Tools.Mapbox;
using Backend.Mapbox;
using Microsoft.OpenApi;
using Microsoft.Extensions.Options;

var builder = WebApplication.CreateBuilder(args);

builder.Logging.AddFilter("System.Net.Http.HttpClient", LogLevel.Warning);

builder.Services.AddControllers();
builder.Services.AddSwaggerGen(options =>
{
    options.SwaggerDoc("v1", new OpenApiInfo
    {
        Title = "Travel Chatbot Backend API",
        Version = "v1",
        Description = "Backend API cho Travel Chatbot và Mapbox Search Text."
    });
});

builder.Services
    .AddOptions<MapboxOptions>()
    .Bind(builder.Configuration.GetSection(MapboxOptions.SectionName))
    .ValidateDataAnnotations()
    .Validate(
        options => Uri.TryCreate(options.BaseUrl, UriKind.Absolute, out var uri)
                   && uri.Scheme == Uri.UriSchemeHttps,
        "Mapbox:BaseUrl phải là một HTTPS URL hợp lệ.")
    .Validate(
        options => !string.IsNullOrWhiteSpace(options.AccessToken),
        "Mapbox:AccessToken là cấu hình bắt buộc.")
    .ValidateOnStart();

builder.Services.AddHttpClient<IMapboxClient, MapboxClient>((services, client) =>
{
    var options = services.GetRequiredService<IOptions<MapboxOptions>>().Value;
    client.BaseAddress = new Uri($"{options.BaseUrl.TrimEnd('/')}/", UriKind.Absolute);
    client.Timeout = TimeSpan.FromSeconds(options.TimeoutSeconds);
    client.DefaultRequestHeaders.Accept.ParseAdd("application/geo+json, application/json");
});

builder.Services.AddTransient<MapboxForwardSearchTool>();
builder.Services.AddTransient<MapboxCategorySearchTool>();
builder.Services.AddTransient<MapboxReverseLookupTool>();

var app = builder.Build();

if (app.Environment.IsDevelopment())
{
    app.UseSwagger();
    app.UseSwaggerUI(options =>
    {
        options.SwaggerEndpoint("v1/swagger.json", "Travel Chatbot Backend API v1");
        options.DocumentTitle = "Travel Chatbot Backend API";
    });
}

app.UseHttpsRedirection();

app.UseAuthorization();

app.MapControllers();

app.Run();

public partial class Program;
