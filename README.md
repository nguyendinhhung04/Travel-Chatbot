# Travel Chatbot

Ứng dụng chatbot du lịch gồm:

- `chatbot_service`: Django REST API, RAG, Gemini và ChromaDB.
- `frontend`: giao diện Next.js.

## Yêu cầu

Trước khi chạy dự án, cần cài đặt:

- Python 3
- Node.js và npm
- Gemini API key

## 1. Cài đặt Chatbot Service

Mở PowerShell tại thư mục gốc của dự án, sau đó chuyển vào
`chatbot_service`:

```powershell
cd chatbot_service
```

### Tạo và kích hoạt môi trường ảo

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### Cài đặt thư viện Python

```powershell
python -m pip install -r requirements.txt
```

### Tạo file môi trường

Sao chép file cấu hình mẫu:

```powershell
Copy-Item .env.example .env
```

Mở file `chatbot_service/.env` và cấu hình:

```env
GEMINI_API_KEY=your_gemini_api_key
GEMINI_EMBEDDING_MODEL=gemini-embedding-001
GEMINI_CHAT_MODEL=gemini-3.6-flash
```

Không commit Gemini API key thật lên Git.

### Ingest Knowledge Base

Chạy lệnh sau để đưa dữ liệu trong Knowledge Base vào ChromaDB:

```powershell
python manage.py ingest_knowledge
```

### Chạy Chatbot Service

```powershell
python manage.py runserver
```

Chatbot Service mặc định chạy tại `http://127.0.0.1:8000`.

## 2. Cài đặt Frontend

Giữ Chatbot Service đang chạy. Mở một cửa sổ PowerShell khác tại thư mục gốc
của dự án, sau đó chuyển vào `frontend`:

```powershell
cd frontend
```

### Cài đặt thư viện Node.js

```powershell
npm install
```

### Tạo file môi trường

Sao chép file cấu hình mẫu:

```powershell
Copy-Item .env.example .env
```

Kiểm tra file `frontend/.env` có nội dung:

```env
BACKEND_URL=http://127.0.0.1:8000
```

### Chạy Frontend

```powershell
npm run dev
```

Mở `http://localhost:3000` trên trình duyệt để sử dụng chatbot.

## Những lần chạy tiếp theo

### Chatbot Service

```powershell
cd chatbot_service
.\.venv\Scripts\Activate.ps1
python manage.py runserver
```

Chạy lại `python manage.py ingest_knowledge` khi nội dung Knowledge Base được
thêm mới hoặc thay đổi.

### Frontend

```powershell
cd frontend
npm run dev
```
