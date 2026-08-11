# Travel Chatbot Backend

Django backend cho chatbot du lich RAG, dung Gemini Embedding va ChromaDB.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Tao file `.env`:

```env
GEMINI_API_KEY=your_gemini_api_key
GEMINI_EMBEDDING_MODEL=gemini-embedding-001
```

## Kiem Tra

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py test
.\.venv\Scripts\python.exe manage.py ingest_knowledge --dry-run
```

## Ingest Knowledge Base

Chay ingest that de tao/cap nhat `chroma_db/`:

```powershell
.\.venv\Scripts\python.exe manage.py ingest_knowledge
```

Chay lai lan 2 de kiem tra dong bo on dinh. Neu du lieu khong doi, output nen co `Added: 0`.

## Thu Retrieval

Retrieval tim cac chunk gan voi cau hoi nhat trong ChromaDB. `Top K` la so
chunk duoc tra ve; mac dinh la 5.

Tren PowerShell, dat encoding UTF-8 de hien thi tieng Viet dung:

```powershell
$env:PYTHONIOENCODING = "utf-8"
```

Chay mot cau hoi:

```powershell
.\.venv\Scripts\python.exe manage.py retrieve_knowledge "Ngũ Hành Sơn có phải chỉ là một ngọn núi không?"
```

Muon thay doi so chunk:

```powershell
.\.venv\Scripts\python.exe manage.py retrieve_knowledge "Huế có những hoạt động gì?" --top-k 3
```

Ket qua hien thi thu hang, `source`, `title`, heading va mot doan noi dung cua
tung chunk. Can ingest Knowledge Base truoc khi thu Retrieval.

## Thu RAG Chat

Sau khi Knowledge Base da ingest, co the thu luong RAG day du bang command:

```powershell
$env:PYTHONIOENCODING = "utf-8"
.\.venv\Scripts\python.exe manage.py ask_travel "Hue co nhung hoat dong gi?"
```

Co the thay doi so chunk duoc dua vao Context:

```powershell
.\.venv\Scripts\python.exe manage.py ask_travel "Di Hoi An tu Da Nang mat bao lau?" --top-k 3
```

Command hien thi cau tra loi va cac `title`/`source` cua chunks da duoc dung.
Neu Knowledge Base khong co du thong tin, chatbot tra ve:
`Knowledge Base hien chua co du thong tin.`

## Chay Server

```powershell
.\.venv\Scripts\python.exe manage.py runserver
```

Mac dinh server chay tai `http://127.0.0.1:8000/`.
