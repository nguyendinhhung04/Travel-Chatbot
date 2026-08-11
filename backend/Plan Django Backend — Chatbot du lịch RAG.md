# Plan Django Backend — Chatbot du lịch RAG

## 1. Mục tiêu

Xây dựng chatbot du lịch có thể:

- Hỏi thông tin địa điểm du lịch.
- Gợi ý địa điểm, ăn uống, vui chơi.
- Lập lịch trình du lịch đơn giản.
- Trả lời dựa trên Knowledge Base.
- Hiển thị nguồn tham khảo.

### Stack

- Django + Django REST Framework
- LangChain
- Gemini Chat API
- Gemini Embedding API
- ChromaDB
- Markdown Knowledge Base
- SQLite cho lịch sử chat

---

# Giai đoạn 1 — Setup project

## Bước 1. Tạo Django project

```text
travel_chatbot/
├── config/
├── chatbot/
├── knowledge_base/
├── chroma_db/
├── manage.py
├── requirements.txt
└── .env
```

### Checklist

- [x] Tạo virtual environment `.venv`
- [x] Tạo Django project
- [x] Tạo app `chatbot`
- [x] Tạo `requirements.txt`
- [x] Cài Django REST Framework
- [x] Cài LangChain
- [x] Cài ChromaDB
- [x] Cài Gemini SDK / LangChain Gemini integration
- [x] Tạo `.env`
- [x] Cấu hình `GEMINI_API_KEY`
- [ ] Tạo `/api/health/`

---

# Giai đoạn 2 — Chuẩn bị Knowledge Base

Knowledge Base chia thành các file Markdown.

```text
knowledge_base/
├── ha-noi/
│   ├── ho-guom.md
│   └── van-mieu.md
├── tam-dao/
│   ├── overview.md
│   └── cau-may.md
└── da-nang/
    └── ...
```

Markdown nên có cấu trúc:

```markdown
# Cầu Mây Tam Đảo

## Tổng quan

...

## Địa chỉ

...

## Điểm nổi bật

...

## Kinh nghiệm

...
```

### Checklist

- [x] Tạo 10–30 file Markdown
- [x] Mỗi file tập trung vào một địa điểm/chủ đề
- [x] Có heading rõ ràng
- [x] Có tên địa điểm
- [x] Có mô tả
- [x] Có kinh nghiệm/thông tin hữu ích

---

# Giai đoạn 3 — Pipeline lập chỉ mục Knowledge Base

Pipeline:

```text
Markdown
   ↓
Loader
   ↓
Text Splitter
   ↓
Embedding
   ↓
ChromaDB
```

## Bước 1. Load Markdown

Dùng LangChain document loader để đọc các file `.md`.

Output:


```text
List[Document]
```

Mỗi Document gồm:

```text
page_content
metadata
```

### Checklist

- [x] Đọc được toàn bộ file Markdown
- [x] Lưu `source` vào metadata
- [x] Kiểm tra nội dung Document
- [x] Parse và chuẩn hóa YAML front matter
- [x] Chuẩn hóa metadata cho Chroma

---

## Bước 2. Chunking

Dùng LangChain Text Splitter.

Có thể dùng:

```text
MarkdownHeaderTextSplitter
```

để tách theo:

```text
#
##
###
```

sau đó dùng:

```text
RecursiveCharacterTextSplitter
```

để chia đoạn dài hơn.

Thiết lập ban đầu:

```text
chunk_size: 500–800 tokens
chunk_overlap: 50–100 tokens
```

### Checklist

- [x] Tách document theo heading
- [x] Chia đoạn quá dài thành chunk nhỏ
- [x] Giữ metadata của file
- [x] In thử một số chunk để kiểm tra
- [x] Tạo ID ổn định cho chunk

---

## Bước 3. Embedding

Dùng Gemini Embedding thông qua LangChain.

```text
Chunk
 ↓
Gemini Embedding
 ↓
Vector
```

### Checklist

- [x] Khởi tạo Gemini Embedding model
- [x] Kết nối Gemini Embedding
- [x] Embed thử một đoạn text
- [x] Embed toàn bộ chunks

---

## Bước 4. Lưu vào Chroma

Dùng LangChain Chroma Vector Store.

```text
Chunks + Embeddings
        ↓
      Chroma
```

Lưu local:

```text
chroma_db/
```

File triển khai:

```text
chatbot/rag/vector_store.py
```

Chức năng: mở Chroma persistent, đồng bộ chunks theo ID ổn định, chia lô
embedding để phù hợp quota, bỏ qua chunks không đổi và xóa bản ghi đã lỗi thời.

### Checklist

- [x] Tạo Chroma collection
- [x] Lưu chunks
- [x] Lưu metadata
- [x] Dùng persistent storage
- [x] Reload được Chroma sau khi restart

---

## Bước 5. Tạo script ingest

Tạo:

```text
scripts/ingest_knowledge.py
```

Flow:

```text
Load
 ↓
Chunk
 ↓
Embed
 ↓
Save Chroma
```

Chạy:

```bash
python scripts/ingest_knowledge.py
```

### Checklist

- [x] Script chạy độc lập
- [x] Đọc toàn bộ Knowledge Base
- [x] Chunk thành công
- [x] Embedding thành công
- [x] Lưu thành công vào Chroma

---

# Giai đoạn 4 — Retrieval

Khi user hỏi:

```text
Tam Đảo có gì chơi?
```

Flow:

```text
Question
   ↓
Embedding
   ↓
Chroma similarity search
   ↓
Top K documents
```

Dùng LangChain Retriever:

```python
retriever = vectorstore.as_retriever(
    search_kwargs={"k": 5}
)
```

### Checklist

- [ ] Load Chroma
- [ ] Tạo Retriever
- [ ] Search bằng câu hỏi
- [ ] Lấy Top 3–5 chunks
- [ ] Kiểm tra chunks trả về có liên quan

---

# Giai đoạn 5 — RAG Chat

Pipeline chính:

```text
User Question
      ↓
Retriever
      ↓
Relevant Documents
      ↓
Prompt
      ↓
Gemini
      ↓
Answer
```

## Bước 1. Prompt

Prompt cơ bản:

```text
Bạn là trợ lý du lịch.

Chỉ trả lời dựa trên Context được cung cấp.

Nếu Context không có thông tin cần thiết,
hãy nói rằng Knowledge Base chưa có đủ thông tin.

Context:
{context}

Question:
{question}
```

### Checklist

- [ ] Tạo PromptTemplate
- [ ] Truyền context vào prompt
- [ ] Truyền question vào prompt
- [ ] Yêu cầu Gemini không tự bịa thông tin

---

## Bước 2. Gemini Chat Model

Dùng LangChain Gemini Chat Model.

Flow:

```text
Prompt
 ↓
Gemini
 ↓
Answer
```

### Checklist

- [ ] Kết nối Gemini Chat
- [ ] Gọi model thành công
- [ ] Nhận text response

---

## Bước 3. Tạo RAG Chain

Ghép:

```text
Retriever
+
Prompt
+
Gemini
```

thành một RAG pipeline.

### Checklist

- [ ] User question đi vào Retriever
- [ ] Retriever trả documents
- [ ] Documents được đưa vào prompt
- [ ] Gemini sinh câu trả lời
- [ ] API trả answer cho frontend

---

# Giai đoạn 6 — Chat API

Tạo endpoint:

```http
POST /api/chat/
```

Request:

```json
{
    "message": "Tam Đảo có gì chơi?"
}
```

Response:

```json
{
    "answer": "...",
    "sources": [
        {
            "title": "Cầu Mây Tam Đảo",
            "source": "tam-dao/cau-may.md"
        }
    ]
}
```

### Checklist

- [ ] Tạo serializer
- [ ] Tạo API view
- [ ] Gọi RAG Chain
- [ ] Trả answer
- [ ] Trả sources
- [ ] Handle lỗi Gemini API

---

# Giai đoạn 7 — Lịch sử hội thoại

Database đơn giản:

```text
Conversation
    │
    └── Message
```

## Conversation

```text
id
created_at
```

## Message

```text
id
conversation_id
role
content
created_at
```

### Checklist

- [ ] Tạo Conversation model
- [ ] Tạo Message model
- [ ] Lưu câu hỏi user
- [ ] Lưu câu trả lời chatbot
- [ ] Load vài message gần nhất khi chat

Không cần Redis hoặc Vector Memory.

---

# Giai đoạn 8 — Lập lịch trình du lịch

Ví dụ:

```text
Lên lịch trình Tam Đảo 2 ngày 1 đêm.
```

Vẫn dùng cùng pipeline:

```text
Question
   ↓
Retriever
   ↓
Địa điểm liên quan
   ↓
Gemini
   ↓
Itinerary
```

Prompt bổ sung:

```text
Nếu người dùng yêu cầu lập lịch trình:

- Chia theo từng ngày
- Chia sáng / trưa / chiều / tối
- Ưu tiên các địa điểm trong Context
- Không tự tạo địa điểm không có trong Context
```

### Checklist

- [ ] Test câu hỏi lập lịch trình
- [ ] Retriever lấy đúng địa điểm
- [ ] Gemini chia lịch theo ngày
- [ ] Không sinh địa điểm ngoài Knowledge Base

---

# Giai đoạn 9 — Test

## Test Retrieval

Ví dụ:

```text
Cầu Mây ở đâu?
```

Kiểm tra Chroma trả đúng document.

## Test RAG

Ví dụ:

```text
Tam Đảo có gì chơi?
```

Kiểm tra answer dựa trên Knowledge Base.

## Test thiếu dữ liệu

Ví dụ hỏi địa điểm không có trong KB.

Bot nên trả:

```text
Knowledge Base hiện chưa có đủ thông tin.
```

## Test itinerary

```text
Lên lịch trình Tam Đảo 2 ngày.
```

### Checklist

- [ ] Test loading
- [ ] Test chunking
- [ ] Test embedding
- [ ] Test retrieval
- [ ] Test RAG
- [ ] Test source citation
- [ ] Test conversation
- [ ] Test itinerary

---

# Giai đoạn 10 — Hoàn thiện V1

V1 cần có:

- [ ] Django REST API
- [ ] Gemini Chat
- [ ] Gemini Embedding
- [ ] LangChain
- [ ] Markdown Loader
- [ ] Markdown Chunking
- [ ] Chroma Vector DB
- [ ] Retriever
- [ ] RAG Chain
- [ ] Source citation
- [ ] Conversation history
- [ ] Basic itinerary generation

---

# Những phần chưa cần làm

Để tránh over-engineering, V1 chưa cần:

- [ ] Agent
- [ ] Tool Calling
- [ ] Web Search
- [ ] Map API
- [ ] Routing
- [ ] Weather API
- [ ] LangGraph
- [ ] MCP
- [ ] Redis
- [ ] Celery
- [ ] Kafka
- [ ] Microservices
- [ ] Reranking
- [ ] Hybrid Search
- [ ] Graph RAG
- [ ] Multi-agent

---

# Flow cuối cùng

## Indexing

```text
Markdown
   ↓
LangChain Loader
   ↓
Text Splitter
   ↓
Gemini Embedding
   ↓
Chroma
```

## Chat

```text
User
 ↓
Django API
 ↓
LangChain Retriever
 ↓
Chroma
 ↓
Relevant Documents
 ↓
Prompt
 ↓
Gemini
 ↓
Answer + Sources
```

## Thứ tự triển khai khuyến nghị

```text
1. Django Setup
       ↓
2. Gemini Chat
       ↓
3. Knowledge Base
       ↓
4. Markdown Loader
       ↓
5. Chunking
       ↓
6. Gemini Embedding
       ↓
7. Chroma
       ↓
8. Retrieval
       ↓
9. RAG Chain
       ↓
10. Chat API
       ↓
11. Conversation History
       ↓
12. Itinerary Generation
```

Mục tiêu chính của project là hiểu được flow:

```text
Document
→ Chunk
→ Embedding
→ Vector DB
→ Retrieval
→ Prompt
→ LLM
→ Answer
```

LangChain chỉ giúp đơn giản hóa việc kết nối các bước này, còn các khái niệm cốt lõi của RAG vẫn cần hiểu rõ.
