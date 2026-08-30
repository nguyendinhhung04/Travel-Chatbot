"""Structured semantic interpretation for travel question-answering requests."""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from datetime import date
from enum import Enum
from typing import Annotated, Any, Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.exceptions import OutputParserException
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

from chatbot.intent import INTENT_DESCRIPTIONS, TravelIntent
from chatbot.rag.rag_chain import get_chat_model


NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
MAX_HISTORY_MESSAGES = 6


class SemanticModel(BaseModel):
    """Strict base model for semantic data produced by Gemini."""

    model_config = ConfigDict(
        extra="forbid",
        allow_inf_nan=False,
        str_strip_whitespace=True,
    )


class TravelDomain(str, Enum):
    ATTRACTION = "ATTRACTION"
    NATURE = "NATURE"
    FOOD = "FOOD"
    ACCOMMODATION = "ACCOMMODATION"
    TRANSPORT = "TRANSPORT"
    ENTERTAINMENT = "ENTERTAINMENT"
    CULTURE = "CULTURE"
    NIGHTLIFE = "NIGHTLIFE"
    SHOPPING = "SHOPPING"
    ESSENTIAL = "ESSENTIAL"


class SearchTargetType(str, Enum):
    POI = "poi"
    COUNTRY = "country"
    CITY = "city"
    ADDRESS = "address"
    PLACE = "place"


class InterpretationStatus(str, Enum):
    SUPPORTED = "supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    NEEDS_CLARIFICATION = "needs_clarification"
    UNSUPPORTED = "unsupported"


class SemanticActionType(str, Enum):
    ANSWER_TRAVEL_QUESTION = "answer_travel_question"
    FIND_NAMED_PLACE = "find_named_place"
    DISCOVER_PLACES = "discover_places"
    REVERSE_GEOCODE = "reverse_geocode"
    MAKE_ITINERARY = "make_itinerary"
    SHOW_ITINERARY = "show_itinerary"
    ADD_ITINERARY_STOP = "add_itinerary_stop"
    REMOVE_ITINERARY_STOP = "remove_itinerary_stop"
    UPDATE_ITINERARY = "update_itinerary"
    REORDER_ITINERARY_STOPS = "reorder_itinerary_stops"
    PROVIDE_ITINERARY_ADVICE = "provide_itinerary_advice"
    PROVIDE_TRANSPORTATION_ADVICE = "provide_transportation_advice"
    PROVIDE_BUDGET_ADVICE = "provide_budget_advice"
    REQUEST_CLARIFICATION = "request_clarification"
    REPORT_UNSUPPORTED = "report_unsupported"


class ConversationMessage(SemanticModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class SemanticLocation(SemanticModel):
    use_current_location: bool = Field(
        default=False,
        description=(
            "True when the question refers to the user's current location, "
            "such as nearby or where am I."
        ),
    )
    near: NonEmptyString | None = None
    longitude: float | None = Field(default=None, ge=-180, le=180)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    radius_km: float | None = Field(default=None, gt=0, le=10)

    @model_validator(mode="after")
    def validate_coordinate_pair(self) -> SemanticLocation:
        if (self.longitude is None) != (self.latitude is None):
            raise ValueError("longitude and latitude must be provided together")
        return self


class SemanticEntities(SemanticModel):
    destinations: list[NonEmptyString] = Field(default_factory=list, max_length=10)
    places: list[NonEmptyString] = Field(default_factory=list, max_length=10)
    place_types: list[NonEmptyString] = Field(default_factory=list, max_length=10)
    search_target: SearchTargetType | None = None
    referenced_result_indexes: list[int] = Field(default_factory=list, max_length=10)


class SemanticTimeContext(SemanticModel):
    start_date: date | None = None
    end_date: date | None = None
    relative_terms: list[NonEmptyString] = Field(default_factory=list, max_length=10)
    day_parts: list[Literal["morning", "afternoon", "evening", "night"]] = Field(
        default_factory=list,
        max_length=4,
    )
    duration_days: int | None = Field(default=None, ge=1, le=365)
    duration_nights: int | None = Field(default=None, ge=0, le=365)

    @model_validator(mode="after")
    def validate_date_range(self) -> SemanticTimeContext:
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must not be earlier than start_date")
        return self


class SemanticConstraints(SemanticModel):
    group_size: int | None = Field(default=None, ge=1, le=100)
    budget_amount: float | None = Field(default=None, ge=0)
    budget_currency: NonEmptyString | None = None
    open_now: bool | None = None
    minimum_rating: float | None = Field(default=None, ge=0, le=5)
    rank_strategy: Literal["distance", "relevance"] | None = None
    price_preference: NonEmptyString | None = None
    mobility_needs: list[NonEmptyString] = Field(default_factory=list, max_length=10)
    cuisines: list[NonEmptyString] = Field(default_factory=list, max_length=10)
    experience_tags: list[NonEmptyString] = Field(default_factory=list, max_length=15)


class SemanticItineraryContext(SemanticModel):
    stop_indexes: list[int] = Field(default_factory=list, max_length=10)
    target_stop_name: NonEmptyString | None = None
    route_profile: Literal["driving", "walking", "cycling"] | None = None
    add_position: Literal["first", "last", "optimized"] | None = None


class SemanticAction(SemanticModel):
    type: SemanticActionType
    depends_on: list[int] = Field(default_factory=list, max_length=4)


class SemanticInterpretation(SemanticModel):
    primary_intent: TravelIntent
    normalized_query: str = Field(min_length=1, max_length=2000)
    travel_domains: list[TravelDomain] = Field(default_factory=list, max_length=10)
    entities: SemanticEntities = Field(default_factory=SemanticEntities)
    location: SemanticLocation = Field(default_factory=SemanticLocation)
    time_context: SemanticTimeContext = Field(default_factory=SemanticTimeContext)
    constraints: SemanticConstraints = Field(default_factory=SemanticConstraints)
    itinerary_context: SemanticItineraryContext = Field(
        default_factory=SemanticItineraryContext
    )
    actions: list[SemanticAction] = Field(min_length=1, max_length=4)
    missing_information: list[NonEmptyString] = Field(default_factory=list, max_length=10)
    status: InterpretationStatus

    @model_validator(mode="after")
    def validate_status_actions(self) -> SemanticInterpretation:
        action_types = {action.type for action in self.actions}
        is_itinerary_making = self.primary_intent == TravelIntent.ITINERARY_MAKING
        has_make_itinerary = SemanticActionType.MAKE_ITINERARY in action_types
        management_actions = {
            SemanticActionType.SHOW_ITINERARY,
            SemanticActionType.ADD_ITINERARY_STOP,
            SemanticActionType.REMOVE_ITINERARY_STOP,
            SemanticActionType.UPDATE_ITINERARY,
            SemanticActionType.REORDER_ITINERARY_STOPS,
        }
        has_management_action = bool(action_types.intersection(management_actions))
        is_itinerary_management = (
            self.primary_intent == TravelIntent.ITINERARY_MANAGEMENT
        )
        if has_make_itinerary and not is_itinerary_making:
            raise ValueError(
                "make_itinerary is only valid for the itinerary_making intent"
            )
        if (
            is_itinerary_making
            and self.status
            in {
                InterpretationStatus.SUPPORTED,
                InterpretationStatus.PARTIALLY_SUPPORTED,
            }
            and not has_make_itinerary
        ):
            raise ValueError(
                "supported itinerary_making requires a make_itinerary action"
            )
        if has_management_action and not is_itinerary_management:
            raise ValueError(
                "itinerary management actions require the itinerary_management intent"
            )
        if (
            is_itinerary_management
            and self.status
            in {
                InterpretationStatus.SUPPORTED,
                InterpretationStatus.PARTIALLY_SUPPORTED,
            }
            and not has_management_action
        ):
            raise ValueError(
                "supported itinerary_management requires a management action"
            )
        if self.status == InterpretationStatus.NEEDS_CLARIFICATION:
            if not self.missing_information:
                raise ValueError(
                    "needs_clarification requires at least one missing information item"
                )
            is_client_location_request = (
                self.location.use_current_location
                and self.location.longitude is None
                and self.location.latitude is None
                and "current_location" in self.missing_information
            )
            if (
                SemanticActionType.REQUEST_CLARIFICATION not in action_types
                and not is_client_location_request
            ):
                raise ValueError(
                    "needs_clarification requires a request_clarification action"
                )
        if (
            self.status == InterpretationStatus.UNSUPPORTED
            and SemanticActionType.REPORT_UNSUPPORTED not in action_types
        ):
            raise ValueError("unsupported requires a report_unsupported action")
        return self


_INTENT_PROMPT_LINES = "\n".join(
    f"- {intent.value}: {description}"
    for intent, description in INTENT_DESCRIPTIONS.items()
)

SEMANTIC_SYSTEM_PROMPT = f"""Phân tích yêu cầu du lịch thành đúng schema, không trả lời người dùng.

Chọn đúng một primary_intent:
{_INTENT_PROMPT_LINES}

Quy tắc:
- Có thể tạo nhiều action nhưng không tạo tên tool, canonicalId, route hoặc dữ liệu giả.
- Dùng itinerary_making khi người dùng yêu cầu tạo/lập/xây dựng một lịch trình cụ thể có
  điểm đến hoặc thời lượng, ví dụ "Lập lịch trình Hà Nội 3 ngày 2 đêm". Khi đủ thông tin,
  luôn thêm make_itinerary; thêm discover_places khi cần khám phá các địa điểm cho lịch trình.
- Dùng itinerary_advice cho câu hỏi tư vấn nguyên tắc, đánh giá hoặc góp ý lịch trình dạng
  văn bản mà không yêu cầu tạo một lịch trình mới có route.
- Dùng itinerary_management khi người dùng muốn xem hoặc thay đổi một lịch trình đang tồn tại.
  Intent nghiệp vụ này ưu tiên hơn context_follow_up dù câu hỏi phụ thuộc vào history.
  + "Thêm Công viên Yên Sở vào lịch trình": itinerary_management,
    actions=[find_named_place, add_itinerary_stop], entities.places=["Công viên Yên Sở"].
  + "Xóa điểm thứ 2": itinerary_management, action=remove_itinerary_stop,
    itinerary_context.stop_indexes=[2].
  + "Đổi điểm thứ 2 thành Văn Miếu": itinerary_management,
    actions=[find_named_place, update_itinerary], itinerary_context.stop_indexes=[2].
  + "Cho điểm thứ 3 lên đầu": itinerary_management, action=reorder_itinerary_stops.
  + "Cho tôi xem lịch trình hiện tại": itinerary_management, action=show_itinerary.
- Không dùng make_itinerary cho thao tác thêm/xóa/sửa lịch trình đang tồn tại.
- Chỉ dùng context_follow_up khi không xác định được intent nghiệp vụ cụ thể hơn.
- "Tìm địa điểm", tìm theo category, travel_qa và "các địa điểm chơi tại Hà Nội" không
  phải itinerary_making và không được thêm make_itinerary.
- Nếu yêu cầu itinerary_making thiếu điểm đến và history không giải quyết được, dùng
  needs_clarification với request_clarification; không tự đoán điểm đến.
- Tên/POI cụ thể dùng find_named_place; nhu cầu khám phá mở dùng discover_places.
  Với place_details như "Đà Lạt ở đâu" hoặc "Hà Nội nằm ở đâu", luôn thêm
  find_named_place khi entities.destinations có tên địa danh và đặt search_target
  phù hợp (city/country/address/place).
  Với find_named_place, đặt entities.search_target đúng loại poi, address, city,
  country hoặc place.
- Phân biệt địa điểm cần tìm với địa điểm làm mốc:
  + Khi người dùng yêu cầu một loại địa điểm gần/quanh một địa điểm có tên, dùng
    discover_places. Đặt loại địa điểm trong entities.place_types; đặt địa điểm làm
    mốc trong location.near và entities.destinations; không đặt địa điểm làm mốc
    trong entities.places.
  + Chỉ dùng find_named_place và entities.places khi người dùng muốn tìm chính địa
    điểm có tên, không phải khi tên đó chỉ đứng sau từ "gần" hoặc "quanh" để làm mốc.
  + Ví dụ "quán cafe gần PTIT": action=discover_places,
    entities.place_types=["cafe"], entities.destinations=["PTIT"],
    entities.places=[], location.near="PTIT".
  + Ví dụ "tìm Highlands Coffee Nguyễn Trãi": action=find_named_place,
    entities.places=["Highlands Coffee Nguyễn Trãi"].
- Backend tự ánh xạ travel_domains, place_types và experience_tags sang category.
  Không chọn loại địa điểm từ từ khóa phụ như mùa hoặc cảm xúc.
- Chỉ đặt minimum_rating/rank_strategy khi người dùng nói rõ; gần nhất dùng distance,
  ưu tiên phù hợp dùng relevance, không giới hạn rating dùng 0.
- Chỉ đường trực tiếp, giao thông thời gian thực, thời tiết hiện tại và thao tác lưu là
  unsupported/report_unsupported. Chỉ itinerary_making mô tả yêu cầu tạo lịch trình có route;
  semantic không tự tạo geometry hoặc thứ tự tối ưu.
- Các câu như "gần tôi", "quanh đây", "ở đâu" đặt location.use_current_location=true.
  Nếu current_location là null thì dùng needs_clarification và nêu
  missing_information là "current_location"; giữ action nghiệp vụ người dùng yêu cầu
  vì backend sẽ xin vị trí từ client trước. Nếu đã có current_location thì dùng tọa độ
  đó để tìm kiếm.
- Dùng history để giải tham chiếu. normalized_query phải độc lập, đúng ý và không
  tự thêm dữ kiện.
"""


class SemanticInterpreter:
    """Ask Gemini for one validated semantic interpretation."""

    def __init__(self, chat_model: Any) -> None:
        self._structured_model = chat_model.with_structured_output(
            SemanticInterpretation,
            method="json_schema",
        )

    def interpret(
        self,
        question: str,
        *,
        history: Sequence[ConversationMessage] = (),
        current_location: SemanticLocation | None = None,
        active_itinerary_id: str | None = None,
    ) -> SemanticInterpretation:
        cleaned_question = question.strip()
        if not cleaned_question:
            raise ValueError("question must not be empty")
        if len(history) > MAX_HISTORY_MESSAGES:
            raise ValueError(
                f"history must contain at most {MAX_HISTORY_MESSAGES} messages"
            )

        payload = {
            "question": cleaned_question,
            "history": [message.model_dump(mode="json") for message in history],
            "current_location": (
                current_location.model_dump(mode="json", exclude_none=True)
                if current_location
                else None
            ),
            "active_itinerary_id": active_itinerary_id,
        }
        messages = [
            SystemMessage(content=SEMANTIC_SYSTEM_PROMPT),
            HumanMessage(
                content=json.dumps(
                    payload,
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
            ),
        ]
        try:
            result = self._structured_model.invoke(messages)
        except OutputParserException:
            correction_messages = [
                *messages,
                HumanMessage(
                    content=(
                        "Kết quả trước vi phạm quan hệ giữa primary_intent và actions. "
                        "Hãy phân tích lại từ đầu; thao tác thêm/xóa/sửa/xem lịch trình "
                        "đang tồn tại phải dùng itinerary_management, không dùng "
                        "context_follow_up hoặc make_itinerary."
                    )
                ),
            ]
            result = self._structured_model.invoke(correction_messages)
        interpretation = (
            result
            if isinstance(result, SemanticInterpretation)
            else SemanticInterpretation.model_validate(result)
        )
        self._print_semantic_response(
            interpretation,
            sensitive_location=current_location,
        )

        location = interpretation.location
        should_hydrate_location = (
            location.use_current_location
            or (
                location.longitude is None
                and location.latitude is None
                and location.near is None
                and not interpretation.entities.destinations
            )
        )
        if current_location is not None and should_hydrate_location:
            interpretation = interpretation.model_copy(
                update={
                    "location": location.model_copy(
                        update={
                            "use_current_location": True,
                            "longitude": current_location.longitude,
                            "latitude": current_location.latitude,
                            "radius_km": current_location.radius_km,
                        }
                    )
                }
            )
        return interpretation

    @staticmethod
    def _print_semantic_response(
        interpretation: SemanticInterpretation,
        *,
        sensitive_location: SemanticLocation | None = None,
    ) -> None:
        """Print Gemini's validated semantic response without SDK metadata."""
        content = interpretation.model_dump_json(
            by_alias=True,
            exclude_none=True,
            indent=2,
        )
        if sensitive_location is not None:
            for coordinate in (
                sensitive_location.longitude,
                sensitive_location.latitude,
            ):
                if coordinate is not None:
                    content = content.replace(str(coordinate), "[location-redacted]")

        output = (
            "Semantic Gemini response (validated):\n"
            f"--- MESSAGE: AI (STRUCTURED) ---\n{content}\n"
        )
        try:
            print(output, end="", flush=True)
        except UnicodeEncodeError:
            stdout_buffer = getattr(sys.stdout, "buffer", None)
            if stdout_buffer is None:
                raise
            stdout_buffer.write(output.encode("utf-8"))
            stdout_buffer.flush()


def interpret_question(
    question: str,
    *,
    history: Sequence[ConversationMessage] = (),
    current_location: SemanticLocation | None = None,
    active_itinerary_id: str | None = None,
    chat_model: Any | None = None,
) -> SemanticInterpretation:
    """Interpret one question without changing the current chat orchestration."""
    model = chat_model or get_chat_model(thinking_level="low")
    return SemanticInterpreter(model).interpret(
        question,
        history=history,
        current_location=current_location,
        active_itinerary_id=active_itinerary_id,
    )


__all__ = [
    "ConversationMessage",
    "InterpretationStatus",
    "MAX_HISTORY_MESSAGES",
    "SEMANTIC_SYSTEM_PROMPT",
    "SemanticAction",
    "SemanticActionType",
    "SemanticConstraints",
    "SemanticEntities",
    "SemanticInterpretation",
    "SemanticItineraryContext",
    "SemanticInterpreter",
    "SemanticLocation",
    "SemanticTimeContext",
    "SearchTargetType",
    "TravelDomain",
    "interpret_question",
]
