"""Project handler executions into the public chatbot response data."""

from __future__ import annotations

import base64
import binascii
import json
import unicodedata
from collections.abc import Callable, Sequence
from typing import Any

from chatbot.tools.models import (
    ChatPlace,
    ChatSource,
    MapboxPlacesDetailsData,
    MapboxPlacesDetailsInput,
    ToolResult,
)
from chatbot.tools.registry import ToolExecution


PlaceDetailsLoader = Callable[
    [MapboxPlacesDetailsInput],
    ToolResult[MapboxPlacesDetailsData],
]


def _is_places_details_poi_id(mapbox_id: str) -> bool:
    encoded = mapbox_id.strip()
    padding = "=" * ((4 - len(encoded) % 4) % 4)
    try:
        decoded = base64.b64decode(
            encoded + padding,
            altchars=b"-_",
            validate=True,
        ).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return False
    return decoded.startswith("urn:mbxpoi:")


class ResponseProjector:
    def __init__(self, place_details_loader: PlaceDetailsLoader | None = None) -> None:
        self._place_details_loader = place_details_loader

    def project_places(
        self,
        answer: str,
        executions: Sequence[ToolExecution],
        destination_evidence: dict[str, Any] | None,
    ) -> list[ChatPlace]:
        return self.enrich_places(
            self.collect_answer_places(answer, executions, destination_evidence)
        )

    def enrich_places(self, places: list[ChatPlace]) -> list[ChatPlace]:
        if not places or self._place_details_loader is None:
            return places
        eligible = [place for place in places if _is_places_details_poi_id(place.mapbox_id)]
        if not eligible:
            return places
        try:
            result = self._place_details_loader(
                MapboxPlacesDetailsInput(ids=[place.mapbox_id for place in eligible])
            )
        except Exception:
            return places
        if not result.success or result.data is None:
            return places
        details_by_id = {detail.mapbox_id: detail for detail in result.data.results}
        enriched: list[ChatPlace] = []
        for place in places:
            detail = details_by_id.get(place.mapbox_id)
            if detail is None:
                enriched.append(place)
                continue
            enriched.append(
                place.model_copy(
                    update={
                        "full_address": detail.full_address or place.full_address,
                        "brand": detail.brand,
                        "primary_category": detail.primary_category,
                        "categories": detail.categories or place.categories,
                        "opening_hours": detail.opening_hours,
                        "permanently_closed": detail.permanently_closed,
                        "phone": detail.phone,
                        "website": detail.website,
                        "operational_status": detail.status or place.operational_status,
                        "popularity": detail.popularity,
                        "photos": detail.photos,
                    },
                )
            )
        return enriched

    @staticmethod
    def _normalize_place_text(value: str) -> str:
        return " ".join(unicodedata.normalize("NFKC", value).casefold().split())

    @classmethod
    def collect_answer_places(
        cls,
        answer: str,
        executions: Sequence[ToolExecution],
        destination_evidence: dict[str, Any] | None,
    ) -> list[ChatPlace]:
        candidates: dict[str, dict[str, Any]] = {}

        def add_candidate(value: Any) -> None:
            if not isinstance(value, dict):
                return
            mapbox_id, name = value.get("mapboxId"), value.get("name")
            if not isinstance(mapbox_id, str) or not mapbox_id.strip():
                return
            if not isinstance(name, str) or not name.strip():
                return
            try:
                longitude, latitude = float(value["longitude"]), float(value["latitude"])
            except (KeyError, TypeError, ValueError):
                return
            if not (-180 <= longitude <= 180 and -90 <= latitude <= 90):
                return
            item = candidates.setdefault(
                mapbox_id.strip(),
                {
                    "mapboxId": mapbox_id.strip(),
                    "names": [],
                    "longitude": longitude,
                    "latitude": latitude,
                    "fullAddress": value.get("fullAddress"),
                    "categories": value.get("poiCategories") or [],
                    "operationalStatus": value.get("operationalStatus"),
                    "rating": value.get("rating"),
                },
            )
            clean_name = name.strip()
            if clean_name not in item["names"]:
                item["names"].append(clean_name)

        if destination_evidence is not None:
            for candidate in destination_evidence.get("matchedCandidates", []):
                add_candidate(candidate)
            for item in destination_evidence.get("additionalMapboxPlaces", []):
                if isinstance(item, dict):
                    add_candidate(item.get("place"))

        for execution in executions:
            if not execution.success:
                continue
            try:
                payload = json.loads(execution.content)
            except (TypeError, ValueError):
                continue
            data = payload.get("data") if isinstance(payload, dict) else None
            if not isinstance(data, dict):
                continue
            for result in data.get("results", []):
                if isinstance(result, dict):
                    add_candidate(result.get("place", result))
            for place in data.get("additionalPlaces", []):
                add_candidate(place)

        normalized_answer = cls._normalize_place_text(answer)
        name_to_ids: dict[str, set[str]] = {}
        for mapbox_id, candidate in candidates.items():
            for name in candidate["names"]:
                name_to_ids.setdefault(cls._normalize_place_text(name), set()).add(mapbox_id)

        places: list[ChatPlace] = []
        for mapbox_id, candidate in candidates.items():
            matching_names = [
                name
                for name in candidate["names"]
                if name_to_ids.get(cls._normalize_place_text(name)) == {mapbox_id}
                and cls._normalize_place_text(name) in normalized_answer
            ]
            if not matching_names:
                continue
            places.append(
                ChatPlace(
                    mapboxId=mapbox_id,
                    name=max(matching_names, key=len),
                    longitude=candidate["longitude"],
                    latitude=candidate["latitude"],
                    fullAddress=candidate["fullAddress"],
                    categories=candidate["categories"],
                    operationalStatus=candidate["operationalStatus"],
                    rating=candidate["rating"],
                )
            )
        return places

    @staticmethod
    def collect_unique_sources(executions: Sequence[ToolExecution]) -> list[ChatSource]:
        sources: list[ChatSource] = []
        seen: set[tuple[str, str, str]] = set()
        for execution in executions:
            for source in execution.sources:
                key = (source.type, source.title, source.source)
                if key in seen:
                    continue
                seen.add(key)
                sources.append(source)
        return sources


__all__ = ["PlaceDetailsLoader", "ResponseProjector"]
