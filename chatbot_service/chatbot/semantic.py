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

SEMANTIC_SYSTEM_PROMPT = f"""Phân tích yêu cầu du lịch thành đúng schema, không trả lời người dùng.

Chọn đúng một primary_intent:
{_INTENT_PROMPT_LINES}

Quy tắc:
- Có thể tạo nhiều action nhưng không tạo tên tool, canonicalId, route hoặc dữ liệu giả.
- Tên/POI cụ thể dùng find_named_place; nhu cầu khám phá mở dùng discover_places.
  Với find_named_place, đặt entities.search_target đúng loại poi, address, city,
  country hoặc place.
- Backend tự ánh xạ travel_domains, place_types và experience_tags sang category.
  Không chọn loại địa điểm từ từ khóa phụ như mùa hoặc cảm xúc.
- Chỉ đặt minimum_rating/rank_strategy khi người dùng nói rõ; gần nhất dùng distance,
  ưu tiên phù hợp dùng relevance, không giới hạn rating dùng 0.
- Chỉ đường, giao thông thời gian thực, thời tiết hiện tại và thao tác lưu là
  unsupported/report_unsupported. Lịch trình chỉ là tư vấn văn bản.
- "Gần tôi" thiếu vị trí dùng needs_clarification và nêu missing_information.
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
    model = chat_model or get_chat_model(thinking_level="low")
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
