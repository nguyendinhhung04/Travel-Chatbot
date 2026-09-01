# Mapbox Search API backend

ASP.NET Core backend tách riêng ba vai trò:

- `Mapbox`: chứa `IMapboxClient`, HTTP client, request model và raw response dùng chung.
- `Chatbot/Tools/Mapbox`: chứa các typed tool handler dành cho chatbot.
- `Controllers`: cung cấp HTTP API cho Django chatbot.

Controller gọi các typed chatbot tool; tool gọi `IMapboxClient`, không tự dựng URL và
không nhận Mapbox access token từ người dùng.

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

Ba endpoint forward/category/reverse chỉ trả DTO gọn cho Django và không chứa raw
GeoJSON: Mapbox ID, tên, địa chỉ, tọa độ, category hiển thị, trạng thái hoạt động,
khoảng cách, ETA, rating và attribution. Các field kỹ thuật `featureType`,
`poiCategoryIds`, `popularity` chỉ được giữ trong typed tool nội bộ để matching và
xếp hạng. Endpoint `mapbox-resolve-candidates` vẫn trả contract đầy đủ để không làm
mất evidence của nhánh khám phá điểm đến. Field tùy chọn có giá trị `null` không được
serialize qua HTTP.
Category ID cho chatbot do Semantic Interpretation và category resolver phía Django
chọn từ whitelist; không cần tải Category List trong mỗi lượt hỏi. Response Mapbox
không được cache hoặc lưu lâu dài.

Các mã lỗi tool:

- `invalid_input`
- `mapbox_http_error`
- `mapbox_timeout`
- `mapbox_unavailable`
- `mapbox_invalid_response`

Backend cung cấp các endpoint nội bộ cho Django:

```http
POST /api/chatbot/tools/mapbox-forward-search
POST /api/chatbot/tools/mapbox-category-search
POST /api/chatbot/tools/mapbox-reverse-lookup
POST /api/chatbot/tools/mapbox-resolve-candidates
```

Các endpoint này trả `ToolResult<T>` đã được chuẩn hóa cho Django; access token chỉ nằm
ở backend .NET.

## Cấu hình token

Tại thư mục `backend/backend`, lưu token bằng .NET User Secrets:

```powershell
dotnet user-secrets set "Mapbox:AccessToken" "YOUR_MAPBOX_ACCESS_TOKEN"
```

Hoặc cấu hình biến môi trường `Mapbox__AccessToken`.

Gemini Live cần API key ở .NET User Secrets, không đưa key này vào frontend:

```powershell
dotnet user-secrets set "GeminiLive:ApiKey" "YOUR_GEMINI_API_KEY"
```

Endpoint `POST /api/speech/ephemeral-token` chỉ cấp token ngắn hạn, một lần dùng,
đã khóa cho model `gemini-3.5-transcribe-live`, TEXT-only, SMART `vi-VN` và manual VAD.

## Chạy và kiểm thử

```powershell
dotnet run
```

Trong môi trường Development, Swagger UI được mở tự động tại:

```text
http://localhost:5257/swagger
```

OpenAPI JSON nằm tại `http://localhost:5257/swagger/v1/swagger.json`.

```powershell
dotnet test backend.slnx
```
