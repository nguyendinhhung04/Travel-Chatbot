"""Build a small, destination-aware evidence payload for Gemini."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from chatbot.tool_planner import PlannedToolCall
from chatbot.tools.registry import ToolExecution


MAX_KNOWLEDGE_CHUNKS = 3
MAX_POIS_PER_CATEGORY = 3


def build_evidence_context(
    calls: Sequence[PlannedToolCall],
    executions: Sequence[ToolExecution],
) -> dict[str, Any]:
    """Group successful normalized evidence without exposing full tool payloads."""
    destinations: dict[str, dict[str, Any]] = {}
    seen_pois: dict[str, set[str]] = {}
    general_knowledge: list[dict[str, Any]] = []
    general_knowledge_statuses: list[str] = []

    for call, execution in zip(calls, executions, strict=True):
        result = _load_result(execution)
        status = _execution_status(execution, result, call.evidence_kind)

        if call.destination is None:
            if call.evidence_kind == "knowledge":
                general_knowledge_statuses.append(status)
                general_knowledge.extend(
                    _knowledge_chunks(result)[:MAX_KNOWLEDGE_CHUNKS]
                )
            continue

        destination = destinations.setdefault(
            call.destination,
            {
                "name": call.destination,
                "knowledge": [],
                "poiGroups": [],
            },
        )
        destination_seen_pois = seen_pois.setdefault(call.destination, set())

        if call.evidence_kind == "knowledge":
            destination["knowledgeStatus"] = status
            destination["knowledge"].extend(
                _knowledge_chunks(result)[:MAX_KNOWLEDGE_CHUNKS]
            )
        elif call.evidence_kind == "location":
            destination["locationStatus"] = status
            places = _normalized_places(result)
            if places:
                destination["location"] = _refine_place(
                    places[0],
                    _raw_features(result),
                    include_metadata=False,
                )
        elif call.evidence_kind == "poi":
            refined_results: list[dict[str, Any]] = []
            raw_features = _raw_features(result)
            for place in _normalized_places(result):
                mapbox_id = place.get("mapboxId")
                if not isinstance(mapbox_id, str) or mapbox_id in destination_seen_pois:
                    continue
                destination_seen_pois.add(mapbox_id)
                refined_results.append(
                    _refine_place(place, raw_features, include_metadata=True)
                )
                if len(refined_results) >= MAX_POIS_PER_CATEGORY:
                    break
            destination["poiGroups"].append(
                {
                    "categoryId": call.category_id,
                    "status": status,
                    "results": refined_results,
                }
            )

    payload: dict[str, Any] = {"destinations": list(destinations.values())}
    if general_knowledge_statuses:
        payload["generalKnowledge"] = {
            "status": _combined_status(general_knowledge_statuses),
            "results": general_knowledge[:MAX_KNOWLEDGE_CHUNKS],
        }
    return _remove_empty_values(payload)


def _load_result(execution: ToolExecution) -> dict[str, Any]:
    try:
        value = json.loads(execution.content)
    except (json.JSONDecodeError, TypeError):
        return {}
    return value if isinstance(value, dict) else {}


def _execution_status(
    execution: ToolExecution,
    result: dict[str, Any],
    evidence_kind: str | None,
) -> str:
    if not execution.success:
        return "failed"
    if evidence_kind == "knowledge":
        return "available" if _knowledge_chunks(result) else "empty"
    return "available" if _normalized_places(result) else "empty"


def _knowledge_chunks(result: dict[str, Any]) -> list[dict[str, Any]]:
    data = result.get("data")
    chunks = data.get("chunks") if isinstance(data, dict) else None
    if not isinstance(chunks, list):
        return []
    refined: list[dict[str, Any]] = []
    for chunk in chunks:
        if not isinstance(chunk, dict):
            continue
        refined.append(
            _remove_empty_values(
                {
                    "title": chunk.get("title"),
                    "heading": chunk.get("heading"),
                    "content": chunk.get("content"),
                    "source": chunk.get("source"),
                }
            )
        )
    return refined


def _normalized_places(result: dict[str, Any]) -> list[dict[str, Any]]:
    data = result.get("data")
    places = data.get("results") if isinstance(data, dict) else None
    if not isinstance(places, list):
        return []
    return [place for place in places if isinstance(place, dict)]


def _raw_features(result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    data = result.get("data")
    raw_response = data.get("rawResponse") if isinstance(data, dict) else None
    features = raw_response.get("features") if isinstance(raw_response, dict) else None
    if not isinstance(features, list):
        return {}

    indexed: dict[str, dict[str, Any]] = {}
    for feature in features:
        if not isinstance(feature, dict):
            continue
        properties = feature.get("properties")
        properties = properties if isinstance(properties, dict) else {}
        mapbox_id = properties.get("mapbox_id") or properties.get("mapboxId")
        mapbox_id = mapbox_id or feature.get("id")
        if isinstance(mapbox_id, str):
            indexed[mapbox_id] = feature
    return indexed


def _refine_place(
    place: dict[str, Any],
    raw_features: dict[str, dict[str, Any]],
    *,
    include_metadata: bool,
) -> dict[str, Any]:
    refined = {
        key: place.get(key)
        for key in (
            "mapboxId",
            "name",
            "featureType",
            "fullAddress",
            "longitude",
            "latitude",
            "poiCategories",
            "poiCategoryIds",
            "operationalStatus",
            "distanceMeters",
            "etaMinutes",
            "rating",
            "popularity",
        )
    }
    if not include_metadata:
        return _remove_empty_values(refined)

    mapbox_id = place.get("mapboxId")
    feature = raw_features.get(mapbox_id, {}) if isinstance(mapbox_id, str) else {}
    properties = feature.get("properties")
    properties = properties if isinstance(properties, dict) else {}
    metadata = properties.get("metadata")
    metadata = metadata if isinstance(metadata, dict) else {}

    refined.update(
        {
            "phone": _first_value(metadata, properties, names=("phone",)),
            "website": _first_value(metadata, properties, names=("website",)),
            "openingHours": _first_value(
                metadata,
                properties,
                names=("open_hours", "opening_hours", "openingHours"),
            ),
            "priceLevel": _first_value(
                metadata,
                properties,
                names=("price_level", "priceLevel"),
            ),
            "brand": _first_value(metadata, properties, names=("brand",)),
            "reviewCount": _first_value(
                metadata,
                properties,
                names=("review_count", "reviewCount"),
            ),
        }
    )
    return _remove_empty_values(refined)


def _first_value(
    *containers: dict[str, Any],
    names: tuple[str, ...],
) -> Any:
    for container in containers:
        for name in names:
            value = container.get(name)
            if not _is_empty(value):
                return value
    return None


def _combined_status(statuses: list[str]) -> str:
    if "available" in statuses:
        return "available"
    if "empty" in statuses:
        return "empty"
    return "failed"


def _remove_empty_values(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: cleaned
            for key, item in value.items()
            if not _is_empty(cleaned := _remove_empty_values(item))
        }
    if isinstance(value, list):
        return [
            cleaned
            for item in value
            if not _is_empty(cleaned := _remove_empty_values(item))
        ]
    return value


def _is_empty(value: Any) -> bool:
    return (
        value is None
        or (isinstance(value, str) and not value.strip())
        or value == []
        or value == {}
    )


__all__ = [
    "MAX_KNOWLEDGE_CHUNKS",
    "MAX_POIS_PER_CATEGORY",
    "build_evidence_context",
]
