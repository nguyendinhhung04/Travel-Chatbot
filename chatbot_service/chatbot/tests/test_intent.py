"""Tests and labelled evaluation cases for the travel intent taxonomy."""

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from chatbot.intent import INTENT_DESCRIPTIONS, TravelIntent


I = TravelIntent

INTENT_CASES: tuple[tuple[str, TravelIntent], ...] = (
    ("Cuối tuần này tôi nên đi đâu gần Hà Nội?", I.DESTINATION_DISCOVERY),
    ("Tôi có 3 ngày 2 đêm thì nên đi Đà Nẵng hay Nha Trang?", I.DESTINATION_DISCOVERY),
    ("Tháng 9 đi Đà Lạt có ổn không?", I.TRAVEL_QA),
    ("Tôi muốn đi nơi nào mát, ít đông và chi phí khoảng 3 triệu.", I.DESTINATION_DISCOVERY),
    ("Có địa điểm nào phù hợp cho nhóm 4 người không?", I.DESTINATION_DISCOVERY),
    ("Tôi thích thiên nhiên hơn khu vui chơi, gợi ý cho tôi vài nơi.", I.DESTINATION_DISCOVERY),
    ("Tôi đi cùng bố mẹ, nên chọn địa điểm nào đỡ phải đi bộ nhiều?", I.DESTINATION_DISCOVERY),
    ("Đà Nẵng có những địa điểm nào đáng đi?", I.PLACE_SEARCH),
    ("Bà Nà Hills có đáng đi không?", I.PLACE_DETAILS),
    ("Có quán cafe view biển nào đẹp không?", I.PLACE_SEARCH),
    ("Tìm cho tôi các quán ăn gần Mỹ Khê.", I.PLACE_SEARCH),
    ("Có những địa điểm nào miễn phí?", I.PLACE_SEARCH),
    ("Chỗ nào phù hợp để ngắm hoàng hôn?", I.PLACE_SEARCH),
    ("Buổi tối ở Đà Nẵng có gì chơi?", I.PLACE_SEARCH),
    ("Từ Mỹ Khê đến Hội An mất bao lâu?", I.TRANSPORTATION_QA),
    ("Các điểm này có gần nhau không?", I.TRANSPORTATION_QA),
    ("Đi Grab hay thuê xe máy sẽ hợp lý hơn?", I.TRANSPORTATION_QA),
    ("Lập lịch trình Đà Nẵng 3 ngày 2 đêm cho tôi.", I.ITINERARY_ADVICE),
    ("Tôi đến sân bay lúc 9 giờ sáng thứ Sáu và về lúc 8 giờ tối Chủ nhật.", I.ITINERARY_ADVICE),
    ("Đừng xếp lịch quá dày.", I.ITINERARY_ADVICE),
    ("Mỗi ngày tôi chỉ muốn đi khoảng 3–4 địa điểm.", I.ITINERARY_ADVICE),
    ("Tôi muốn dành một ngày cho Hội An.", I.ITINERARY_ADVICE),
    ("Ưu tiên các địa điểm gần nhau.", I.ITINERARY_ADVICE),
    ("Xếp đường đi sao cho đỡ phải quay lại.", I.ITINERARY_ADVICE),
    ("Cho tôi ăn trưa ở gần địa điểm đang tham quan.", I.ITINERARY_ADVICE),
    ("Thêm một quán cafe vào chiều ngày 2.", I.ITINERARY_ADVICE),
    ("Bỏ Bà Nà Hills ra.", I.ITINERARY_ADVICE),
    ("Đổi Hội An từ ngày 2 sang ngày 3.", I.ITINERARY_ADVICE),
    ("Ngày đầu tôi muốn nghỉ đến 2 giờ chiều rồi mới đi.", I.ITINERARY_ADVICE),
    ("Tối nào cũng muốn về khách sạn trước 11 giờ.", I.ITINERARY_ADVICE),
    ("Lịch trình này có quá mệt không?", I.ITINERARY_ADVICE),
    ("Chuyến này khoảng bao nhiêu tiền?", I.BUDGET_QA),
    ("4 triệu/người có đủ không?", I.BUDGET_QA),
    ("Tính chi phí cho 2 người giúp tôi.", I.BUDGET_QA),
    ("Không tính vé máy bay thì hết khoảng bao nhiêu?", I.BUDGET_QA),
    ("Địa điểm nào trong lịch trình phải mua vé?", I.BUDGET_QA),
    ("Có thể thay Bà Nà Hills bằng chỗ rẻ hơn không?", I.BUDGET_QA),
    ("Tôi chỉ còn 1 triệu cho 2 ngày cuối, chỉnh lại lịch trình giúp tôi.", I.BUDGET_QA),
    ("Ăn ở đâu vừa ngon vừa không quá 150 nghìn/người?", I.PLACE_SEARCH),
    ("Thuê xe máy hay đi taxi rẻ hơn?", I.BUDGET_QA),
    ("Ngày mai tôi đi rồi, có cần chuẩn bị gì không?", I.TRAVEL_QA),
    ("Tôi cần mang những gì?", I.TRAVEL_QA),
    ("Đà Nẵng cuối tuần này có mưa không?", I.TRAVEL_QA),
    ("Nếu trời mưa thì lịch trình hiện tại có vấn đề gì?", I.ITINERARY_ADVICE),
    ("Nhắc lại lịch trình ngày mai cho tôi.", I.ITINERARY_ADVICE),
    ("Ngày mai tôi cần dậy lúc mấy giờ?", I.ITINERARY_ADVICE),
    ("Điểm đầu tiên cách khách sạn bao xa?", I.TRANSPORTATION_QA),
    ("Tôi nên xuất phát lúc mấy giờ để kịp?", I.TRANSPORTATION_QA),
    ("Có địa điểm nào cần đặt vé trước không?", I.TRAVEL_QA),
    ("Kiểm tra xem lịch trình có địa điểm nào đang đóng cửa không?", I.PLACE_DETAILS),
    ("Hôm nay tôi đi đâu?", I.ITINERARY_ADVICE),
    ("Điểm tiếp theo là đâu?", I.ITINERARY_ADVICE),
    ("Từ đây đến đó mất bao lâu?", I.TRANSPORTATION_QA),
    ("Chỉ đường đến đó.", I.UNSUPPORTED_CAPABILITY),
    ("Tôi đang ở gần cầu Rồng, quanh đây có gì?", I.PLACE_SEARCH),
    ("Có quán cafe nào trong bán kính 1 km không?", I.PLACE_SEARCH),
    ("Tìm quán ăn gần tôi.", I.PLACE_SEARCH),
    ("Tôi muốn ăn mì Quảng.", I.PLACE_SEARCH),
    ("Quán nào đang mở?", I.PLACE_DETAILS),
    ("Chỗ nào có đánh giá tốt nhưng không quá đắt?", I.PLACE_SEARCH),
    ("Tôi dậy muộn mất rồi.", I.ITINERARY_ADVICE),
    ("Bây giờ 11 giờ rồi, chỉnh lại lịch trình hôm nay.", I.ITINERARY_ADVICE),
    ("Tôi không muốn đi Bà Nà nữa.", I.ITINERARY_ADVICE),
    ("Ở đây đẹp nên tôi muốn ở thêm một tiếng.", I.ITINERARY_ADVICE),
    ("Bỏ điểm tiếp theo đi.", I.ITINERARY_ADVICE),
    ("Chuyển nó sang ngày mai.", I.ITINERARY_ADVICE),
    ("Tôi mệt rồi, còn địa điểm nào gần khách sạn không?", I.PLACE_SEARCH),
    ("Tôi muốn về khách sạn nghỉ 2 tiếng rồi đi tiếp.", I.ITINERARY_ADVICE),
    ("Tối nay tôi muốn đi Hội An thay vì ngày mai.", I.ITINERARY_ADVICE),
    ("Trời đang mưa, giờ đi đâu?", I.PLACE_SEARCH),
    ("Bà Nà Hills đóng cửa thì thay bằng đâu?", I.PLACE_SEARCH),
    ("Quán này hết chỗ rồi, tìm quán khác gần đây.", I.PLACE_SEARCH),
    ("Đường này đang tắc, có cách nào khác không?", I.UNSUPPORTED_CAPABILITY),
    ("Tôi bị chậm 2 tiếng so với lịch.", I.ITINERARY_ADVICE),
    ("Điểm tiếp theo đóng cửa lúc 5 giờ mà giờ đã 4 giờ 30.", I.ITINERARY_ADVICE),
    ("Tôi đang ở sai phía thành phố, có nên đổi thứ tự các điểm không?", I.ITINERARY_ADVICE),
    ("Bạn tôi không muốn đi Hội An nữa.", I.ITINERARY_ADVICE),
    ("Xe máy bị hỏng nên giờ chỉ đi taxi.", I.TRANSPORTATION_QA),
    ("Tôi còn 500 nghìn cho hôm nay, chỉnh kế hoạch lại.", I.BUDGET_QA),
    ("Tìm quán cafe gần Mỹ Khê.", I.PLACE_SEARCH),
    ("Quán thứ hai trông ổn đấy.", I.CONTEXT_FOLLOW_UP),
    ("Thêm nó vào chiều mai.", I.ITINERARY_ADVICE),
    ("Hôm qua bạn gợi ý tôi một quán hải sản, quán đó tên gì?", I.CONTEXT_FOLLOW_UP),
    ("Điểm tiếp theo trong lịch của tôi là đâu?", I.CONTEXT_FOLLOW_UP),
    ("Cái nào gần tôi nhất?", I.CONTEXT_FOLLOW_UP),
    ("Đổi hai địa điểm đó cho nhau.", I.ITINERARY_ADVICE),
    ("Chuyến vừa rồi tôi đã đi những đâu?", I.CONTEXT_FOLLOW_UP),
    ("Tổng cộng tôi đã đi bao nhiêu địa điểm?", I.CONTEXT_FOLLOW_UP),
    ("Tôi đã bỏ những địa điểm nào trong lịch ban đầu?", I.CONTEXT_FOLLOW_UP),
    ("Tổng chi phí chuyến này khoảng bao nhiêu?", I.BUDGET_QA),
    ("Ngày nào tôi di chuyển nhiều nhất?", I.CONTEXT_FOLLOW_UP),
    ("Tạo lại hành trình thực tế mà tôi đã đi.", I.CONTEXT_FOLLOW_UP),
    ("Tạo bài chia sẻ chuyến Đà Nẵng của tôi.", I.CONTEXT_FOLLOW_UP),
    ("Lưu những quán tôi thích.", I.UNSUPPORTED_CAPABILITY),
    ("Lần sau nếu đi Hội An thì gợi ý dựa trên chuyến này.", I.CONTEXT_FOLLOW_UP),
    ("Tôi thích các quán kiểu quán cafe hôm trước, tìm thêm những chỗ tương tự.", I.CONTEXT_FOLLOW_UP),
    (
        "Tôi đang ở cầu Rồng, trời bắt đầu mưa và tôi còn khoảng 3 tiếng trước khi "
        "về khách sạn. Bỏ Sơn Trà khỏi lịch hôm nay và tìm cho tôi một quán cafe đẹp "
        "gần đây, sau đó chuyển Sơn Trà sang sáng mai.",
        I.ITINERARY_ADVICE,
    ),
)


class TravelIntentTests(SimpleTestCase):
    def test_catalog_contains_the_ten_question_answering_intents(self):
        self.assertEqual(len(TravelIntent), 10)
        self.assertEqual(set(INTENT_DESCRIPTIONS), set(TravelIntent))
        self.assertTrue(all(description.strip() for description in INTENT_DESCRIPTIONS.values()))

    def test_all_97_document_questions_have_one_label_in_document_order(self):
        document_questions = self._load_document_questions()
        labelled_questions = [question for question, _ in INTENT_CASES]

        self.assertEqual(len(INTENT_CASES), 97)
        self.assertEqual(labelled_questions, document_questions)
        self.assertEqual(len(labelled_questions), len(set(labelled_questions)))

    def test_every_case_uses_a_valid_primary_intent(self):
        for question, intent in INTENT_CASES:
            with self.subTest(question=question):
                self.assertTrue(question.strip())
                self.assertIsInstance(intent, TravelIntent)

    @staticmethod
    def _load_document_questions() -> list[str]:
        document_path = (
            Path(settings.BASE_DIR)
            / "docs"
            / "cau-hoi-nguoi-dung-app-du-lich-chatbot.md"
        )
        question_pattern = re.compile(r"^(?:-\s+|>\s+)“([^”]+)”")
        questions: list[str] = []

        for line in document_path.read_text(encoding="utf-8").splitlines():
            match = question_pattern.match(line)
            if match:
                questions.append(match.group(1))

        return questions
