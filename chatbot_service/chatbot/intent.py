"""Stable intent taxonomy for the travel question-answering chatbot."""

from enum import Enum


class TravelIntent(str, Enum):
    """The single primary intent assigned to one user message."""

    DESTINATION_DISCOVERY = "destination_discovery"
    PLACE_SEARCH = "place_search"
    PLACE_DETAILS = "place_details"
    TRAVEL_QA = "travel_qa"
    ITINERARY_MAKING = "itinerary_making"
    ITINERARY_MANAGEMENT = "itinerary_management"
    ITINERARY_ADVICE = "itinerary_advice"
    TRANSPORTATION_QA = "transportation_qa"
    BUDGET_QA = "budget_qa"
    CONTEXT_FOLLOW_UP = "context_follow_up"
    GENERAL_CHAT = "general_chat"
    UNSUPPORTED_CAPABILITY = "unsupported_capability"


INTENT_DESCRIPTIONS: dict[TravelIntent, str] = {
    TravelIntent.DESTINATION_DISCOVERY: (
        "Gợi ý hoặc so sánh điểm đến theo thời gian, sở thích, nhóm đi và ngân sách."
    ),
    TravelIntent.PLACE_SEARCH: (
        "Tìm địa điểm, POI, nhà hàng, quán cafe, nơi lưu trú hoặc tiện ích."
    ),
    TravelIntent.PLACE_DETAILS: (
        "Hỏi thông tin về một địa điểm cụ thể như địa chỉ, giờ mở cửa hoặc liên hệ."
    ),
    TravelIntent.TRAVEL_QA: (
        "Hỏi đáp kiến thức, kinh nghiệm, văn hóa, thời điểm đi hoặc chuẩn bị chuyến đi."
    ),
    TravelIntent.ITINERARY_MAKING: (
        "Tạo một lịch trình cụ thể có các địa điểm theo thứ tự để chuẩn bị tính và hiển thị route."
    ),
    TravelIntent.ITINERARY_MANAGEMENT: (
        "Xem, thêm, xóa, thay thế hoặc sắp xếp điểm dừng trong một lịch trình đang tồn tại."
    ),
    TravelIntent.ITINERARY_ADVICE: (
        "Tư vấn tạo hoặc điều chỉnh lịch trình dạng văn bản, không lưu hay tính route."
    ),
    TravelIntent.TRANSPORTATION_QA: (
        "Tư vấn phương tiện, khoảng cách hoặc cách di chuyển ở mức hỏi đáp."
    ),
    TravelIntent.BUDGET_QA: (
        "Tư vấn, so sánh hoặc ước tính ngân sách và chi phí chuyến đi."
    ),
    TravelIntent.CONTEXT_FOLLOW_UP: (
        "Câu hỏi phụ thuộc vào lịch sử hội thoại hoặc kết quả đã nhắc trước đó."
    ),
    TravelIntent.GENERAL_CHAT: (
        "Chào hỏi hoặc hội thoại chung không cần dữ liệu du lịch hay tool."
    ),
    TravelIntent.UNSUPPORTED_CAPABILITY: (
        "Yêu cầu cần tính năng chưa có như chỉ đường trực tiếp, giao thông thời gian "
        "thực hoặc lưu dữ liệu người dùng."
    ),
}


__all__ = ["INTENT_DESCRIPTIONS", "TravelIntent"]
