# Implementation Plan: Authentication và Conversation History

## 1. Mục tiêu

Triển khai authentication, lưu lịch sử hội thoại và khôi phục đầy đủ trạng thái
chat/map cho Travel Chatbot.

- User phải đăng nhập mới dùng chatbot.
- Conversation và itinerary thuộc user hiện tại.
- MongoDB lưu toàn bộ lịch sử.
- Django tiếp tục stateless.
- Gemini chỉ nhận 3 turn gần nhất, tối đa 6 message.
- Reload hoặc mở lại conversation khôi phục messages, highlight, POI markers và
  itinerary route.

## 2. Kiến trúc và nguyên tắc

- ASP.NET Core phụ trách JWT, user, conversation, itinerary và MongoDB.
- Next.js là BFF: browser chỉ gọi Next API routes và token nằm trong HttpOnly
  cookie.
- Django nhận request chat, xử lý semantic/RAG/Gemini/Mapbox orchestration và
  relay bearer token khi cần gọi ASP.NET.
- Không nhận `userId` từ frontend; ASP.NET lấy user ID từ JWT claim `sub`.
- Không lưu conversation hoặc session trong Django.

## 3. Public API contract

### Authentication

```http
POST /api/auth/register
POST /api/auth/login
GET  /api/auth/me
```

Login trả thông tin user và access token cho Next.js server route. Next.js lưu
token bằng cookie HttpOnly. Logout xóa cookie ở Next.js.

### Conversation

```http
GET    /api/conversations
POST   /api/conversations
GET    /api/conversations/{conversationId}
DELETE /api/conversations/{conversationId}
POST   /api/conversations/{conversationId}/turns
```

Conversation API luôn dùng user ID từ JWT và trả `404` nếu resource thuộc user
khác.

Turn request:

```json
{
  "turnId": "uuid",
  "userMessage": {
    "content": "Đà Nẵng đi đâu?"
  },
  "assistantMessage": {
    "content": "...",
    "sources": [],
    "places": [],
    "itinerary": null
  }
}
```

`POST /api/conversations` dùng cho turn đầu tiên để không tạo conversation
rỗng. Các turn tiếp theo dùng endpoint `/turns`.

### User-scoped itinerary

Đổi route owner cố định `admin` thành:

```http
POST /api/itineraries
GET  /api/itineraries/latest
GET  /api/itineraries/{id}
POST /api/itineraries/{id}/stops
```

Django forward bearer token khi gọi các endpoint này. Các document cũ có
`userId: "admin"` không tự động gán cho user mới; chỉ mở lại sau migration có
owner xác định.

## 4. Các bước triển khai

### Bước 1 — Shared MongoDB infrastructure

- Mở rộng `MongoDbOptions` cho users, conversations và messages.
- Đăng ký một `MongoClient` singleton và một `IMongoDatabase`.
- Refactor itinerary repository dùng infrastructure chung.
- Tạo indexes cho email, conversation ownership, message ordering và itinerary
  ownership.
- Bật MongoDB transaction cho thao tác lưu một turn.

### Bước 2 — User model và JWT authentication

- Tạo `UserDocument`, user repository và auth service.
- Chuẩn hóa email và tạo unique index.
- Hash password bằng ASP.NET password hasher.
- Cấu hình JWT issuer, audience, signing key và expiry bằng User Secrets hoặc
  environment variables.
- Thêm `AddAuthentication().AddJwtBearer()` và `UseAuthentication()`.
- Tạo register, login và `/me`.
- Bắt lỗi duplicate email thành `409`; dữ liệu sai trả lỗi validation phù hợp.

### Bước 3 — Bảo vệ ASP.NET và relay identity

- Thêm `[Authorize]` cho conversation, itinerary và các tool endpoint do Django
  gọi.
- Next.js kiểm tra cookie cho `/api/chat`, `/api/conversations/*`,
  `/api/itineraries` và `/api/speech-token`.
- `/api/chat` forward bearer token tới Django.
- Django truyền token tiếp tục tới ASP.NET, không lưu token hoặc tạo session.
- Cập nhật typed Django client và các test HTTP boundary.

### Bước 4 — Conversation domain

- Tạo `ConversationDocument`, `MessageDocument`, repository và service.
- `MessageDocument` gồm `turnId`, `turnIndex`, role, content, sources, places,
  itinerary snapshot và `createdAt`.
- `places` phải lưu tối thiểu `mapboxId`, name và tọa độ; giữ metadata hiện có
  để render card sau reload.
- Lưu user message, assistant message và metadata conversation trong transaction.
- Dùng `turnId` để retry không tạo duplicate.
- Sắp xếp messages theo `turnIndex`, không chỉ theo timestamp.

### Bước 5 — User-scoped itinerary

- Sửa `ItineraryService` không còn dùng `DefaultUserId = "admin"`.
- Mọi create/get/update/add-stop đều lấy user ID từ claims.
- Cập nhật repository query theo `userId + itineraryId`.
- Cập nhật Django itinerary paths và frontend proxy.
- Tạo migration/handling rõ ràng cho document legacy `admin`.

### Bước 6 — Next.js authentication và route protection

- Tạo `/login`, `/register` và `/chat`.
- Tạo auth API proxy, cookie HttpOnly, logout và auth user state.
- Route `/chat` gọi `/api/auth/me`; chưa đăng nhập redirect `/login`.
- Root `/` redirect hoặc liên kết tới `/chat` để giữ compatibility.
- Không lưu JWT hoặc message content trong localStorage.
- Chỉ có thể lưu `activeConversationId` nếu cần khôi phục tab hiện tại.

### Bước 7 — Frontend conversation state

Đưa các state sau lên `TravelWorkspace`:

```text
activeConversationId
messages
places
itinerary
```

- `ChatWindow` nhận messages qua props và không tự quản lý persistence.
- Thêm `replacePlaces()` bên cạnh logic `addPlaces()`.
- Khi đổi conversation, clear messages, places, itinerary, active marker,
  focus request và GPS state.
- Dùng AbortController hoặc request ID để response cũ không ghi đè chat mới.

### Bước 8 — Lưu và khôi phục turn

- Chat mới gọi Django trước; chỉ khi có response thành công mới tạo conversation
  và lưu turn đầu tiên.
- Chat đang mở lưu bằng `/turns` sau khi nhận assistant response.
- Nếu save thất bại, hiển thị retry và không đánh dấu turn đã persisted.
- Assistant message lưu `sources`, `places` và itinerary snapshot.
- Khi mở conversation, fetch toàn bộ messages, gom places và lấy itinerary
  snapshot mới nhất.
- Restore map bằng dữ liệu đã lưu; không gọi lại Gemini hoặc Mapbox.

### Bước 9 — Tách UI history và LLM context

- Frontend giữ toàn bộ messages để hiển thị.
- Không dùng `trimMessages()` để cắt state UI.
- Tạo helper riêng để lấy 3 turn hoàn chỉnh gần nhất.
- Request sang Django chỉ gồm `role` và `content` của tối đa 6 message.
- Không gửi ID, sources, tọa độ GPS hoặc itinerary vào LLM history.
- Giữ validation history hiện tại ở cả Next.js và Django.

### Bước 10 — Kiểm thử và rollout

Backend tests:

- Register, duplicate email, login đúng/sai, `/me`, token thiếu/hỏng.
- Conversation create/list/load/delete/append.
- Ownership isolation giữa hai user.
- Itinerary ownership và legacy `admin` handling.
- Transaction và idempotent retry của turn.

Frontend mocked Edge E2E:

- Login/register/logout và redirect khi chưa đăng nhập.
- Tạo, mở, xóa conversation.
- Reload giữ messages, highlight, POI markers và itinerary route.
- New Chat clear state.
- Năm turn nhưng request tiếp theo chỉ gửi Q3-A3, Q4-A4, Q5-A5.
- Cập nhật các test GPS, speech và itinerary để login trước khi chạy.

E2E mock Gemini, Mapbox và ASP.NET ở HTTP boundary. Live provider validation
phải báo cáo riêng.

## 5. Definition of Done

- User phải đăng nhập mới truy cập chat và dữ liệu cá nhân.
- User không đọc, sửa hoặc xóa conversation/itinerary của user khác.
- Conversation lưu toàn bộ messages trong MongoDB.
- Reload và mở lại conversation khôi phục đúng chat, highlight, markers và route.
- Frontend hiển thị toàn bộ history nhưng Gemini chỉ nhận 3 turn gần nhất.
- Django vẫn stateless.
- Không còn phụ thuộc `travel_chat_messages`.
- Unit, integration, lint, build và mocked Microsoft Edge E2E đều đạt.
