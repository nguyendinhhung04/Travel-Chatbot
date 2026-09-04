using Backend.Chatbot.Tools.Mapbox;
using Backend.Auth;
using Backend.Conversations;
using Backend.Itineraries;
using Backend.Mapbox;
using Backend.Speech;
using Backend.Users;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.AspNetCore.Identity;
using Microsoft.IdentityModel.Tokens;
using System.Text;
using MongoDB.Driver;
using Microsoft.OpenApi;
using Microsoft.Extensions.Options;

var builder = WebApplication.CreateBuilder(args);

builder.Logging.AddFilter("System.Net.Http.HttpClient", LogLevel.Warning);

builder.Services.AddControllers();
builder.Services
    .AddOptions<JwtOptions>()
    .Bind(builder.Configuration.GetSection(JwtOptions.SectionName))
    .ValidateDataAnnotations()
    .Validate(
        options => !string.IsNullOrWhiteSpace(options.SigningKey),
        "Jwt:SigningKey là cấu hình bắt buộc.")
    .ValidateOnStart();
builder.Services.AddSingleton<IPasswordHasher<UserDocument>, PasswordHasher<UserDocument>>();
builder.Services.AddAuthorization();
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

builder.Services
    .AddOptions<GeminiLiveOptions>()
    .Bind(builder.Configuration.GetSection(GeminiLiveOptions.SectionName))
    .ValidateDataAnnotations()
    .Validate(
        options => Uri.TryCreate(options.BaseUrl, UriKind.Absolute, out var uri)
                   && uri.Scheme == Uri.UriSchemeHttps,
        "GeminiLive:BaseUrl phải là một HTTPS URL hợp lệ.")
    .Validate(
        options => !string.IsNullOrWhiteSpace(options.Model),
        "GeminiLive:Model là cấu hình bắt buộc.")
    .ValidateOnStart();

builder.Services.AddHttpClient<IMapboxClient, MapboxClient>((services, client) =>
{
    var options = services.GetRequiredService<IOptions<MapboxOptions>>().Value;
    client.BaseAddress = new Uri($"{options.BaseUrl.TrimEnd('/')}/", UriKind.Absolute);
    client.Timeout = TimeSpan.FromSeconds(options.TimeoutSeconds);
    client.DefaultRequestHeaders.Accept.ParseAdd("application/geo+json, application/json");
});

builder.Services.AddHttpClient<IMapboxOptimizationClient, MapboxOptimizationClient>(
    (services, client) =>
    {
        var options = services.GetRequiredService<IOptions<MapboxOptions>>().Value;
        client.BaseAddress = new Uri($"{options.BaseUrl.TrimEnd('/')}/", UriKind.Absolute);
        client.Timeout = TimeSpan.FromSeconds(options.TimeoutSeconds);
        client.DefaultRequestHeaders.Accept.ParseAdd("application/json");
    });

builder.Services.AddHttpClient<IGeminiEphemeralTokenClient, GeminiEphemeralTokenClient>(
    (services, client) =>
    {
        var options = services.GetRequiredService<IOptions<GeminiLiveOptions>>().Value;
        client.BaseAddress = new Uri($"{options.BaseUrl.TrimEnd('/')}/", UriKind.Absolute);
        client.Timeout = TimeSpan.FromSeconds(10);
        client.DefaultRequestHeaders.Accept.ParseAdd("application/json");
    });

builder.Services
    .AddOptions<MongoDbOptions>()
    .Bind(builder.Configuration.GetSection(MongoDbOptions.SectionName))
    .ValidateDataAnnotations();

var configuredMongo = builder.Configuration
    .GetSection(MongoDbOptions.SectionName)
    .Get<MongoDbOptions>();
if (!string.IsNullOrWhiteSpace(configuredMongo?.ConnectionString))
{
    builder.Services.AddSingleton<IMongoClient>(services =>
    {
        var options = services.GetRequiredService<IOptions<MongoDbOptions>>().Value;
        var settings = MongoClientSettings.FromConnectionString(options.ConnectionString);
        settings.ServerApi = new ServerApi(ServerApiVersion.V1);
        return new MongoClient(settings);
    });
    builder.Services.AddSingleton<IMongoDatabase>(services =>
    {
        var options = services.GetRequiredService<IOptions<MongoDbOptions>>().Value;
        return services
            .GetRequiredService<IMongoClient>()
            .GetDatabase(options.DatabaseName);
    });
    builder.Services.AddSingleton<MongoDbIndexes>();
}

builder.Services.AddSingleton<IUserRepository>(services =>
{
    var options = services.GetRequiredService<IOptions<MongoDbOptions>>().Value;
    if (string.IsNullOrWhiteSpace(options.ConnectionString))
    {
        return new UnavailableUserRepository();
    }
    return new MongoUserRepository(
        services.GetRequiredService<IMongoDatabase>(),
        services.GetRequiredService<MongoDbIndexes>(),
        Options.Create(options));
});
builder.Services.AddSingleton<IConversationRepository>(services =>
{
    var options = services.GetRequiredService<IOptions<MongoDbOptions>>().Value;
    if (string.IsNullOrWhiteSpace(options.ConnectionString))
    {
        return new UnavailableConversationRepository();
    }
    return new MongoConversationRepository(
        services.GetRequiredService<IMongoClient>(),
        services.GetRequiredService<IMongoDatabase>(),
        services.GetRequiredService<MongoDbIndexes>(),
        Options.Create(options));
});
builder.Services.AddScoped<AuthService>();
builder.Services.AddScoped<ConversationService>();
builder.Services
    .AddAuthentication(options =>
    {
        options.DefaultAuthenticateScheme = JwtBearerDefaults.AuthenticationScheme;
        options.DefaultChallengeScheme = JwtBearerDefaults.AuthenticationScheme;
    })
    .AddJwtBearer(options =>
    {
        var jwt = builder.Configuration
            .GetSection(JwtOptions.SectionName)
            .Get<JwtOptions>() ?? new JwtOptions();
        options.TokenValidationParameters = new TokenValidationParameters
        {
            ValidateIssuer = true,
            ValidIssuer = jwt.Issuer,
            ValidateAudience = true,
            ValidAudience = jwt.Audience,
            ValidateIssuerSigningKey = true,
            IssuerSigningKey = new SymmetricSecurityKey(Encoding.UTF8.GetBytes(jwt.SigningKey)),
            ValidateLifetime = true,
            ClockSkew = TimeSpan.FromSeconds(30)
        };
    });

builder.Services.AddSingleton<IItineraryRepository>(services =>
{
    var options = services.GetRequiredService<IOptions<MongoDbOptions>>().Value;
    if (string.IsNullOrWhiteSpace(options.ConnectionString))
    {
        return new UnavailableItineraryRepository();
    }
    return new MongoItineraryRepository(
        services.GetRequiredService<IMongoDatabase>(),
        services.GetRequiredService<MongoDbIndexes>(),
        Options.Create(options));
});
builder.Services.AddScoped<ItineraryService>();

builder.Services.AddTransient<MapboxForwardSearchTool>();
builder.Services.AddTransient<MapboxCategorySearchTool>();
builder.Services.AddTransient<MapboxReverseLookupTool>();
builder.Services.AddTransient<MapboxCandidateResolverTool>();
builder.Services.AddTransient<MapboxPlacesDetailsTool>();
builder.Services.AddTransient<MapboxOptimizationTool>();

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

// The HTTP launch profile is intentionally used for local development. In that
// profile there is no HTTPS endpoint to redirect to (and no dev certificate is
// required), so only enforce the redirect outside Development.
if (!app.Environment.IsDevelopment())
{
    app.UseHttpsRedirection();
}

app.UseAuthentication();
app.UseAuthorization();

app.MapControllers();

app.Run();

public partial class Program;
