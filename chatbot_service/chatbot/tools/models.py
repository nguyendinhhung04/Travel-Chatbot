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
    language: NonEmptyString | None = None
    limit: int | None = Field(default=None, ge=1, le=25)
    proximity: NonEmptyString | None = None
    near: NonEmptyString | None = None
    bbox: NonEmptyString | None = None
    radius: float | None = Field(default=None, ge=0.00001, le=10)
    country: NonEmptyString | None = None
    types: NonEmptyString | None = None
    poi_category_exclusions: NonEmptyString | None = None
    show_closed_pois: bool | None = None
    exclude_fields: NonEmptyString | None = None
    sar_type: Literal["isochrone"] | None = None
    route: NonEmptyString | None = None
    route_geometry: Literal["polyline", "polyline6"] | None = None
    time_deviation: float | None = Field(default=None, ge=0)
    eta_type: Literal["navigation"] | None = None
    navigation_profile: Literal["driving", "walking", "cycling"] | None = None
    origin: NonEmptyString | None = None


class MapboxForwardSearchInput(_MapboxSearchFilters):
    """Arguments accepted by the Mapbox forward-search typed endpoint."""

    q: str = Field(min_length=1, max_length=256)
    limit: int | None = Field(default=None, ge=1, le=10)
    poi_category: NonEmptyString | None = None
    open_now: bool | None = None
    minimum_rating: float | None = Field(default=None, ge=0, le=5)
    price_levels: NonEmptyString | None = None
    rank_strategy: Literal["distance", "relevance"] | None = None
    auto_complete: bool | None = None


class MapboxListCategoriesInput(ToolModel):
    """Arguments accepted by the Mapbox category-list typed endpoint."""

    language: NonEmptyString | None = None


class MapboxCategorySearchInput(_MapboxSearchFilters):
    """Arguments accepted by the Mapbox category-search typed endpoint."""

    category_id: NonEmptyString


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


class MapboxPlaceToolData(ToolModel):
    attribution: NonEmptyString
    results: list[MapboxPlaceItem]


class MapboxCategoryItem(ToolModel):
    canonical_id: NonEmptyString = Field(alias="canonicalId")
    name: NonEmptyString


class MapboxCategoryToolData(ToolModel):
    attribution: NonEmptyString
    categories: list[MapboxCategoryItem]


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
    "ChatSource",
    "KnowledgeBaseSource",
    "MapboxCategoryItem",
    "MapboxCategorySearchInput",
    "MapboxCategoryToolData",
    "MapboxForwardSearchInput",
    "MapboxListCategoriesInput",
    "MapboxPlaceItem",
    "MapboxPlaceToolData",
    "MapboxReverseLookupInput",
    "MapboxSource",
    "RagChunk",
    "RagToolData",
    "SearchTravelKnowledgeInput",
    "ToolResult",
]
