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
- Chỉ đề xuất địa điểm có mapboxId trong data.results; Knowledge Base chỉ bổ sung
  bối cảnh ổn định và không được mâu thuẫn với dữ liệu Mapbox.
- Chỉ nói "chưa tìm thấy" khi request thành công nhưng results rỗng. Nếu request
  thất bại và không có kết quả thành công khác, nói "chưa thể lấy dữ liệu".
- Nếu tìm tọa độ anchor không có kết quả nhưng tìm bằng near có kết quả, vẫn dùng
  kết quả đó. Không suy đoán địa điểm thay thế.
"""

RAG_FIRST_ADVICE_POLICY = """Chính sách evidence cho nhóm hỏi đáp và tư vấn du lịch:
- Ưu tiên Knowledge Base, sau đó dùng kiến thức ổn định; dữ liệu provider chỉ bổ sung.
- Không biến kết quả provider thành trọng tâm của câu hỏi tư vấn và không tự tạo
  dữ liệu có thể thay đổi.
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
    if intent in _MAPBOX_FIRST_INTENTS:
        return MAPBOX_FIRST_POLICY
    if intent in _RAG_FIRST_ADVICE_INTENTS:
        return RAG_FIRST_ADVICE_POLICY
    return None


__all__ = [
    "DESTINATION_DISCOVERY_POLICY",
    "MAPBOX_FIRST_POLICY",
    "RAG_FIRST_ADVICE_POLICY",
    "response_policy_for",
]
