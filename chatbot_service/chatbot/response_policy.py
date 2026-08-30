"""Intent-grouped evidence priorities for final answer synthesis."""

from __future__ import annotations

from chatbot.intent import TravelIntent


DESTINATION_DISCOVERY_POLICY = """Chính sách evidence cho nhóm khám phá điểm đến:
- Ưu tiên: Knowledge Base liên quan, matchedCandidates đã được backend xác minh,
  rồi additionalMapboxPlaces để bổ sung.
- Chỉ đề xuất tên có trong hai danh sách trên. Không thêm địa điểm khác; nếu
  destinationResolved=false hoặc cả hai danh sách rỗng, nói chưa đủ dữ liệu.
- matchedCandidates cung cấp dữ liệu đã xác minh gồm tên, Mapbox ID, địa chỉ,
  category, lý do, khoảng cách, ETA, rating và popularity. Chỉ dùng giá trị có sẵn.
- Chọn và xếp chung các nơi phù hợp nhất; không liệt kê máy móc hoặc chia nhóm theo
  nguồn. Tổng hợp, so sánh và viết nhận định tự nhiên thay vì chép lại dữ liệu.
- Có thể dùng kiến thức ổn định để giải thích trải nghiệm, nhưng không dùng nó để
  tạo thêm địa điểm hoặc dữ liệu có thể thay đổi.
"""

MAPBOX_FIRST_POLICY = """Chính sách evidence cho nhóm tìm kiếm và thông tin địa điểm:
- Chỉ đề xuất địa điểm có mapboxId trong mapbox.places; Knowledge Base chỉ bổ sung
  bối cảnh ổn định và không được mâu thuẫn với dữ liệu Mapbox.
- mapbox.destinationLocations chỉ là anchor dùng để định vị khu vực, không phải địa
  điểm được phép đề xuất.
- Chỉ nói "chưa tìm thấy" khi mapbox.success=true nhưng mapbox.places rỗng. Nếu
  mapbox.success=false, nói "chưa thể lấy dữ liệu".
- Nếu destinationLocations rỗng nhưng mapbox.places có dữ liệu, vẫn dùng các địa
  điểm đó. Không suy đoán địa điểm thay thế.
"""

RAG_FIRST_ADVICE_POLICY = """Chính sách evidence cho nhóm hỏi đáp và tư vấn du lịch:
- Ưu tiên Knowledge Base, sau đó dùng kiến thức ổn định; dữ liệu provider chỉ bổ sung.
- Không biến kết quả provider thành trọng tâm của câu hỏi tư vấn và không tự tạo
  dữ liệu có thể thay đổi.
"""

ITINERARY_MAKING_POLICY = """Chính sách evidence cho xây dựng lịch trình có tuyến đường:
- Chỉ dùng itinerary khi success=true; giữ nguyên đúng thứ tự, tên và dữ liệu điểm dừng do backend trả về.
- Chỉ nói tuyến đã được tối ưu khi có itinerary và route geometry hợp lệ. Không tự tạo điểm dừng,
  thứ tự, khoảng cách, thời gian hay hình học tuyến đường.
- Khi success=false, nói rõ chưa thể xây dựng tuyến tối ưu và dựa vào errorCode để giải thích ngắn gọn;
  không biến verifiedStops thành một tuyến đã tối ưu.
- Không tuyên bố lịch trình đã được lưu nếu success=false.
"""

ITINERARY_MANAGEMENT_POLICY = """Chính sách evidence cho thay đổi lịch trình đã lưu:
- Chỉ xác nhận đã thêm, xóa hoặc cập nhật khi success=true và itinerary hợp lệ.
- Giữ nguyên tên, thứ tự, route, khoảng cách và thời gian backend trả về.
- Với missing_active_itinerary, yêu cầu người dùng tạo hoặc mở một lịch trình trước.
- Với place_not_uniquely_resolved, yêu cầu làm rõ địa điểm; không tự chọn ứng viên.
- Với duplicate_stop hoặc version_conflict, giải thích đúng lỗi và không tuyên bố đã lưu.
- Khi success=false, không mô tả mutation như đã hoàn thành.
"""

_MAPBOX_FIRST_INTENTS = frozenset(
    {
        TravelIntent.PLACE_SEARCH,
        TravelIntent.PLACE_DETAILS,
    }
)
_RAG_FIRST_ADVICE_INTENTS = frozenset(
    {
        TravelIntent.TRAVEL_QA,
        TravelIntent.ITINERARY_ADVICE,
        TravelIntent.TRANSPORTATION_QA,
        TravelIntent.BUDGET_QA,
    }
)


def response_policy_for(intent: TravelIntent) -> str | None:
    """Return exactly one evidence policy for the primary intent, if needed."""
    if intent == TravelIntent.DESTINATION_DISCOVERY:
        return DESTINATION_DISCOVERY_POLICY
    if intent == TravelIntent.ITINERARY_MAKING:
        return ITINERARY_MAKING_POLICY
    if intent == TravelIntent.ITINERARY_MANAGEMENT:
        return ITINERARY_MANAGEMENT_POLICY
    if intent in _MAPBOX_FIRST_INTENTS:
        return MAPBOX_FIRST_POLICY
    if intent in _RAG_FIRST_ADVICE_INTENTS:
        return RAG_FIRST_ADVICE_POLICY
    return None


__all__ = [
    "DESTINATION_DISCOVERY_POLICY",
    "ITINERARY_MAKING_POLICY",
    "ITINERARY_MANAGEMENT_POLICY",
    "MAPBOX_FIRST_POLICY",
    "RAG_FIRST_ADVICE_POLICY",
    "response_policy_for",
]
