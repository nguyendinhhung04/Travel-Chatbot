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

## Chay Server

```powershell
.\.venv\Scripts\python.exe manage.py runserver
```

Mac dinh server chay tai `http://127.0.0.1:8000/`.
