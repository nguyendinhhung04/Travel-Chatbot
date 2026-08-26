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
GEMINI_CHAT_MODEL=gemini-3.5-flash-lite
MAPBOX_TOOL_BASE_URL=http://localhost:5257
MAPBOX_TOOL_TIMEOUT_SECONDS=12
CHATBOT_MAX_TOOL_CALLS=4
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
chunk ung vien toi da; mac dinh la 5. He thong chi giu cac chunk co relevance
score tu `0.5` tro len. Vi vay so chunk thuc te co the it hon `Top K`, hoac bang
0 neu khong co chunk nao du lien quan.

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

## Thu Chat API

Sau khi da ingest Knowledge Base va cau hinh `GEMINI_API_KEY`, khoi dong server:

```powershell
.\.venv\Scripts\python.exe manage.py runserver
```

Goi endpoint bang PowerShell:

```powershell
$body = @{ message = "Hue co nhung hoat dong gi?" } | ConvertTo-Json
Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8000/api/chat/" `
  -ContentType "application/json; charset=utf-8" `
  -Body $body
```

Response gom `answer`, danh sach `sources` va `places` Mapbox da xac minh (chi nhung dia diem duoc nhac trong cau tra loi). Cau hoi khong hop le tra `400`; loi Gemini,
Embedding hoac Chroma tra `503` voi thong bao an toan.

### Intent, Semantic va Tool flow

Moi request duoc xu ly theo thu tu:

1. Gemini tra ve `SemanticInterpretation` da duoc Pydantic validate.
2. Backend `ToolPlanner` chon tool tu intent va semantic action.
3. `CategoryResolver` anh xa travel domain sang canonical Mapbox category trong whitelist.
4. Voi destination discovery, Gemini tao candidate; ASP.NET xac minh ca batch,
   matching, loai trung va chi tra DTO da chuan hoa.
5. Django dua evidence da xac minh cho Gemini tong hop cau tra loi. Nhanh thong
   thuong gom du lieu thanh `knowledgeBase` va `mapbox`; ket qua tim anchor nam trong
   `mapbox.destinationLocations`, con dia diem duoc phep de xuat nam trong
   `mapbox.places`. Nhanh destination discovery giu nguyen `destinationResolved`,
   `matchedCandidates` va `additionalMapboxPlaces`.

Bo runtime tool gom:

- `search_travel_knowledge`: kien thuc va tu van du lich tu Knowledge Base.
- `mapbox_forward_search`: ten rieng, dia chi hoac POI cu the.
- `mapbox_category_search`: kham pha POI theo category do backend resolve.
- `mapbox_reverse_lookup`: tra dia diem tu toa do.
- `mapbox_resolve_candidates`: batch noi bo cho destination discovery; Django khong
  xu ly raw Mapbox hoac tu matching provider result.

`mapbox_list_categories` khong nam trong runtime flow. Danh sach category da duoc loc
trong `docs/travel_categories_mapbox.md`, vi vay chatbot khong can tai lai toan bo
category trong moi cau hoi. Contract hien tai cung khong co route, ETA, luu itinerary,
MongoDB hay user.

Request co the gui them context khong luu tru:

```json
{
  "message": "Tim quan cafe gan day",
  "history": [
    {"role": "user", "content": "Toi dang o cau Rong"}
  ],
  "current_location": {
    "longitude": 108.227,
    "latitude": 16.061,
    "radius_km": 1
  }
}
```

## Chay Server

```powershell
.\.venv\Scripts\python.exe manage.py runserver
```

Mac dinh server chay tai `http://127.0.0.1:8000/`.
