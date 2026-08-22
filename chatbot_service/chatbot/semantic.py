"""Structured semantic interpretation for travel question-answering requests."""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import date
from enum import Enum
from typing import Annotated, Any, Literal

from langchain_core.messages import HumanMessage, SystemMessage
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
MAX_HISTORY_MESSAGES = 12


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
    PROVIDE_ITINERARY_ADVICE = "provide_itinerary_advice"
    PROVIDE_TRANSPORTATION_ADVICE = "provide_transportation_advice"
    PROVIDE_BUDGET_ADVICE = "provide_budget_advice"
    REQUEST_CLARIFICATION = "request_clarification"
    REPORT_UNSUPPORTED = "report_unsupported"


class ConversationMessage(SemanticModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class SemanticLocation(SemanticModel):
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
    actions: list[SemanticAction] = Field(min_length=1, max_length=4)
    missing_information: list[NonEmptyString] = Field(default_factory=list, max_length=10)
    status: InterpretationStatus

    @model_validator(mode="after")
    def validate_status_actions(self) -> SemanticInterpretation:
        action_types = {action.type for action in self.actions}
        if self.status == InterpretationStatus.NEEDS_CLARIFICATION:
            if not self.missing_information:
                raise ValueError(
                    "needs_clarification requires at least one missing information item"
                )
            if SemanticActionType.REQUEST_CLARIFICATION not in action_types:
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

SEMANTIC_SYSTEM_PROMPT = f"""Bạn là bộ phân tích intent và ngữ nghĩa cho chatbot hỏi đáp du lịch.

Mỗi message phải có đúng một primary_intent trong danh sách:
{_INTENT_PROMPT_LINES}

Quy tắc:
- Chỉ phân tích và chuẩn hóa ý nghĩa; không trả lời câu hỏi của người dùng.
- Có thể tạo nhiều action đọc dữ liệu, nhưng chỉ có một primary_intent.
- Không tạo tên tool, Mapbox canonicalId, route hoặc dữ liệu địa điểm giả.
- Chỉ chọn travel domain trong schema. Backend sẽ tự ánh xạ domain, place_types và
  experience_tags sang Mapbox category.
- Phân biệt POI/tên riêng cụ thể với nhu cầu tìm kiếm mở. POI cụ thể dùng action
  find_named_place; nhu cầu mở dùng discover_places.
- Với find_named_place, điền entities.search_target: poi cho nhà hàng/khách sạn/điểm tham
  quan/doanh nghiệp cụ thể; address cho địa chỉ; city cho thành phố; country cho quốc gia;
  place cho địa danh hành chính khác.
- Chỉ điền constraints.minimum_rating khi người dùng nêu mức rating cụ thể. Nếu người dùng
  nói không giới hạn rating, dùng 0. Chỉ điền constraints.rank_strategy=distance khi họ yêu
  cầu gần nhất; dùng relevance khi họ nói rõ ưu tiên phù hợp với truy vấn; nếu không thì để null.
- Itinerary chỉ là tư vấn bằng văn bản, không lưu và không tính route.
- Yêu cầu chỉ đường trực tiếp, giao thông thời gian thực, lưu yêu thích hoặc lưu dữ
  liệu người dùng phải có status unsupported và action report_unsupported.
- Câu hỏi thời tiết hiện tại không có provider nên cũng phải đánh dấu unsupported.
- Nếu câu hỏi "gần tôi" không có tọa độ hoặc địa danh trong input/history, dùng
  needs_clarification, điền missing_information và action request_clarification.
- Dùng history để giải tham chiếu như "nó", "quán thứ hai" hoặc "địa điểm đó".
- normalized_query phải là câu độc lập, giữ đúng ý người dùng và không tự thêm dữ kiện.
- Không chọn category theo từ khóa phụ như mùa hoặc cảm xúc nếu chúng không phải loại
  địa điểm chính.
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
        result = self._structured_model.invoke(messages)
        if isinstance(result, SemanticInterpretation):
            return result
        return SemanticInterpretation.model_validate(result)


def interpret_question(
    question: str,
    *,
    history: Sequence[ConversationMessage] = (),
    current_location: SemanticLocation | None = None,
    chat_model: Any | None = None,
) -> SemanticInterpretation:
    """Interpret one question without changing the current chat orchestration."""
    model = chat_model or get_chat_model()
    return SemanticInterpreter(model).interpret(
        question,
        history=history,
        current_location=current_location,
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
    "SemanticInterpreter",
    "SemanticLocation",
    "SemanticTimeContext",
    "SearchTargetType",
    "TravelDomain",
    "interpret_question",
]
