"""Intent-grouped evidence priorities for final answer synthesis."""

from __future__ import annotations

from chatbot.intent import TravelIntent


DESTINATION_DISCOVERY_POLICY = """Chính sách evidence cho nhóm khám phá điểm đến:
- Ưu tiên nội dung theo thứ tự: (1) Knowledge Base liên quan, (2) ứng viên nổi tiếng từ kiến thức ổn định của mô hình đã được backend đối chiếu, (3) Mapbox Category Search chỉ để bổ sung.
- Chỉ đề xuất địa điểm xuất hiện trong matchedCandidates hoặc additionalMapboxPlaces và có mapboxId; không đưa các ứng viên bị loại vào câu trả lời.
- Nếu Knowledge Base có thông tin phù hợp, dùng nó làm nền tảng nhưng chỉ nhắc tên địa điểm khi địa điểm đó đã được đối chiếu và có mapboxId.
- Không liệt kê máy móc tất cả kết quả bổ sung. Chỉ chọn địa điểm phù hợp rõ với câu hỏi hoặc làm câu trả lời hữu ích hơn.
- Xếp tất cả địa điểm được chọn vào một danh sách thống nhất theo độ phù hợp với câu hỏi; không tách nhóm "Bên cạnh đó" chỉ vì địa điểm đến từ nguồn evidence bổ sung.
- Mỗi "Điểm nổi bật" phải ngắn, cụ thể và giúp người dùng hiểu vì sao nên chọn địa điểm đó; tránh lặp lại các cụm chung chung như "nổi tiếng" hoặc "hấp dẫn" cho mọi nơi.
- Không tự tạo dữ liệu có thể thay đổi như địa chỉ, tọa độ, rating, giờ mở cửa, điện thoại hoặc website.
- Nếu destinationResolved=false hoặc cả hai danh sách địa điểm đều rỗng, nói rõ chưa thể đối chiếu dữ liệu địa điểm và không tự đề xuất địa điểm thay thế.
"""

MAPBOX_FIRST_POLICY = """Chính sách evidence cho nhóm tìm kiếm và thông tin địa điểm:
- Mapbox là nguồn chính để xác định địa điểm và các dữ liệu có thể thay đổi.
- Chỉ đề xuất địa điểm có mapboxId trong data.results phù hợp với yêu cầu; không thêm địa điểm khác bằng kiến thức riêng của mô hình.
- Knowledge Base chỉ bổ sung bối cảnh ổn định khi liên quan và không được mâu thuẫn với dữ liệu địa điểm từ Mapbox.
- Nếu Mapbox trả empty hoặc failed, nói rõ chưa tìm thấy hoặc chưa thể lấy dữ liệu; không suy đoán địa điểm thay thế.
"""

RAG_FIRST_ADVICE_POLICY = """Chính sách evidence cho nhóm hỏi đáp và tư vấn du lịch:
- Ưu tiên theo thứ tự: (1) Knowledge Base liên quan, (2) kiến thức ổn định và đáng tin cậy của mô hình, (3) dữ liệu provider chỉ để bổ sung khi có.
- Không biến kết quả provider thành trọng tâm nếu câu hỏi chủ yếu cần giải thích, kinh nghiệm, ngân sách, phương tiện hoặc lịch trình.
- Không tự tạo dữ liệu có thể thay đổi như giá hiện tại, giờ mở cửa, rating, tọa độ, điện thoại hoặc website.
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
