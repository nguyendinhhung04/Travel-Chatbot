# Kế hoạch triển khai Frontend Next.js — Chatbot du lịch RAG

## 1. Mục tiêu

Xây dựng frontend chat đơn giản bằng Next.js và TypeScript để người dùng:

- Nhập một câu hỏi về du lịch.
- Gửi câu hỏi đến Django backend.
- Xem câu trả lời của chatbot.
- Xem danh sách nguồn Knowledge Base được sử dụng.
- Nhận thông báo dễ hiểu khi request lỗi.

Đây là dự án học tập cá nhân. Giữ code ngắn, dễ đọc; không thêm Redux, Zustand,
WebSocket, streaming, authentication hoặc thư viện UI lớn.

## 2. Cấu trúc dự án

Frontend là thư mục ngang hàng với backend:

```text
TestChatbot/
├── backend/                 # Django hiện có
└── frontend/                # Next.js cần tạo
```

Khởi tạo frontend bằng `create-next-app` với các lựa chọn:

- TypeScript: Yes
- ESLint: Yes
- Tailwind CSS: Yes
- App Router: Yes
- `src/` directory: Yes
- Import alias: `@/*`

Không cài thêm package nếu Next.js và Tailwind đã đáp ứng được yêu cầu.

## 3. API Django hiện có

Backend chạy tại:

```text
http://127.0.0.1:8000
```

Endpoint:

```http
POST /api/chat/
Content-Type: application/json
```

Request:

```json
{
  "message": "Huế có những hoạt động gì?"
}
```

Response thành công — `200 OK`:

```json
{
  "answer": "Bạn có thể tham quan Đại Nội...",
  "sources": [
    {
      "title": "Hoạt động du lịch tại Huế",
      "source": "destinations/hue/activities.md"
    }
  ]
}
```

Các response lỗi:

- Request thiếu hoặc `message` rỗng: `400 Bad Request`.
- Lỗi Gemini, Embedding hoặc Chroma: `503 Service Unavailable`.

```json
{
  "error": "Chatbot hiện không thể trả lời. Vui lòng thử lại sau."
}
```

Backend hiện chưa có lịch sử hội thoại. Mỗi request chỉ gửi câu hỏi mới nhất;
không gửi lại toàn bộ nội dung chat trước đó.

## 4. Cách kết nối backend

Không gọi trực tiếp Django từ Client Component vì frontend chạy cổng `3000` và
backend chạy cổng `8000`, có thể bị trình duyệt chặn CORS.

Tạo Next.js Route Handler:

```text
src/app/api/chat/route.ts
```

Client gọi endpoint cùng origin:

```text
POST /api/chat
```

Route Handler gọi tiếp Django:

```text
POST ${BACKEND_URL}/api/chat/
```

Tạo `.env.local`:

```env
BACKEND_URL=http://127.0.0.1:8000
```

`BACKEND_URL` chỉ được sử dụng phía server; không đổi thành biến
`NEXT_PUBLIC_BACKEND_URL`.

Route Handler phải:

1. Đọc JSON request và lấy `message`.
2. Kiểm tra `message` là chuỗi không rỗng; nếu sai trả `400`.
3. Gọi Django bằng `fetch`, đặt `Content-Type: application/json` và
   `cache: "no-store"`.
4. Chuyển nguyên status và JSON hợp lệ từ Django về client.
5. Nếu không kết nối được Django, trả `502 Bad Gateway`:

```json
{
  "error": "Không thể kết nối đến máy chủ chatbot."
}
```

Không để lộ stack trace hoặc giá trị `BACKEND_URL` trong response.

## 5. Types

Tạo `src/types/chat.ts`:

```ts
export type ChatSource = {
  title: string;
  source: string;
};

export type ChatSuccessResponse = {
  answer: string;
  sources: ChatSource[];
};

export type ChatErrorResponse = {
  error: string;
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: ChatSource[];
};
```

Dùng `crypto.randomUUID()` để tạo ID phía client. Không cần thư viện UUID.

## 6. Giao diện

Chỉ cần một trang chat tại `/`, responsive cho desktop và mobile:

```text
┌──────────────────────────────────────────┐
│ Trợ lý du lịch                           │
├──────────────────────────────────────────┤
│                                          │
│  Bot: Xin chào, bạn muốn đi đâu?         │
│                         User: ...         │
│  Bot: ...                                │
│  Nguồn:                                  │
│  • Tổng quan du lịch Huế                 │
│                                          │
├──────────────────────────────────────────┤
│ [ Nhập câu hỏi...                 ] [Gửi] │
└──────────────────────────────────────────┘
```

Yêu cầu hành vi:

- Khi chưa có message, hiển thị lời chào và 3 câu hỏi gợi ý về Huế, Đà Nẵng,
  Hội An.
- Click câu hỏi gợi ý sẽ điền vào ô nhập, không tự gửi.
- Tin nhắn user căn phải; tin nhắn assistant căn trái.
- Nguồn hiển thị dưới câu trả lời assistant, loại bỏ nếu `sources` rỗng.
- Hiển thị `title` là nội dung chính và `source` bằng chữ nhỏ bên dưới.
- `source` chỉ là metadata, không tạo link vì backend chưa cung cấp URL công khai.
- Textarea hỗ trợ `Enter` để gửi và `Shift+Enter` để xuống dòng.
- Không gửi khi nội dung rỗng hoặc đang có request.
- Khi chờ response, disable textarea/nút gửi và hiển thị “Đang trả lời...”.
- Sau khi gửi thành công, xóa textarea và cuộn xuống message mới nhất.
- Nếu request lỗi, giữ tin nhắn user và hiển thị một thông báo lỗi trong vùng chat.
- Không render nội dung chatbot bằng `dangerouslySetInnerHTML`; hiển thị text an toàn
  với `white-space: pre-wrap`.

## 7. Component tối thiểu

Giữ cấu trúc nhỏ:

```text
src/
├── app/
│   ├── api/chat/route.ts
│   ├── globals.css
│   ├── layout.tsx
│   └── page.tsx
├── components/
│   ├── chat-message.tsx
│   └── chat-window.tsx
└── types/
    └── chat.ts
```

Trách nhiệm:

- `page.tsx`: layout trang và render `ChatWindow`.
- `chat-window.tsx`: Client Component quản lý messages, input, loading, error và
  gửi request.
- `chat-message.tsx`: hiển thị một message và sources.
- `route.ts`: proxy request đến Django.

Không tạo service, hook hoặc context riêng cho phiên bản đầu tiên.

## 8. Luồng gửi tin nhắn

Trong `ChatWindow`:

1. Trim input và dừng nếu rỗng hoặc đang loading.
2. Thêm message của user vào state.
3. Đặt `loading = true`, xóa lỗi cũ.
4. Gọi `fetch("/api/chat", ...)`.
5. Nếu response không thành công, đọc trường `error`; nếu không có dùng thông
   báo mặc định `Không thể nhận câu trả lời. Vui lòng thử lại.`.
6. Nếu thành công, kiểm tra `answer` là chuỗi và `sources` là mảng rồi thêm
   message assistant.
7. Trong `finally`, đặt `loading = false`.

Lịch sử message chỉ lưu trong React state và mất khi reload trang. Đây là hành
vi mong muốn cho giai đoạn hiện tại.

## 9. Giao diện và accessibility

- Dùng màu nền sáng, nội dung dễ đọc, chiều rộng chat tối đa khoảng `800px`.
- Nút và textarea có trạng thái focus rõ ràng.
- Textarea có `aria-label="Câu hỏi du lịch"`.
- Vùng messages có `aria-live="polite"` để thông báo câu trả lời mới.
- Nút gửi có text, không chỉ dùng icon.
- Không cần dark mode hoặc animation phức tạp.

## 10. Các bước triển khai

### Bước 1 — Khởi tạo Next.js

- Tạo project `frontend` theo cấu hình ở mục 2.
- Tạo `.env.local` và `.env.example` với `BACKEND_URL`.
- Không commit `.env.local`.

### Bước 2 — Khai báo types và API proxy

- Tạo types trong `src/types/chat.ts`.
- Tạo `src/app/api/chat/route.ts`.
- Kiểm tra proxy trả được `200`, `400`, `502` và chuyển tiếp `503`.

### Bước 3 — Tạo giao diện chat

- Tạo `ChatWindow` và `ChatMessage`.
- Quản lý state bằng `useState`.
- Hoàn thiện gửi message, loading, sources và error.

### Bước 4 — Hoàn thiện responsive và accessibility

- Chỉnh Tailwind cho mobile/desktop.
- Kiểm tra thao tác bàn phím, focus và cuộn message.

### Bước 5 — Kiểm tra tích hợp

- Chạy Django tại `127.0.0.1:8000`.
- Chạy Next.js tại `127.0.0.1:3000`.
- Gửi câu hỏi có dữ liệu và xác nhận hiển thị answer + sources.
- Gửi câu hỏi ngoài Knowledge Base và xác nhận hiển thị thông báo thiếu dữ liệu.
- Tắt Django và xác nhận frontend hiển thị lỗi kết nối.
- Kiểm tra câu hỏi rỗng không tạo request.
- Chạy `npm run lint` và `npm run build`.

## 11. Tiêu chí hoàn thành

- Người dùng có thể chat hỏi đáp với backend từ trình duyệt.
- Answer và sources hiển thị đúng theo response Django.
- Không gặp lỗi CORS vì request đi qua Next.js Route Handler.
- Loading và lỗi kết nối được hiển thị rõ ràng.
- Giao diện dùng được trên mobile và desktop.
- Frontend build thành công.
- Không triển khai conversation history phía backend, streaming, đăng nhập hoặc
  lưu lịch sử vào local storage trong phiên bản này.
