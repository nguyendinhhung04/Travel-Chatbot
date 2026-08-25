# Mapbox Search API backend

ASP.NET Core backend tách riêng ba vai trò:

- `Mapbox`: chứa `IMapboxClient`, HTTP client, request model và raw response dùng chung.
- `Chatbot/Tools/Mapbox`: chứa các typed tool handler dành cho chatbot.
- `Controllers`: cung cấp HTTP API cho frontend và trả nguyên response của Mapbox.

Controller và chatbot tool đều gọi `IMapboxClient`. Tool không gọi vòng qua controller,
không tự dựng URL và không nhận Mapbox access token từ người dùng.

## Chatbot tools

Backend đăng ký bốn Mapbox tool đọc dữ liệu trong dependency injection:

- `mapbox_forward_search`
- `mapbox_category_search`
- `mapbox_reverse_lookup`
- `mapbox_resolve_candidates`: nhận tối đa 5 candidate theo batch, xác minh,
  matching, loại trùng và trả thêm POI theo category.

Các tool hiện là typed C# handler độc lập, chưa kết nối với Gemini, Semantic Kernel hoặc
một AI SDK cụ thể. Mỗi tool trả `ToolResult<T>` gồm `success`, `data`, `errorCode` và
`errorMessage`.

Kết quả typed tool chỉ giữ dữ liệu chatbot cần dùng và không chứa raw GeoJSON:
Mapbox ID, tên, loại địa điểm,
địa chỉ, tọa độ, category, trạng thái hoạt động, khoảng cách, ETA và attribution.
Category ID cho chatbot do Semantic Interpretation và category resolver phía Django
chọn từ whitelist; không cần tải Category List trong mỗi lượt hỏi. Response Mapbox
không được cache hoặc lưu lâu dài.

Các mã lỗi tool:

- `invalid_input`
- `mapbox_http_error`
- `mapbox_timeout`
- `mapbox_unavailable`
- `mapbox_invalid_response`

Backend cung cấp endpoint:

```http
GET /api/mapbox/search?q=Eiffel%20Tower&language=en&limit=5&types=poi
```

Endpoint gọi Mapbox Search Box Text Search `/forward` và trả nguyên GeoJSON. Backend không triển khai
`/suggest` hoặc `/retrieve`, đồng thời không nhận `access_token` từ client.

Danh sách category Mapbox có endpoint riêng:

```http
GET /api/mapbox/categories?language=en
```

Endpoint này gọi Mapbox `/list/category` và trả nguyên danh sách gồm canonical ID, icon và tên category.

Dùng `canonical_id` từ Category List để tìm các POI thuộc category:

```http
GET /api/mapbox/categories/restaurant?language=en&limit=10&proximity=2.2945,48.8584
```

Category Search gọi Mapbox `/category/{canonical_category_id}` và trả nguyên GeoJSON `FeatureCollection`.

Tra cứu địa điểm và POI quanh một tọa độ:

```http
GET /api/mapbox/reverse?longitude=2.2945&latitude=48.8584&language=en&limit=5
```

Reverse Lookup gọi Mapbox `/reverse` và trả nguyên GeoJSON `FeatureCollection`.

## Cấu hình token

Tại thư mục `backend/backend`, lưu token bằng .NET User Secrets:

```powershell
dotnet user-secrets set "Mapbox:AccessToken" "YOUR_MAPBOX_ACCESS_TOKEN"
```

Hoặc cấu hình biến môi trường `Mapbox__AccessToken`.

## Chạy và kiểm thử

```powershell
dotnet run
```

Trong môi trường Development, Swagger UI được mở tự động tại:

```text
http://localhost:5257/swagger
```

OpenAPI JSON nằm tại `http://localhost:5257/swagger/v1/swagger.json`.

Request mẫu đầy đủ hơn nằm trong `backend/backend/backend.http`.

```powershell
dotnet test backend.slnx
```
