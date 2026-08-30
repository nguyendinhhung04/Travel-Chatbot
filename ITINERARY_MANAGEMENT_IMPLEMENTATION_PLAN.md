# Kế hoạch triển khai Itinerary Management

## 1. Mục tiêu

Hỗ trợ các yêu cầu thay đổi một lịch trình đang tồn tại, trước mắt là:

> Thêm địa điểm Công viên Yên Sở vào lịch trình.

Hệ thống phải xác định đúng đây là thao tác quản lý lịch trình, tìm và xác minh
địa điểm, cập nhật các điểm dừng, tối ưu lại tuyến đường, lưu trạng thái mới và
trả itinerary đã cập nhật cho frontend.

Không được trả HTTP 503 chỉ vì Gemini tạo ra một cặp intent/action không hợp lệ.

## 2. Phạm vi và giả định

- `itinerary_making` tiếp tục dùng để tạo một lịch trình mới.
- Thêm `itinerary_management` cho các thao tác trên lịch trình đã tồn tại.
- ASP.NET Core sở hữu persistence và mutation của itinerary.
- Django sở hữu semantic interpretation, xác minh ứng viên và orchestration.
- Frontend sở hữu `active_itinerary_id`, hiển thị tuyến và gửi context cần thiết.
- Ordinary `place_search` không được tự động lưu hoặc thay đổi itinerary.
- Kế hoạch ưu tiên vertical slice `ADD_STOP`; các thao tác khác triển khai sau.
- Cần xác nhận lại lựa chọn MongoDB trước khi bắt đầu phần persistence.
- Worktree hiện có nhiều thay đổi chưa commit; phải giữ nguyên mọi thay đổi không
  thuộc task và không merge/rebase tự động.

## 3. Taxonomy đề xuất

### Intent

```text
itinerary_making
itinerary_management
context_follow_up
```

### Action

```text
make_itinerary
show_itinerary
add_itinerary_stop
remove_itinerary_stop
update_itinerary
reorder_itinerary_stops
```

### Quy tắc phân loại

| Câu hỏi | Intent | Action |
|---|---|---|
| Lập lịch trình Hà Nội 2 ngày | `itinerary_making` | `make_itinerary` |
| Thêm Công viên Yên Sở vào lịch trình | `itinerary_management` | `add_itinerary_stop` |
| Xóa điểm thứ hai | `itinerary_management` | `remove_itinerary_stop` |
| Đổi điểm thứ hai thành Văn Miếu | `itinerary_management` | `update_itinerary` |
| Cho điểm A lên trước điểm B | `itinerary_management` | `reorder_itinerary_stops` |
| Ở đó có gì hay? | `context_follow_up` | Action đọc dữ liệu phù hợp |

Quy tắc ưu tiên:

1. Khi nhận diện được thao tác nghiệp vụ thêm, xóa, sửa hoặc sắp xếp, dùng
   `itinerary_management` dù câu hỏi phụ thuộc vào history.
2. Chỉ dùng `context_follow_up` khi không có intent nghiệp vụ cụ thể hơn.
3. `make_itinerary` chỉ hợp lệ với `itinerary_making`.
4. Các action quản lý chỉ hợp lệ với `itinerary_management`.
5. Thiếu itinerary đang hoạt động phải trả `needs_clarification`, không tự tạo
   itinerary mới.

## 4. Contract mục tiêu

### Chat request

```json
{
  "message": "Thêm Công viên Yên Sở vào lịch trình",
  "history": [],
  "active_itinerary_id": "itinerary-id",
  "active_itinerary_version": 3
}
```

Không dùng history làm nguồn xác định itinerary ID. History chỉ hỗ trợ giải tham
chiếu ngôn ngữ.

### Semantic interpretation

```json
{
  "primary_intent": "itinerary_management",
  "entities": {
    "places": ["Công viên Yên Sở"]
  },
  "itinerary_context": {
    "active_itinerary_id": "itinerary-id",
    "expected_version": 3,
    "target_stop_index": null,
    "add_position": "append"
  },
  "actions": [
    {"type": "add_itinerary_stop"}
  ],
  "missing_information": [],
  "status": "supported"
}
```

### Chat response

```json
{
  "answer": "Đã thêm Công viên Yên Sở vào lịch trình.",
  "places": [],
  "itinerary": {},
  "itineraryOperation": {
    "type": "add_stop",
    "success": true
  }
}
```

Gemini chỉ được nói thao tác đã thành công khi backend trả `success=true` và có
itinerary hợp lệ.

## 5. Các phase triển khai

### Phase 0 — Đối chiếu code và bảo vệ worktree

- Kiểm kê các thay đổi hiện tại liên quan đến `itinerary_making`.
- Đối chiếu thiết kế itinerary management trước đây với branch hiện tại.
- Xác định phần có thể phục hồi và phần phải triển khai lại.
- Không ghi đè các file đang có thay đổi của người dùng.
- Chốt persistence store, owner mặc định và quy tắc chọn active itinerary.

**Đầu ra:** danh sách file sẽ sửa/thêm và contract đã được chốt.

### Phase 1 — Semantic schema và regression cho lỗi hiện tại

Các khu vực dự kiến:

```text
chatbot_service/chatbot/intent.py
chatbot_service/chatbot/semantic.py
chatbot_service/chatbot/tests/test_intent.py
chatbot_service/chatbot/tests/test_semantic.py
```

Công việc:

- Thêm `TravelIntent.ITINERARY_MANAGEMENT`.
- Thêm các action quản lý itinerary.
- Thêm `SemanticItineraryContext` chứa itinerary ID, version, stop index và vị
  trí cần chèn.
- Cập nhật prompt bằng ví dụ rõ ràng cho create/add/remove/update/reorder.
- Quy định business intent ưu tiên hơn `context_follow_up`.
- Bổ sung validator cho các cặp intent/action.
- Xử lý output semantic sai bằng một retry có validation feedback hoặc một bước
  normalization có giới hạn cho những trường hợp an toàn.
- Không chuyển mọi `OutputParserException` thành lỗi dịch vụ chung không rõ
  nguyên nhân.

**Acceptance:** câu “Thêm địa điểm Công viên Yên Sở vào lịch trình” không còn tạo
`context_follow_up + make_itinerary`.

### Phase 2 — Truyền active itinerary qua chat API

Các khu vực dự kiến:

```text
frontend/src/components/chat-window.tsx
frontend/src/app/api/chat/route.ts
chatbot_service/chatbot/serializers.py
chatbot_service/chatbot/views.py
chatbot_service/chatbot/orchestrator.py
chatbot_service/chatbot/semantic.py
```

Công việc:

- Frontend gửi `active_itinerary_id` và `active_itinerary_version`.
- Next.js validate và forward hai trường trên.
- Django serializer validate ID và version.
- Orchestrator chuyển context cho semantic interpreter và pipeline.
- Không chèn ID vào nội dung prompt tự do nếu có thể truyền dưới dạng structured
  context.

**Acceptance:** ID/version đi xuyên suốt frontend → Next.js → Django mà không bị
mất hoặc lấy từ history.

### Phase 3 — ASP.NET persistence và mutation

Các thành phần dự kiến:

```text
backend/backend/Itineraries/
backend/backend/Controllers/ItinerariesController.cs
backend/backend/Controllers/RouteToolsController.cs
backend/backend.Tests/
```

Công việc:

- Định nghĩa `Itinerary`, `ItineraryStop`, route và version.
- Tạo repository/service cho persistence.
- Cung cấp API load, add, remove, update và reorder.
- Dùng optimistic concurrency để tránh ghi đè phiên bản cũ.
- Với mutation, tạo bản itinerary tạm và tối ưu route trước khi persist.
- Không ghi dữ liệu nếu Mapbox Optimization thất bại.
- Từ chối POI trùng `mapboxId`, itinerary không tồn tại và số stop không hợp lệ.
- Ánh xạ lỗi rõ ràng:
  - `404`: itinerary không tồn tại.
  - `409`: version conflict hoặc duplicate.
  - `422`: mutation không hợp lệ.
  - `503`: provider/persistence thực sự không khả dụng.

**Acceptance:** thêm stop thành công tạo một version mới; lỗi optimization không
làm thay đổi document đã lưu.

### Phase 4 — Django typed tools và ItineraryManagementPipeline

Các khu vực dự kiến:

```text
chatbot_service/chatbot/itinerary_management.py
chatbot_service/chatbot/tools/models.py
chatbot_service/chatbot/tools/mapbox_client.py
chatbot_service/chatbot/tools/registry.py
chatbot_service/chatbot/tool_planner.py
chatbot_service/chatbot/orchestrator.py
```

Typed operations dự kiến:

```text
get_active_itinerary
add_itinerary_stop
remove_itinerary_stop
update_itinerary
reorder_itinerary_stops
```

Luồng `ADD_STOP`:

```text
SemanticInterpretation
→ tải itinerary hiện tại
→ tìm POI bằng Mapbox
→ kiểm tra unresolved/ambiguous
→ kiểm tra duplicate
→ gọi ASP.NET add-stop
→ ASP.NET tối ưu và persist
→ trả itinerary đã cập nhật
```

Nguyên tắc:

- Tách `ItineraryManagementPipeline` khỏi `ItineraryMakingPipeline`.
- `plan_tools()` chỉ lập các bước tìm kiếm/đọc phù hợp; mutation phải nằm trong
  pipeline có validation.
- Không gửi POI chưa xác minh tới persistence.
- Không tự chọn ứng viên khi nhiều kết quả mơ hồ.

**Acceptance:** mutation chỉ chạy khi có itinerary hợp lệ và POI đã được xác minh.

### Phase 5 — Orchestrator và response policy

Công việc:

- Thêm nhánh `ITINERARY_MANAGEMENT` trong `ChatOrchestrator.answer()`.
- Trả `itinerary` và `itineraryOperation` theo contract.
- Chỉ tuyên bố “đã thêm/đã xóa/đã cập nhật” khi backend xác nhận thành công.
- Với missing itinerary, ambiguous place hoặc version conflict, trả lời hướng dẫn
  phù hợp thay vì thông báo thành công giả.
- Giữ ordinary `PLACE_SEARCH` hoàn toàn tách khỏi persistence.

**Acceptance:** response text, response metadata và dữ liệu đã lưu luôn nhất quán.

### Phase 6 — Frontend active itinerary và UI

Công việc:

- Lưu `activeItineraryId` và `version` trong state phù hợp.
- Load itinerary đang hoạt động khi mở/refresh trang.
- Sau mutation, thay route, stop list và marker bằng response mới.
- Đánh số marker theo thứ tự backend trả về.
- Hover/click stop phải focus đúng marker.
- Với `409`, reload itinerary mới nhất và thông báo người dùng thử lại.
- Không persist GPS trong conversation storage.

**Acceptance:** sau câu lệnh thêm Yên Sở, route, ordered stops và markers cập nhật
cùng một lần, không cần refresh.

### Phase 7 — Kiểm thử

#### Django

- Intent/action validator.
- Exact regression cho câu hỏi Yên Sở có history.
- Có và không có `active_itinerary_id`.
- Gemini trả intent/action mâu thuẫn.
- POI unresolved, ambiguous và duplicate.
- Backend mutation thành công, conflict và unavailable.
- Orchestrator không tuyên bố thành công khi mutation lỗi.

#### ASP.NET

- Repository/service CRUD.
- Add/remove/update/reorder.
- Optimistic concurrency.
- Duplicate stop và giới hạn stop.
- Optimization failure không ghi database.
- HTTP status/error contract.

#### Frontend

- Validate và forward ID/version.
- Áp dụng itinerary version mới từ response.
- Ordered stops, route và marker đồng bộ.
- Chạy lint và production build.

#### Playwright

- Thêm E2E cho luồng tạo/load itinerary → thêm Yên Sở → UI cập nhật.
- Mock Gemini, Mapbox và mutation API tại HTTP boundary để test deterministic.
- Dùng Microsoft Edge project đã cấu hình.
- Chỉ chạy `cd frontend && npm run test:e2e` khi người dùng yêu cầu rõ ràng.

#### Live smoke test

- Báo cáo riêng với mocked/local suites.
- Chỉ xác nhận Atlas/Mapbox live khi đã chạy bằng credential hợp lệ.
- Không log hoặc commit connection string/token.

## 6. Thứ tự delivery đề xuất

1. Semantic contract và regression test cho lỗi hiện tại.
2. `active_itinerary_id` và version xuyên suốt chat request.
3. ASP.NET mutation contract tối thiểu cho `ADD_STOP`.
4. Django `ItineraryManagementPipeline` cho `ADD_STOP`.
5. Frontend cập nhật itinerary sau mutation.
6. Unit, integration, lint và build.
7. Thêm Playwright coverage; chỉ chạy khi được yêu cầu.
8. Mở rộng `REMOVE_STOP`.
9. Mở rộng update/reorder và UI quản lý đầy đủ.
10. Live Atlas/Mapbox smoke test.

## 7. Definition of Done cho vertical slice ADD_STOP

Task `ADD_STOP` chỉ hoàn thành khi:

- Câu “Thêm Công viên Yên Sở vào lịch trình” được phân loại thành
  `itinerary_management + add_itinerary_stop`.
- Thiếu active itinerary tạo clarification, không tạo mới ngầm định.
- Công viên Yên Sở được Mapbox xác minh và không mơ hồ.
- Duplicate được phát hiện trước persistence.
- Route được tối ưu trước khi lưu.
- Optimization thất bại không ghi đè itinerary hiện tại.
- Response trả itinerary/version mới và chỉ báo operation thành công.
- Frontend cập nhật route, thứ tự stop và marker mà không cần refresh.
- Unit/integration/lint/build liên quan đều pass.
- Playwright coverage đã được thêm; kết quả chạy E2E chỉ được báo khi người dùng
  yêu cầu thực thi.
- Mocked validation và live-provider validation được báo cáo tách biệt.

## 8. Ngoài phạm vi vertical slice đầu tiên

- Authentication và itinerary riêng cho nhiều user thật.
- Collaborative editing.
- Undo/redo nhiều bước.
- Offline synchronization.
- Tối ưu lịch trình nhiều ngày theo time window phức tạp.
- Điều hướng hoặc giao thông thời gian thực.
