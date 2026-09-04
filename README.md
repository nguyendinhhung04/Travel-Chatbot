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
    FE --> NP[Next.js API Proxy]

    NP -->|Chat request kèm Bearer token| DJ[Django Chatbot Service]
    DJ --> OR[ChatOrchestrator]
    OR --> SI[SemanticInterpreter]
    SI --> GM[Google Gemini]
    OR --> RAG[RAG retrieval]
    RAG --> CH[(ChromaDB)]
    OR -->|Typed tool APIs| NET[ASP.NET Core Backend]

    NP -->|Auth, conversation, itinerary, speech token| NET
    NET --> MB[Mapbox APIs]
    NET --> DB[(MongoDB)]
    NET --> LIVE[Gemini Live auth token]

    OR --> OUT[ChatAPIView response:<br/>answer, sources, places,<br/>itinerary, itineraryOperation]
    OUT --> NP
    NP --> FE
    FE --> MAP[Mapbox GL JS]
    MAP -->|Public map token| MB
```

### Frontend

`frontend` chạy tại `http://localhost:3000` và chịu trách nhiệm:

- Hiển thị giao diện chat, nguồn tham khảo và thông tin địa điểm.
- Gửi request qua Next.js API route thay vì gọi Django trực tiếp từ trình duyệt.
- Gửi tối đa ba lượt hỏi đáp gần nhất làm context cho mỗi chat request.
- Lưu, mở và xóa conversation của tài khoản qua ASP.NET Core và MongoDB.
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
- Đăng ký, đăng nhập và xác thực JWT.
- Lưu conversation và itinerary theo người dùng trong MongoDB.
- Tối ưu route và cập nhật có version khi thêm điểm dừng vào itinerary.
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
    QUESTION[Câu hỏi cần kiến thức du lịch] --> RETRIEVE[Vector search k=5]
    CHROMA --> RETRIEVE
    RETRIEVE --> EVIDENCE[Knowledge Base evidence cho handler]
    EVIDENCE --> ANSWER[Gemini tổng hợp câu trả lời]
```

Chạy lại `python manage.py ingest_knowledge` khi thêm, sửa hoặc xóa tài liệu.

### 2. Sơ đồ định tuyến tổng quát theo intent

Mỗi request chỉ có một `primary_intent`. `SemanticInterpreter` chỉ phân loại và
trích xuất semantic data; `IntentRouter` dispatch tới đúng một handler. Handler
tự lập plan, chạy tool/pipeline và gắn evidence policy.

```mermaid
flowchart TD
    U[Người dùng gửi câu hỏi] --> API[Next.js proxy đến ChatAPIView]
    API --> VALIDATE[Kiểm tra message, history, GPS,<br/>suggested_places và active itinerary]
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
    PROJECTOR --> RESPONSE[answer, sources, places,<br/>itinerary, itineraryOperation]
    RESPONSE --> UI[Frontend hiển thị chat, POI và route]
    UI --> SAVE[Lưu lượt hoàn chỉnh qua conversation API]
    SAVE --> MONGO[(MongoDB)]
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
    START -->|place_search| SEARCH_ACTION{Action Mapbox}
    START -->|place_details| DETAILS_ACTION{Action Mapbox}
    START -->|place_details| RAG_DETAILS[Truy xuất RAG bổ sung]

    SEARCH_ACTION -->|find_named_place| NAMED[Mapbox forward search]
    SEARCH_ACTION -->|discover_places| ANCHOR{Đã có tọa độ vùng?}
    SEARCH_ACTION -->|reverse_geocode| REVERSE[Mapbox reverse lookup]
    DETAILS_ACTION -->|find_named_place| NAMED
    DETAILS_ACTION -->|discover_places| ANCHOR
    DETAILS_ACTION -->|Thiếu action Mapbox nhưng có địa danh| NAMED

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
`budget_qa`. Riêng `itinerary_advice` chỉ tư vấn lịch trình dạng văn bản; yêu cầu
tạo và lưu route được định tuyến sang `itinerary_making`.

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

### 6. Intent `itinerary_making`

Luồng này tạo lịch trình có từ 2 đến 12 điểm dừng đã xác minh. Nếu người dùng yêu
cầu tạo lịch trình từ danh sách vừa được gợi ý, frontend gửi lại tối đa 12
`suggested_places` có `mapboxId` và tọa độ; pipeline tái sử dụng các POI đó thay vì
để Gemini sinh lại tên địa điểm.

```mermaid
flowchart TD
    I[itinerary_making + make_itinerary] --> RAG[Truy xuất Knowledge Base]
    I --> DEST{Đã có tọa độ điểm đến?}
    DEST -->|Chưa có| FORWARD[Mapbox forward search điểm đến]
    DEST -->|Đã có| SOURCE{Có suggested_places<br/>từ câu trả lời trước?}
    FORWARD --> SOURCE

    SOURCE -->|Có| REUSE[Tái sử dụng POI đã có<br/>mapboxId và tọa độ]
    SOURCE -->|Không| GENERATE[Gemini sinh ứng viên địa điểm]
    GENERATE --> LIMIT[Chọn tối đa 12 ứng viên]
    LIMIT --> VERIFY[Mapbox resolve candidates theo batch]
    REUSE --> DEDUPE[Khử trùng lặp và yêu cầu 2-12 điểm]
    VERIFY --> DEDUPE

    DEDUPE --> CREATE[Tool create_itinerary gọi ASP.NET Core]
    CREATE --> OPTIMIZE[Mapbox Optimization sắp thứ tự và tạo route]
    OPTIMIZE --> PERSIST[Lưu itinerary version 1 vào MongoDB]
    PERSIST --> RESPONSE[Trả itinerary và create_itinerary success]
    RESPONSE --> UI[Hiển thị danh sách điểm dừng,<br/>marker đánh số và đường route]
```

Nếu không xác minh đủ hai điểm, tối ưu route thất bại hoặc MongoDB không lưu được,
response không chứa một itinerary giả hay route tự suy diễn.

### 7. Intent `itinerary_management`

Runtime hiện hỗ trợ thao tác `add_itinerary_stop`; các thao tác xóa, thay thế hoặc
sắp xếp lại chưa đi qua pipeline quản lý này.

```mermaid
flowchart TD
    I[itinerary_management] --> ACTION{Action có phải<br/>add_itinerary_stop?}
    ACTION -->|Không| UNSUPPORTED[unsupported_itinerary_operation]
    ACTION -->|Có| ACTIVE{Có active itinerary<br/>id và version?}
    ACTIVE -->|Không| MISSING[missing_active_itinerary]
    ACTIVE -->|Có| GET[Đọc itinerary hiện tại từ MongoDB]
    GET --> VERSION{Version còn khớp?}
    VERSION -->|Không| CONFLICT[version_conflict]
    VERSION -->|Có| RESOLVE[Mapbox xác minh duy nhất<br/>địa điểm cần thêm]
    RESOLVE --> DUPLICATE{Đã có cùng mapboxId?}
    DUPLICATE -->|Có| DUP[duplicate_stop]
    DUPLICATE -->|Không| ADD[POST thêm điểm với expectedVersion]
    ADD --> OPTIMIZE[Mapbox tối ưu lại toàn bộ route]
    OPTIMIZE --> UPDATE[Cập nhật có điều kiện và tăng version trong MongoDB]
    UPDATE --> RESPONSE[Trả itinerary mới và add_itinerary_stop success]
    RESPONSE --> UI[Frontend thay route và marker]
```

### 8. Intent phụ thuộc hội thoại và intent không dùng tool

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

`unsupported_capability` áp dụng cho yêu cầu chưa được hỗ trợ như điều hướng từng
chặng theo thời gian thực, dữ liệu giao thông trực tiếp hoặc thao tác itinerary ngoài
phạm vi đang triển khai.

### 9. Quản lý context và lưu hội thoại

Django vẫn xử lý từng request theo kiểu stateless. Frontend giữ hội thoại đang mở
trong state, gửi tối đa ba lượt hoàn chỉnh gần nhất làm `history`, rồi lưu mỗi lượt
đã hoàn thành qua ASP.NET Core vào MongoDB theo tài khoản đăng nhập.

```mermaid
flowchart TD
    LOGIN[Người dùng đăng nhập] --> COOKIE[Next.js giữ JWT trong HttpOnly cookie]
    COOKIE --> LIST[GET danh sách conversation và itinerary mới nhất]
    LIST --> OPEN{Mở conversation đã lưu?}
    OPEN -->|Có| RESTORE[Khôi phục messages, sources,<br/>places và itinerary từ MongoDB]
    OPEN -->|Không| EMPTY[Khởi tạo state hội thoại mới]

    INPUT[Người dùng gửi câu hỏi] --> HISTORY[Lấy tối đa 3 lượt hoàn chỉnh gần nhất]
    HISTORY --> CONTEXT[Đính kèm active itinerary và<br/>suggested_places khi phù hợp]
    CONTEXT --> CHAT[POST /api/chat qua Next.js]
    CHAT --> ANSWER[Django trả lời bằng history hiện tại]
    ANSWER --> COMPLETE{Đã có đủ user + assistant?}
    COMPLETE -->|Có| SAVE[Create conversation hoặc append turn]
    SAVE --> MONGO[(MongoDB)]
    SAVE --> SIDEBAR[Cập nhật danh sách conversation]

    NEW[Cuộc trò chuyện mới] --> EMPTY
    DELETE[Xóa conversation] --> MONGO
```

Message người dùng đang chờ phản hồi không được đưa vào `history`; câu hỏi hiện tại
không bị lặp lại. Next.js và Django cùng từ chối history vượt quá sáu message, và
`SemanticInterpreter` dùng history để giải tham chiếu trước khi router chọn handler.
Tọa độ GPS và audio microphone không được lưu trong conversation. Nút **Cuộc trò
chuyện mới** chỉ xóa state đang mở; xóa một conversation đã lưu là thao tác API riêng.

### 10. Speech-to-text với Gemini Live

Speech-to-text dùng model `gemini-3.5-transcribe-live`, chế độ `SMART` cho tiếng Việt
`vi-VN`. API key Gemini Live chỉ nằm ở ASP.NET Core; browser nhận ephemeral token
ngắn hạn, một lần dùng qua Next.js proxy rồi kết nối WebSocket trực tiếp tới Gemini.

```mermaid
flowchart LR
    MIC[Người dùng bấm Nói] --> PERMISSION[Trình duyệt xin quyền microphone]
    PERMISSION --> WORKLET[AudioWorklet chuyển âm thanh thành PCM16 mono 16 kHz]

    FE[Frontend đã đăng nhập] -->|POST /api/speech-token| NEXT[Next.js proxy]
    NEXT -->|Bearer token| NET[ASP.NET Core]
    NET -->|API key server-side, POST auth_tokens| TOKEN[Gemini v1alpha]
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

### 11. Luồng hiển thị kết quả trên frontend

```mermaid
flowchart TD
    RESPONSE[answer, sources, places,<br/>itinerary, itineraryOperation] --> VALIDATE[Kiểm tra runtime contract]
    VALIDATE --> CHAT[Hiển thị câu trả lời, nguồn và thẻ POI]
    VALIDATE --> PLACES{Có places hợp lệ?}
    PLACES -->|Có| MARKER[Tạo marker POI trên Mapbox GL]
    MARKER --> INTERACT[Hover làm nổi bật;<br/>click để focus bản đồ]
    VALIDATE --> ROUTE{Có persisted itinerary hợp lệ?}
    ROUTE -->|Có| LINE[Vẽ GeoJSON LineString]
    ROUTE -->|Có| STOP_MARKERS[Tạo marker điểm dừng đánh số]
    LINE --> FIT[Fit bản đồ theo route và các điểm dừng]
    STOP_MARKERS --> FIT
    VALIDATE --> COMPLETE[Ghép lượt user + assistant hoàn chỉnh]
    COMPLETE --> SAVE[Lưu conversation qua ASP.NET Core]
```

Frontend không lưu tọa độ GPS chính xác hoặc audio microphone vào conversation.

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
