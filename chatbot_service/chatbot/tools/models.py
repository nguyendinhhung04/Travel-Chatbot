"""Pydantic contracts shared by the chatbot orchestrator and tool clients."""

from __future__ import annotations

from typing import Annotated, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator


NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
ToolData = TypeVar("ToolData")


class ToolModel(BaseModel):
    """Strict base model for data crossing a tool boundary."""

    model_config = ConfigDict(
        allow_inf_nan=False,
        extra="forbid",
        populate_by_name=True,
        str_strip_whitespace=True,
    )


class _MapboxSearchFilters(ToolModel):
    language: NonEmptyString | None = Field(
        default=None,
        description="Ngôn ngữ kết quả, ưu tiên 'vi' khi người dùng hỏi bằng tiếng Việt.",
    )
    limit: int | None = Field(default=None, ge=1, le=25)
    proximity: NonEmptyString | None = None
    near: NonEmptyString | None = Field(
        default=None,
        description=(
            "Địa danh làm khu vực tìm kiếm, ví dụ 'Hà Nội'. Dùng cho nơi người dùng "
            "muốn đi; không dùng làm category_id."
        ),
    )
    bbox: NonEmptyString | None = None
    radius: float | None = Field(default=None, ge=0.00001, le=10)
    country: NonEmptyString | None = None
    types: NonEmptyString | None = None
    poi_category_exclusions: NonEmptyString | None = None
    show_closed_pois: bool | None = None
    exclude_fields: NonEmptyString | None = None


class MapboxForwardSearchInput(_MapboxSearchFilters):
    """Arguments accepted by the Mapbox forward-search typed endpoint."""

    q: str = Field(
        min_length=1,
        max_length=256,
        description=(
            "Tên riêng, địa chỉ hoặc POI cụ thể cần tìm. Không truyền nguyên câu hỏi "
            "tư vấn, cảm xúc như 'chill/lãng mạn', mùa hoặc thời điểm vào q."
        ),
    )
    limit: int | None = Field(default=None, ge=1, le=10)
    poi_category: NonEmptyString | None = Field(
        default=None,
        description=(
            "Bộ lọc category chỉ dùng kèm một q là tên/địa chỉ cụ thể; với nhu cầu "
            "gợi ý theo trải nghiệm, backend sẽ dùng category resolver và "
            "mapbox_category_search."
        ),
    )
    open_now: bool | None = None
    minimum_rating: float | None = Field(default=None, ge=0, le=5)
    price_levels: NonEmptyString | None = None
    rank_strategy: Literal["distance", "relevance"] | None = None
    auto_complete: bool | None = None


class MapboxCategorySearchInput(_MapboxSearchFilters):
    """Arguments accepted by the Mapbox category-search typed endpoint."""

    category_id: NonEmptyString = Field(
        description=(
            "Canonical category ID thuộc whitelist do backend category resolver chọn "
            "từ semantic domain. Không dùng địa danh làm category_id."
        )
    )
    minimum_rating: float | None = Field(default=None, ge=0, le=5)


class MapboxReverseLookupInput(ToolModel):
    """Arguments accepted by the Mapbox reverse-lookup typed endpoint."""

    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(ge=-90, le=90)
    language: NonEmptyString | None = None
    limit: int | None = Field(default=None, ge=1, le=10)
    country: NonEmptyString | None = None
    types: NonEmptyString | None = None
    show_closed_pois: bool | None = None


class SearchTravelKnowledgeInput(ToolModel):
    """Arguments accepted by the local travel-knowledge retrieval tool."""

    query: str = Field(min_length=1, max_length=2000)
    destination: NonEmptyString | None = Field(
        default=None,
        description="Điểm đến dùng để lọc metadata của Knowledge Base.",
    )


class MapboxPlaceItem(ToolModel):
    """Chatbot-oriented place fields returned by the ASP.NET typed tools."""

    mapbox_id: NonEmptyString = Field(alias="mapboxId")
    name: NonEmptyString
    feature_type: NonEmptyString = Field(alias="featureType")
    full_address: str | None = Field(default=None, alias="fullAddress")
    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(ge=-90, le=90)
    poi_categories: list[str] = Field(alias="poiCategories")
    poi_category_ids: list[str] = Field(alias="poiCategoryIds")
    operational_status: str | None = Field(default=None, alias="operationalStatus")
    distance_meters: float | None = Field(default=None, alias="distanceMeters", ge=0)
    eta_minutes: float | None = Field(default=None, alias="etaMinutes", ge=0)
    rating: float | None = Field(default=None, ge=0, le=5)
    popularity: float | None = Field(default=None, ge=0)


class MapboxPlaceToolData(ToolModel):
    attribution: NonEmptyString
    results: list[MapboxPlaceItem]


class MapboxPlaceSummaryItem(ToolModel):
    """Compact place fields returned by ordinary ASP.NET Mapbox endpoints."""

    mapbox_id: NonEmptyString = Field(alias="mapboxId")
    name: NonEmptyString
    full_address: str | None = Field(default=None, alias="fullAddress")
    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(ge=-90, le=90)
    poi_categories: list[str] = Field(default_factory=list, alias="poiCategories")
    operational_status: str | None = Field(default=None, alias="operationalStatus")
    distance_meters: float | None = Field(default=None, alias="distanceMeters", ge=0)
    eta_minutes: float | None = Field(default=None, alias="etaMinutes", ge=0)
    rating: float | None = Field(default=None, ge=0, le=5)


class MapboxPlaceSummaryData(ToolModel):
    attribution: NonEmptyString
    results: list[MapboxPlaceSummaryItem]


class MapboxPlacesDetailsInput(ToolModel):
    ids: list[NonEmptyString] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_unique_ids(self) -> "MapboxPlacesDetailsInput":
        if len(set(self.ids)) != len(self.ids):
            raise ValueError("ids must not contain duplicates")
        return self


class MapboxPlacePhoto(ToolModel):
    url: NonEmptyString
    width: int | None = Field(default=None, gt=0)
    height: int | None = Field(default=None, gt=0)
    source: str | None = None


class MapboxPlaceDetailsItem(ToolModel):
    mapbox_id: NonEmptyString = Field(alias="mapboxId")
    name: NonEmptyString
    full_address: str | None = Field(default=None, alias="fullAddress")
    brand: str | None = None
    primary_category: str | None = Field(default=None, alias="primaryCategory")
    categories: list[str] = Field(default_factory=list)
    opening_hours: str | None = Field(default=None, alias="openingHours")
    permanently_closed: bool | None = Field(default=None, alias="permanentlyClosed")
    phone: str | None = None
    website: str | None = None
    status: str | None = None
    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(ge=-90, le=90)
    popularity: float | None = Field(default=None, ge=0, le=1)
    photos: list[MapboxPlacePhoto] = Field(default_factory=list)


class MapboxPlacesDetailsData(ToolModel):
    results: list[MapboxPlaceDetailsItem]
    missing: list[str] = Field(default_factory=list)
    unprocessed: list[str] = Field(default_factory=list)


class MapboxCandidateInput(ToolModel):
    candidate_id: NonEmptyString = Field(alias="candidateId")
    name: NonEmptyString
    aliases: list[NonEmptyString] = Field(default_factory=list, max_length=5)
    category_hints: list[NonEmptyString] = Field(
        default_factory=list,
        alias="categoryHints",
        max_length=5,
    )


class MapboxCandidateResolveInput(ToolModel):
    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(ge=-90, le=90)
    candidates: list[MapboxCandidateInput] = Field(default_factory=list, max_length=5)
    category_id: NonEmptyString | None = Field(default=None, alias="categoryId")
    minimum_rating: float | None = Field(
        default=None,
        alias="minimumRating",
        ge=0,
        le=5,
    )

    @model_validator(mode="after")
    def require_candidate_or_category(self) -> MapboxCandidateResolveInput:
        if not self.candidates and self.category_id is None:
            raise ValueError("At least one candidate or categoryId is required.")
        candidate_ids = [candidate.candidate_id for candidate in self.candidates]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("candidateId values must be unique.")
        return self


class MapboxCandidateMatch(ToolModel):
    candidate_id: NonEmptyString = Field(alias="candidateId")
    status: Literal[
        "matched",
        "ambiguous",
        "not_found",
        "lookup_failed",
        "duplicate",
    ]
    similarity: float | None = Field(default=None, ge=0, le=1)
    place: MapboxPlaceItem | None = None


class MapboxCandidateResolutionData(ToolModel):
    attribution: NonEmptyString
    results: list[MapboxCandidateMatch]
    additional_places: list[MapboxPlaceItem] = Field(alias="additionalPlaces")


class ItineraryStopInput(ToolModel):
    mapbox_id: NonEmptyString = Field(alias="mapboxId")
    name: NonEmptyString
    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(ge=-90, le=90)


class ItineraryStopData(ItineraryStopInput):
    id: NonEmptyString
    order: int = Field(ge=1, le=12)
    input_index: int = Field(alias="inputIndex", ge=0, le=11)


class ItineraryGeometryData(ToolModel):
    type: Literal["LineString"]
    coordinates: list[list[float]] = Field(min_length=2)


class ItineraryData(ToolModel):
    id: NonEmptyString
    user_id: Literal["admin"] = Field(alias="userId")
    version: int = Field(ge=1)
    title: NonEmptyString
    destination: NonEmptyString
    duration_days: int = Field(alias="durationDays", ge=1, le=365)
    duration_nights: int = Field(alias="durationNights", ge=0, le=365)
    profile: Literal["driving", "walking", "cycling"]
    stops: list[ItineraryStopData] = Field(min_length=2, max_length=12)
    route: ItineraryGeometryData
    distance_meters: float = Field(alias="distanceMeters", ge=0)
    duration_seconds: float = Field(alias="durationSeconds", ge=0)
    provider: Literal["mapbox"] = "mapbox"
    generated_at: str = Field(alias="generatedAt")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")


class ItineraryGetInput(ToolModel):
    itinerary_id: NonEmptyString | None = Field(default=None, alias="itineraryId")


class ItineraryCreateInput(ToolModel):
    title: NonEmptyString
    destination: NonEmptyString
    duration_days: int = Field(alias="durationDays", ge=1, le=365)
    duration_nights: int = Field(alias="durationNights", ge=0, le=365)
    profile: Literal["driving", "walking", "cycling"]
    stops: list[ItineraryStopInput] = Field(min_length=2, max_length=12)

    @model_validator(mode="after")
    def validate_unique_stops(self) -> "ItineraryCreateInput":
        mapbox_ids = [stop.mapbox_id for stop in self.stops]
        if len(mapbox_ids) != len(set(mapbox_ids)):
            raise ValueError("stops must not contain duplicate mapboxId values")
        return self


class ItineraryAddStopInput(ToolModel):
    itinerary_id: NonEmptyString = Field(alias="itineraryId")
    expected_version: int = Field(alias="expectedVersion", ge=1)
    stop: ItineraryStopInput
    position: Literal["first", "last", "optimized"] = "optimized"


class MapboxOptimizationStopInput(ToolModel):
    """One verified POI passed to the Mapbox Optimization endpoint."""

    mapbox_id: NonEmptyString = Field(alias="mapboxId")
    name: NonEmptyString
    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(ge=-90, le=90)


class MapboxOptimizeRouteInput(ToolModel):
    """Arguments accepted by the Mapbox route-optimization typed endpoint."""

    profile: Literal["driving", "walking", "cycling"]
    stops: list[MapboxOptimizationStopInput] = Field(min_length=2, max_length=12)

    @model_validator(mode="after")
    def validate_unique_stops(self) -> "MapboxOptimizeRouteInput":
        mapbox_ids = [stop.mapbox_id for stop in self.stops]
        if len(mapbox_ids) != len(set(mapbox_ids)):
            raise ValueError("stops must not contain duplicate mapboxId values")
        return self


class MapboxOptimizedStop(ToolModel):
    order: int = Field(ge=1)
    input_index: int = Field(alias="inputIndex", ge=0)
    mapbox_id: NonEmptyString = Field(alias="mapboxId")
    name: NonEmptyString
    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(ge=-90, le=90)


class MapboxRouteGeometry(ToolModel):
    type: Literal["LineString"]
    coordinates: list[tuple[float, float]] = Field(min_length=2)

    @model_validator(mode="after")
    def validate_coordinates(self) -> "MapboxRouteGeometry":
        for longitude, latitude in self.coordinates:
            if not -180 <= longitude <= 180 or not -90 <= latitude <= 90:
                raise ValueError(
                    "route coordinates must be valid longitude/latitude pairs"
                )
        return self


class MapboxOptimizedRouteData(ToolModel):
    profile: Literal["driving", "walking", "cycling"]
    ordered_stops: list[MapboxOptimizedStop] = Field(
        alias="orderedStops",
        min_length=2,
        max_length=12,
    )
    geometry: MapboxRouteGeometry
    distance_meters: float = Field(alias="distanceMeters", ge=0)
    duration_seconds: float = Field(alias="durationSeconds", ge=0)

    @model_validator(mode="after")
    def validate_stop_order(self) -> "MapboxOptimizedRouteData":
        expected_orders = list(range(1, len(self.ordered_stops) + 1))
        if [stop.order for stop in self.ordered_stops] != expected_orders:
            raise ValueError(
                "orderedStops must be sorted with contiguous order values"
            )
        input_indexes = [stop.input_index for stop in self.ordered_stops]
        if sorted(input_indexes) != list(range(len(self.ordered_stops))):
            raise ValueError(
                "orderedStops must contain every inputIndex exactly once"
            )
        mapbox_ids = [stop.mapbox_id for stop in self.ordered_stops]
        if len(mapbox_ids) != len(set(mapbox_ids)):
            raise ValueError(
                "orderedStops must not contain duplicate mapboxId values"
            )
        return self


class ToolResult(ToolModel, Generic[ToolData]):
    """Success or failure envelope returned by ASP.NET and local tools."""

    success: bool
    data: ToolData | None = None
    error_code: str | None = Field(default=None, alias="errorCode")
    error_message: str | None = Field(default=None, alias="errorMessage")

    @model_validator(mode="after")
    def validate_envelope(self) -> ToolResult[ToolData]:
        if self.success:
            if self.data is None:
                raise ValueError("A successful tool result must include data.")
            if self.error_code is not None or self.error_message is not None:
                raise ValueError("A successful tool result cannot include an error.")
        else:
            if self.data is not None:
                raise ValueError("A failed tool result cannot include data.")
            if not self.error_code or not self.error_message:
                raise ValueError("A failed tool result must include an error code and message.")
        return self


class KnowledgeBaseSource(ToolModel):
    type: Literal["knowledge_base"] = "knowledge_base"
    title: NonEmptyString
    source: NonEmptyString


class MapboxSource(ToolModel):
    type: Literal["mapbox"] = "mapbox"
    title: NonEmptyString = "Mapbox"
    source: NonEmptyString = "Mapbox Search API"
    attribution: NonEmptyString


class ChatPlace(ToolModel):
    """Verified Mapbox place exposed for answer highlighting and map markers."""

    mapbox_id: NonEmptyString = Field(alias="mapboxId")
    name: NonEmptyString
    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(ge=-90, le=90)
    full_address: str | None = Field(default=None, alias="fullAddress")
    brand: str | None = None
    primary_category: str | None = Field(default=None, alias="primaryCategory")
    categories: list[str] = Field(default_factory=list)
    opening_hours: str | None = Field(default=None, alias="openingHours")
    permanently_closed: bool | None = Field(default=None, alias="permanentlyClosed")
    phone: str | None = None
    website: str | None = None
    operational_status: str | None = Field(default=None, alias="operationalStatus")
    rating: float | None = Field(default=None, ge=0, le=5)
    popularity: float | None = Field(default=None, ge=0, le=1)
    photos: list[MapboxPlacePhoto] = Field(default_factory=list)


ChatSource = Annotated[
    KnowledgeBaseSource | MapboxSource,
    Field(discriminator="type"),
]


class RagChunk(ToolModel):
    content: NonEmptyString
    title: NonEmptyString
    source: NonEmptyString
    heading: str | None = None


class RagToolData(ToolModel):
    chunks: list[RagChunk] = Field(default_factory=list)
    sources: list[KnowledgeBaseSource] = Field(default_factory=list)


__all__ = [
    "ChatPlace",
    "ChatSource",
    "KnowledgeBaseSource",
    "ItineraryAddStopInput",
    "ItineraryData",
    "ItineraryGeometryData",
    "ItineraryGetInput",
    "ItineraryStopData",
    "ItineraryStopInput",
    "MapboxCategorySearchInput",
    "MapboxCandidateInput",
    "MapboxCandidateMatch",
    "MapboxCandidateResolutionData",
    "MapboxCandidateResolveInput",
    "MapboxForwardSearchInput",
    "MapboxOptimizationStopInput",
    "MapboxOptimizeRouteInput",
    "MapboxOptimizedRouteData",
    "MapboxOptimizedStop",
    "MapboxPlaceItem",
    "MapboxPlaceDetailsItem",
    "MapboxPlacePhoto",
    "MapboxPlaceSummaryData",
    "MapboxPlaceSummaryItem",
    "MapboxPlaceToolData",
    "MapboxPlacesDetailsData",
    "MapboxPlacesDetailsInput",
    "MapboxReverseLookupInput",
    "MapboxRouteGeometry",
    "MapboxSource",
    "RagChunk",
    "RagToolData",
    "SearchTravelKnowledgeInput",
    "ToolResult",
]
