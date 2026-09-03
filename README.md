# Travel Chatbot

Travel Chatbot là hệ thống trợ lý du lịch Việt Nam kết hợp RAG, Google Gemini và
dữ liệu địa điểm từ Mapbox. Dự án gồm ba ứng dụng chính:

- `frontend`: giao diện người dùng và bản đồ.
- `chatbot_service`: chatbot, RAG và điều phối nghiệp vụ.
- `backend`: dịch vụ ASP.NET Core làm việc với Mapbox.

## Công nghệ sử dụng

| Thành phần | Công nghệ | Chức năng chính |
| --- | --- | --- |
| Frontend | Next.js 16, React 19, TypeScript, Tailwind CSS 4 | Giao diện chat, context hội thoại, speech-to-text và API proxy |
| Bản đồ | Mapbox GL JS | Hiển thị vị trí người dùng và địa điểm được gợi ý |
| Chatbot service | Python, Django 5.2, Django REST Framework | Nhận request, phân tích câu hỏi và điều phối các công cụ |
| AI | Google Gemini, Gemini Live, LangChain | Hiểu ý định, nhận dạng giọng nói, sinh ứng viên và tạo câu trả lời |
| RAG | LangChain, ChromaDB, Gemini Embeddings | Lập chỉ mục và truy xuất Knowledge Base |
| Backend | ASP.NET Core Web API, .NET 10 | Gọi Mapbox và cấp token ngắn hạn cho Gemini Live |
| Dịch vụ ngoài | Google Gemini API, Gemini Live API, Mapbox Search API | Sinh nội dung, embedding, speech-to-text, tìm kiếm và xác minh địa điểm |

## Kiến trúc hệ thống

```mermaid
flowchart LR
    U[Người dùng] --> FE[Next.js Frontend]
    FE -->|POST /api/chat| NP[Next.js API Proxy]
    NP -->|POST /api/chat/| DJ[Django Chatbot Service]

    DJ --> SI[Semantic Interpreter]
    SI --> GM[Google Gemini]
    DJ --> OR[Chat Orchestrator]
    OR --> RAG[RAG Tool]
    RAG --> CH[(ChromaDB)]
    OR --> NET[ASP.NET Core Backend]
    NET --> MB[Mapbox Search API]

    DJ -->|answer, sources, places| NP
    NP --> FE
    FE --> MAP[Mapbox GL JS]
    MAP --> MB
```

### Frontend

`frontend` chạy tại `http://localhost:3000` và chịu trách nhiệm:

- Hiển thị giao diện chat, nguồn tham khảo và thông tin địa điểm.
- Gửi request qua Next.js API route thay vì gọi Django trực tiếp từ trình duyệt.
- Lưu tối đa ba lượt hỏi đáp gần nhất trong `localStorage`.
- Thu âm từ microphone và đưa transcript tiếng Việt vào ô soạn thảo để người dùng
  kiểm tra, chỉnh sửa rồi chủ động gửi.
- Xin quyền truy cập GPS khi chatbot cần vị trí hiện tại.
- Hiển thị vị trí và marker địa điểm bằng Mapbox GL JS.

### Chatbot service

`chatbot_service` chạy tại `http://127.0.0.1:8000` và là tầng nghiệp vụ chính:

- Kiểm tra `message`, `history` và `current_location`.
- Dùng Gemini để xác định intent, action, địa danh và điều kiện tìm kiếm.
- Lập kế hoạch gọi RAG hoặc công cụ Mapbox theo allowlist.
- Thu thập bằng chứng rồi yêu cầu Gemini tạo câu trả lời cuối cùng.
- Trả về `answer`, `sources` và `places` cho frontend.

### Backend

`backend` chạy tại `http://localhost:5257` và cung cấp các typed API cho Django:

- Tìm địa điểm theo tên.
- Tìm địa điểm theo danh mục.
- Reverse geocoding từ tọa độ.
- Xác minh danh sách ứng viên địa điểm.
- Lấy chi tiết các POI theo lô.
- Cấp ephemeral token một lần dùng cho phiên speech-to-text với Gemini Live.

Mapbox server token được giữ tại ASP.NET Core. Frontend chỉ sử dụng public token
để hiển thị bản đồ.

### Kho dữ liệu RAG

- Dữ liệu Markdown nằm trong `chatbot_service/chatbot/knowledge_base`.
- Vector được lưu cục bộ trong ChromaDB.
- Gemini Embeddings được dùng để tạo vector cho tài liệu và câu truy vấn.

## Các luồng hoạt động

### 1. Luồng khởi tạo Knowledge Base

```mermaid
flowchart LR
    MD[Knowledge Base Markdown] --> LOAD[Đọc và kiểm tra tài liệu]
    LOAD --> SPLIT[Chia chunk và tạo metadata]
    SPLIT --> EMBED[Gemini Embeddings]
    EMBED --> SYNC[Đồng bộ vector]
    SYNC --> CHROMA[(ChromaDB)]
    CHROMA --> RETRIEVE[Truy xuất khi chatbot gọi RAG]
```

Chạy lại `python manage.py ingest_knowledge` khi thêm, sửa hoặc xóa tài liệu.

### 2. Sơ đồ định tuyến tổng quát theo intent

Mỗi request chỉ có một `primary_intent`. `SemanticInterpreter` chỉ phân loại và
trích xuất semantic data; `IntentRouter` dispatch tới đúng một handler. Handler
tự lập plan, chạy tool/pipeline và gắn evidence policy.

```mermaid
flowchart TD
    U[Người dùng gửi câu hỏi] --> API[Next.js proxy đến ChatAPIView]
    API --> VALIDATE[Kiểm tra message, history, current_location]
    VALIDATE --> SEMANTIC[SemanticInterpreter phân tích bằng Gemini]
    SEMANTIC --> GPS{Cần vị trí hiện tại<br/>nhưng chưa có tọa độ?}

    GPS -->|Có| CLIENT[get_current_location]
    CLIENT --> BROWSER[Trình duyệt xin quyền GPS]
    BROWSER --> RETRY[Gửi lại cùng câu hỏi kèm tọa độ]
    RETRY --> SEMANTIC

    GPS -->|Không| ROUTER[IntentRouter dispatch]
    ROUTER --> HANDLER[Một concrete IntentHandler]
    HANDLER --> EXEC[ToolRegistry hoặc domain pipeline]
    EXEC --> COMPOSER[AnswerComposer]
    ROUTER -->|needs_clarification/unsupported| COMPOSER
    COMPOSER --> PROJECTOR[ResponseProjector]
    PROJECTOR --> RESPONSE[answer, sources, places, itinerary]
    RESPONSE --> UI[Frontend hiển thị chat và bản đồ]
```

12 handler được đăng ký tại `chatbot/intent_routing/factory.py`; registry kiểm tra
đủ và không trùng `TravelIntent` ngay khi khởi tạo. `ToolRegistry` vẫn là boundary
allowlist và typed validation duy nhất cho tool backend.

`chatbot.tool_planner.plan_tools()` và `response_policy_for()` chỉ còn là compatibility
facade cho test hoặc integration cũ; runtime request không đi qua hai API này. Có thể
xóa chúng sau khi toàn bộ consumer bên ngoài chuyển sang handler và policy tương ứng.

### 3. Intent `destination_discovery`

Dùng cho yêu cầu gợi ý hoặc so sánh điểm đến theo thời gian, sở thích, nhóm đi
và ngân sách.

```mermaid
flowchart LR
    I[destination_discovery] --> RAG[Truy xuất Knowledge Base]
    I --> LOC{Có địa danh<br/>làm vùng tìm kiếm?}
    LOC -->|Có| FORWARD[Mapbox forward search lấy tọa độ]
    LOC -->|Không| CANDIDATE
    RAG --> CANDIDATE[Gemini sinh ứng viên]
    FORWARD --> CANDIDATE
    CANDIDATE --> VERIFY[Mapbox xác minh ứng viên theo lô]
    VERIFY --> EVIDENCE[matchedCandidates và dữ liệu RAG]
    EVIDENCE --> ANSWER[Gemini tạo câu trả lời]
    ANSWER --> PLACES[Trả địa điểm đã xác minh cho bản đồ]
```

### 4. Intent `place_search` và `place_details`

Hai intent này ưu tiên dữ liệu Mapbox. Knowledge Base chỉ bổ sung bối cảnh ổn
định và không thay thế dữ liệu địa điểm từ provider.

```mermaid
flowchart TD
    START{Intent}
    START -->|place_search| SEARCH_ACTION{Action tìm kiếm}
    START -->|place_details| RAG_DETAILS[Truy xuất RAG bổ sung]
    RAG_DETAILS --> NAMED[Forward search địa điểm cụ thể]

    SEARCH_ACTION -->|find_named_place| NAMED
    SEARCH_ACTION -->|discover_places| ANCHOR{Đã có tọa độ vùng?}
    SEARCH_ACTION -->|reverse_geocode| REVERSE[Mapbox reverse lookup]

    ANCHOR -->|Chưa có| RESOLVE_AREA[Forward search địa danh làm mốc]
    ANCHOR -->|Đã có| CATEGORY[Mapbox category search]
    RESOLVE_AREA --> CATEGORY

    NAMED --> EVIDENCE[Chuẩn hóa Mapbox evidence]
    CATEGORY --> EVIDENCE
    REVERSE --> EVIDENCE
    RAG_DETAILS --> EVIDENCE
    EVIDENCE --> ANSWER[Gemini tạo câu trả lời Mapbox-first]
    ANSWER --> SELECT[Chọn place hợp lệ được nhắc trong answer]
    SELECT --> ENRICH[Lấy chi tiết POI theo một batch]
    ENRICH --> UI[Thẻ địa điểm và marker Mapbox]
```

### 5. Nhóm intent tư vấn dựa trên RAG

Nhóm này gồm `travel_qa`, `itinerary_advice`, `transportation_qa` và
`budget_qa`. `itinerary_advice` chỉ tư vấn lịch trình dạng văn bản; hệ thống hiện
không lưu lịch trình hoặc tính route.

```mermaid
flowchart LR
    I{Intent tư vấn} --> TQ[travel_qa]
    I --> IA[itinerary_advice]
    I --> TR[transportation_qa]
    I --> BQ[budget_qa]

    TQ --> RAG[RAG search]
    IA --> RAG
    TR --> RAG
    BQ --> RAG
    RAG --> OPTIONAL{Action có yêu cầu<br/>tìm địa điểm?}
    OPTIONAL -->|Có| MAPBOX[Thực thi Mapbox tool phù hợp]
    OPTIONAL -->|Không| POLICY[RAG-first evidence]
    MAPBOX --> POLICY
    POLICY --> ANSWER[Gemini tổng hợp tư vấn]
    ANSWER --> RESPONSE[answer và sources]
```

### 6. Intent phụ thuộc hội thoại và intent không dùng tool

```mermaid
flowchart TD
    I{Intent}
    I -->|context_follow_up| CONTEXT[Đọc tối đa 3 lượt hỏi đáp gần nhất]
    CONTEXT --> ACTION[Khôi phục đối tượng được nhắc và xác định action]
    ACTION --> PLAN{Action cần dữ liệu?}
    PLAN -->|Có| TOOLS[RAG hoặc Mapbox tools]
    PLAN -->|Không| DIRECT[Trả lời từ ngữ cảnh]

    I -->|general_chat| DIRECT
    I -->|unsupported_capability| LIMIT[Thông báo giới hạn tính năng]
    I -->|semantic status needs_clarification| CLARIFY[Yêu cầu người dùng bổ sung thông tin]

    TOOLS --> ANSWER[Gemini tạo câu trả lời]
    DIRECT --> ANSWER
    LIMIT --> ANSWER
    CLARIFY --> ANSWER
    ANSWER --> RESPONSE[Trả response cho frontend]
```

`unsupported_capability` áp dụng cho yêu cầu chưa được hỗ trợ như chỉ đường trực
tiếp, giao thông thời gian thực hoặc lưu dữ liệu người dùng.

### 7. Quản lý context hội thoại

Ứng dụng giữ context ở frontend để Django tiếp tục stateless, không tạo Django
Session, bảng hội thoại hoặc migration. Một lượt hội thoại gồm một câu hỏi của người
dùng và một câu trả lời của trợ lý; tối đa ba lượt hoàn chỉnh, tương đương sáu message
`user`/`assistant`, được lưu bằng key `travel_chat_messages` trong `localStorage`.

```mermaid
flowchart LR
    LOAD[Mở ứng dụng] --> RESTORE[Khôi phục tối đa 3 lượt từ localStorage]
    INPUT[Người dùng gửi câu hỏi mới] --> HISTORY[Lấy các lượt đã hoàn chỉnh trước đó]
    HISTORY --> TRIM[Giới hạn 6 message user/assistant]
    TRIM --> NEXT[Next.js POST /api/chat]
    NEXT --> VALIDATE[Next.js và Django kiểm tra history]
    VALIDATE --> SEMANTIC[Gemini phân tích intent và giải tham chiếu]
    VALIDATE --> ANSWER[Gemini tạo câu trả lời với context]
    ANSWER --> COMPLETE[Thêm câu trả lời hoàn chỉnh]
    COMPLETE --> SAVE[Cắt còn 3 lượt và lưu localStorage]
    NEW[Cuộc trò chuyện mới] --> CLEAR[Xóa state và travel_chat_messages]
```

Message người dùng đang chờ phản hồi không được lưu và câu hỏi hiện tại không bị lặp
trong `history`. Next.js và Django cùng từ chối history vượt quá sáu message; mỗi
`content` phía Django có giới hạn 4.000 ký tự. `SemanticInterpreter` dùng history để
hiểu câu hỏi nối tiếp, còn `AnswerComposer` chuyển đúng thứ tự thành
`HumanMessage`/`AIMessage` trước khi thêm câu hỏi hiện tại.

Khi tải lại trang, dữ liệu hợp lệ được khôi phục; JSON hỏng hoặc trường không hợp lệ
được bỏ qua để UI vẫn hoạt động. Frontend chỉ lưu nội dung hội thoại và nguồn tham
khảo cần thiết, không lưu tọa độ GPS hay audio microphone. Nút **Cuộc trò chuyện
mới** xóa cả state trong bộ nhớ và dữ liệu hội thoại đã lưu.

### 8. Speech-to-text với Gemini Live

Speech-to-text dùng model `gemini-3.5-transcribe-live`, chế độ `SMART` cho tiếng Việt
`vi-VN`. API key Gemini Live chỉ nằm ở ASP.NET Core; browser nhận ephemeral token
ngắn hạn, một lần dùng qua Next.js proxy rồi kết nối WebSocket trực tiếp tới Gemini.

```mermaid
flowchart LR
    MIC[Người dùng bấm Nói] --> PERMISSION[Trình duyệt xin quyền microphone]
    PERMISSION --> WORKLET[AudioWorklet chuyển âm thanh thành PCM16 mono 16 kHz]

    FE[Frontend] -->|POST /api/speech-token| NEXT[Next.js proxy]
    NEXT -->|POST /api/speech/ephemeral-token| NET[ASP.NET Core]
    NET -->|API key server-side| TOKEN[Gemini v1alpha auth_tokens]
    TOKEN -->|Ephemeral token một lần dùng| FE

    WORKLET -->|Chunk 100 ms qua WebSocket| LIVE[Gemini Live]
    FE -->|Setup TEXT, SMART vi-VN, manual activity| LIVE
    LIVE -->|Interim và final transcript| COMPOSER[Ô soạn thảo]
    COMPOSER --> EDIT[Người dùng dừng và chỉnh sửa]
    EDIT -->|Tự bấm Gửi| CHAT[Luồng POST /api/chat]
```

Audio được gửi theo MIME `audio/pcm;rate=16000` với chunk 1.600 mẫu, tương đương
khoảng 100 ms. Frontend nhận cả interim transcript để hiển thị khi đang nói và final
transcript khi kết thúc đoạn nói. WebSocket có thể trả frame dạng `string`, `Blob`
hoặc `ArrayBuffer`; client xử lý cả ba dạng.

Nút microphone hỗ trợ các trạng thái xin quyền/token, đang nghe và đang dừng. Người
dùng có thể dừng cả khi bước khởi tạo còn chờ; ứng dụng sẽ đóng WebSocket,
`AudioContext` và media track khi kết thúc hoặc hủy. Transcript được nối vào nội dung
đang có trong composer, không tự gửi, không phát lại bằng TTS và không lưu audio.

### 9. Luồng hiển thị kết quả trên frontend

```mermaid
flowchart LR
    RESPONSE[answer, sources, places] --> CHAT[Hiển thị câu trả lời và nguồn]
    RESPONSE --> VALID[Kiểm tra mapboxId và tọa độ]
    VALID --> MARKER[Tạo marker trên Mapbox GL]
    MARKER --> HOVER[Hover thẻ làm nổi bật marker]
    MARKER --> CLICK[Click thẻ đưa bản đồ đến địa điểm]
    RESPONSE --> HISTORY[Lưu tối đa 3 lượt hỏi đáp]
```

Frontend không lưu tọa độ GPS chính xác vào `localStorage`.

## Yêu cầu

- Python 3 và `pip`.
- .NET 10 SDK.
- Node.js và npm.
- Gemini API key.
- Mapbox access token cho backend và public token cho frontend.
- Trình duyệt có microphone và cho phép truy cập microphone; dùng `localhost` khi
  phát triển hoặc HTTPS khi triển khai.

Không commit API key, access token hoặc file `.env` thật lên Git.

## Cài đặt và chạy dự án

Ba ứng dụng cần chạy trong ba cửa sổ PowerShell riêng.

### 1. ASP.NET Core Backend

Tại thư mục gốc `Travel-Chatbot`:

```powershell
dotnet user-secrets set "Mapbox:AccessToken" "your_server_mapbox_token" --project .\backend\backend\backend.csproj
dotnet user-secrets set "GeminiLive:ApiKey" "your_gemini_api_key" --project .\backend\backend\backend.csproj
dotnet run --project .\backend\backend\backend.csproj --launch-profile http
```

`GeminiLive:ApiKey` được .NET dùng để cấp ephemeral token và không được gửi xuống
frontend. Backend chạy tại `http://localhost:5257`. Swagger UI có tại
`http://localhost:5257/swagger` trong môi trường Development.

### 2. Django Chatbot Service

```powershell
cd chatbot_service
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Cấu hình `chatbot_service/.env`:

```env
GEMINI_API_KEY=your_gemini_api_key
GEMINI_EMBEDDING_MODEL=gemini-embedding-001
GEMINI_CHAT_MODEL=gemini-3.5-flash-lite
MAPBOX_TOOL_BASE_URL=http://localhost:5257
MAPBOX_TOOL_TIMEOUT_SECONDS=12
CHATBOT_MAX_TOOL_CALLS=8
```

Khởi tạo Knowledge Base và chạy Django:

```powershell
python manage.py ingest_knowledge
python manage.py runserver
```

API chat chạy tại `http://127.0.0.1:8000/api/chat/`.

### 3. Next.js Frontend

```powershell
cd frontend
npm install
Copy-Item .env.example .env
```

Cấu hình `frontend/.env`:

```env
BACKEND_URL=http://127.0.0.1:8000
DOTNET_BACKEND_URL=http://localhost:5257
NEXT_PUBLIC_MAPBOX_ACCESS_TOKEN=your_public_mapbox_token
```

Chạy frontend:

```powershell
npm run dev
```

Mở `http://localhost:3000` để sử dụng ứng dụng.

## Kiểm tra dự án

```powershell
dotnet test .\backend\backend.slnx

cd chatbot_service
python manage.py test

cd ..\frontend
npm run lint
npm run build
npm run test:e2e
```

`npm run test:e2e` tự khởi động một Next.js server riêng tại cổng `3100` và chạy
Playwright bằng Microsoft Edge Stable. Bộ E2E mock response Gemini/Mapbox, token STT,
WebSocket và microphone để kiểm tra ổn định luồng frontend; máy chạy test cần cài
Microsoft Edge.

Các test cục bộ kiểm tra logic và contract của ứng dụng nhưng không thay thế kiểm
thử trực tiếp Gemini, Mapbox và kết nối mạng đến các nhà cung cấp.
