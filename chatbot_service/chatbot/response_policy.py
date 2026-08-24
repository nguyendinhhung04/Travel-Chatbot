"""Intent-grouped evidence priorities for final answer synthesis."""

from __future__ import annotations

from chatbot.intent import TravelIntent


DESTINATION_DISCOVERY_POLICY = """Chính sách evidence cho nhóm khám phá điểm đến:
- Ưu tiên nội dung theo thứ tự: (1) Knowledge Base liên quan, (2) ứng viên nổi tiếng từ kiến thức ổn định của mô hình đã được backend đối chiếu, (3) Mapbox Category Search chỉ để bổ sung.
- Chỉ đề xuất địa điểm xuất hiện trong matchedCandidates hoặc additionalMapboxPlaces và có mapboxId; không đưa các ứng viên bị loại vào câu trả lời.
- Nếu Knowledge Base có thông tin phù hợp, dùng nó làm nền tảng nhưng chỉ nhắc tên địa điểm khi địa điểm đó đã được đối chiếu và có mapboxId.
- Không liệt kê máy móc tất cả kết quả bổ sung. Chỉ chọn địa điểm phù hợp rõ với câu hỏi hoặc làm câu trả lời hữu ích hơn.
- Xếp tất cả địa điểm được chọn vào một danh sách thống nhất theo độ phù hợp với câu hỏi; không tách nhóm "Bên cạnh đó" chỉ vì địa điểm đến từ nguồn evidence bổ sung.
- Không chỉ chép lại tên, địa chỉ, category hoặc lý do có sẵn trong context. Phải tổng hợp evidence, so sánh các lựa chọn và đưa ra nhận định tư vấn có ích bằng lời của một người am hiểu điểm đến.
- Review địa điểm bằng lời văn tự nhiên: nêu điều đáng chú ý, kiểu du khách phù hợp, hoàn cảnh nên ghé và điểm cần cân nhắc khi những ý đó thực sự hữu ích. Không bắt mọi địa điểm phải có đủ cùng một số ý hoặc cùng một độ dài.
- Đưa nhận định "đáng ghé", "nên ưu tiên", "chỉ hợp nếu..." hoặc "có thể bỏ qua" vào mạch văn thay vì tạo nhãn "Có nên đi:" lặp lại. Mức độ khẳng định phải dựa trên câu hỏi, evidence và sự phù hợp với nhu cầu người dùng.
- Có thể dùng kiến thức ổn định, đáng tin cậy của mô hình để nhận xét trải nghiệm và giải thích vì sao nên đi; không được dùng kiến thức riêng để tạo thêm địa điểm chưa được Mapbox đối chiếu hoặc tạo dữ liệu có thể thay đổi.
- Giọng văn phải nhiệt tình, có quan điểm và mang tính đồng hành. Ưu tiên những nhận xét cụ thể, thực tế; tránh giọng liệt kê cho có hoặc lặp lại các từ chung chung như "nổi tiếng", "hấp dẫn" cho mọi nơi.
- Khi câu hỏi đủ rộng và evidence phù hợp, có thể nhóm địa điểm theo trải nghiệm hoặc buổi trong ngày và gợi ý cách kết hợp thành lịch tham khảo. Không ép nhóm hoặc tạo lịch nếu một danh sách hay đoạn tư vấn tự nhiên phù hợp hơn; không tuyên bố lịch đó đã được tối ưu tuyến đường.
- Nếu lịch sử có tên hoặc sở thích của người dùng thì có thể gọi tên và cá nhân hóa. Không tự đoán tên, sở thích hoặc thời lượng chuyến đi khi chưa có dữ liệu.
- Không tự tạo dữ liệu có thể thay đổi như địa chỉ, tọa độ, rating, giờ mở cửa, điện thoại hoặc website.
- Nếu destinationResolved=false hoặc cả hai danh sách địa điểm đều rỗng, nói rõ chưa thể đối chiếu dữ liệu địa điểm và không tự đề xuất địa điểm thay thế.
"""

MAPBOX_FIRST_POLICY = """Chính sách evidence cho nhóm tìm kiếm và thông tin địa điểm:
- Mapbox là nguồn chính để xác định địa điểm và các dữ liệu có thể thay đổi.
- Chỉ đề xuất địa điểm có mapboxId trong data.results phù hợp với yêu cầu; không thêm địa điểm khác bằng kiến thức riêng của mô hình.
- Knowledge Base chỉ bổ sung bối cảnh ổn định khi liên quan và không được mâu thuẫn với dữ liệu địa điểm từ Mapbox.
- Chỉ nói "chưa tìm thấy địa điểm" khi các truy vấn Mapbox liên quan đã thành công (success=true) nhưng data.results rỗng.
- Nếu Mapbox failed (success=false) và không có kết quả thành công khác, phải nói "chưa thể lấy dữ liệu" và có thể diễn giải errorMessage ngắn gọn; không được nói Mapbox không có địa điểm.
- Nếu bước xác định tọa độ anchor không có kết quả nhưng Category Search bằng near trả về địa điểm, dùng các địa điểm đó và không tuyên bố tìm kiếm thất bại.
- Không suy đoán địa điểm thay thế.
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
