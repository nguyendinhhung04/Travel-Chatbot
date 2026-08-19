using System.Net;
using System.Text;
using Backend.Mapbox;
using Microsoft.Extensions.Options;

namespace Backend.Tests;

public sealed class MapboxClientTests
{
    [Fact]
    public async Task ForwardSearchAsync_EncodesQueryAndAddsOnlyServerToken()
    {
        var handler = new RecordingHandler(new HttpResponseMessage(HttpStatusCode.OK)
        {
            Content = new StringContent(
                "{\"type\":\"FeatureCollection\",\"features\":[]}",
                Encoding.UTF8,
                "application/geo+json")
        });
        var httpClient = new HttpClient(handler)
        {
            BaseAddress = new Uri("https://api.mapbox.com/")
        };
        var client = new MapboxClient(
            httpClient,
            Options.Create(new MapboxOptions { AccessToken = "server-token" }));

        var response = await client.ForwardSearchAsync(
            new MapboxForwardSearchRequest
            {
                Query = "quán café",
                Limit = 5,
                AutoComplete = false
            },
            CancellationToken.None);

        Assert.Equal(200, response.StatusCode);
        Assert.Contains("FeatureCollection", response.Body);
        Assert.NotNull(handler.RequestUri);
        Assert.Equal("/search/searchbox/v1/forward", handler.RequestUri.AbsolutePath);
        Assert.Contains("q=qu%C3%A1n%20caf%C3%A9", handler.RequestUri.Query);
        Assert.Contains("limit=5", handler.RequestUri.Query);
        Assert.Contains("auto_complete=false", handler.RequestUri.Query);
        Assert.Contains("access_token=server-token", handler.RequestUri.Query);
    }

    [Fact]
    public async Task ListCategoriesAsync_ForwardsLanguageAndAddsServerToken()
    {
        var handler = new RecordingHandler(new HttpResponseMessage(HttpStatusCode.OK)
        {
            Content = new StringContent(
                "{\"listItems\":[{\"canonical_id\":\"restaurant\",\"name\":\"Restaurant\"}]}",
                Encoding.UTF8,
                "application/json")
        });
        var httpClient = new HttpClient(handler)
        {
            BaseAddress = new Uri("https://api.mapbox.com/")
        };
        var client = new MapboxClient(
            httpClient,
            Options.Create(new MapboxOptions { AccessToken = "server-token" }));

        var response = await client.ListCategoriesAsync(" en ", CancellationToken.None);

        Assert.Equal(200, response.StatusCode);
        Assert.Contains("restaurant", response.Body);
        Assert.NotNull(handler.RequestUri);
        Assert.Equal("/search/searchbox/v1/list/category", handler.RequestUri.AbsolutePath);
        Assert.Contains("language=en", handler.RequestUri.Query);
        Assert.Contains("access_token=server-token", handler.RequestUri.Query);
    }

    [Fact]
    public async Task SearchCategoryAsync_ForwardsCategoryAndSupportedParameters()
    {
        var handler = new RecordingHandler(new HttpResponseMessage(HttpStatusCode.OK)
        {
            Content = new StringContent(
                "{\"type\":\"FeatureCollection\",\"features\":[]}",
                Encoding.UTF8,
                "application/geo+json")
        });
        var httpClient = new HttpClient(handler)
        {
            BaseAddress = new Uri("https://api.mapbox.com/")
        };
        var client = new MapboxClient(
            httpClient,
            Options.Create(new MapboxOptions { AccessToken = "server-token" }));

        var response = await client.SearchCategoryAsync(
            " food_and_drink ",
            new MapboxCategorySearchRequest
            {
                Language = "en",
                Limit = 25,
                Proximity = "2.2945,48.8584",
                ShowClosedPois = false
            },
            CancellationToken.None);

        Assert.Equal(200, response.StatusCode);
        Assert.NotNull(handler.RequestUri);
        Assert.Equal(
            "/search/searchbox/v1/category/food_and_drink",
            handler.RequestUri.AbsolutePath);
        Assert.Contains("language=en", handler.RequestUri.Query);
        Assert.Contains("limit=25", handler.RequestUri.Query);
        Assert.Contains("proximity=2.2945,48.8584", handler.RequestUri.Query);
        Assert.Contains("show_closed_pois=false", handler.RequestUri.Query);
        Assert.Contains("access_token=server-token", handler.RequestUri.Query);
    }

    [Fact]
    public async Task ReverseLookupAsync_ForwardsCoordinatesAndSupportedParameters()
    {
        var handler = new RecordingHandler(new HttpResponseMessage(HttpStatusCode.OK)
        {
            Content = new StringContent(
                "{\"type\":\"FeatureCollection\",\"features\":[]}",
                Encoding.UTF8,
                "application/geo+json")
        });
        var httpClient = new HttpClient(handler)
        {
            BaseAddress = new Uri("https://api.mapbox.com/")
        };
        var client = new MapboxClient(
            httpClient,
            Options.Create(new MapboxOptions { AccessToken = "server-token" }));

        var response = await client.ReverseLookupAsync(
            new MapboxReverseLookupRequest
            {
                Longitude = -118.471383,
                Latitude = 34.023653,
                Language = "en",
                Limit = 10,
                Country = "US",
                Types = "address,poi",
                ShowClosedPois = false
            },
            CancellationToken.None);

        Assert.Equal(200, response.StatusCode);
        Assert.NotNull(handler.RequestUri);
        Assert.Equal("/search/searchbox/v1/reverse", handler.RequestUri.AbsolutePath);
        Assert.Contains("longitude=-118.471383", handler.RequestUri.Query);
        Assert.Contains("latitude=34.023653", handler.RequestUri.Query);
        Assert.Contains("language=en", handler.RequestUri.Query);
        Assert.Contains("limit=10", handler.RequestUri.Query);
        Assert.Contains("country=US", handler.RequestUri.Query);
        Assert.Contains("types=address,poi", handler.RequestUri.Query);
        Assert.Contains("show_closed_pois=false", handler.RequestUri.Query);
        Assert.Contains("access_token=server-token", handler.RequestUri.Query);
    }

    private sealed class RecordingHandler(HttpResponseMessage response) : HttpMessageHandler
    {
        public Uri? RequestUri { get; private set; }

        protected override Task<HttpResponseMessage> SendAsync(
            HttpRequestMessage request,
            CancellationToken cancellationToken)
        {
            RequestUri = request.RequestUri;
            return Task.FromResult(response);
        }
    }
}
