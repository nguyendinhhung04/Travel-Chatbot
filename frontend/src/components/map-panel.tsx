"use client";

import { useEffect, useRef, useState } from "react";
import mapboxgl from "mapbox-gl";
import "mapbox-gl/dist/mapbox-gl.css";
import type {
  ChatItinerary,
  ChatPlace,
  UserLocation,
} from "@/types/chat";

const VIETNAM_CENTER: [number, number] = [108.2022, 16.0544];
const MAPBOX_TOKEN = process.env.NEXT_PUBLIC_MAPBOX_ACCESS_TOKEN;
const ITINERARY_ROUTE_SOURCE_ID = "travel-itinerary-route";
const ITINERARY_ROUTE_LAYER_ID = "travel-itinerary-route-line";

type MapPanelProps = {
  places: ChatPlace[];
  itinerary: ChatItinerary | null;
  userLocation: UserLocation | null;
  activePlaceId: string | null;
  focusRequest: { place: ChatPlace; requestId: string } | null;
};

export default function MapPanel({
  places,
  itinerary,
  userLocation,
  activePlaceId,
  focusRequest,
}: MapPanelProps) {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<mapboxgl.Map | null>(null);
  const markersRef = useRef<Map<string, mapboxgl.Marker>>(new Map());
  const itineraryMarkersRef = useRef<Map<string, mapboxgl.Marker>>(new Map());
  const userMarkerRef = useRef<mapboxgl.Marker | null>(null);
  const [mapState, setMapState] = useState<"loading" | "ready" | "missing-token" | "error">(
    MAPBOX_TOKEN ? "loading" : "missing-token",
  );

  useEffect(() => {
    if (!MAPBOX_TOKEN || !mapContainerRef.current) return;

    const map = new mapboxgl.Map({
      accessToken: MAPBOX_TOKEN,
      container: mapContainerRef.current,
      center: VIETNAM_CENTER,
      zoom: 5.25,
      minZoom: 3.3,
      maxZoom: 18,
      pitchWithRotate: false,
      style: "mapbox://styles/mapbox/standard",
    });

    mapRef.current = map;
    map.addControl(new mapboxgl.NavigationControl({ showCompass: false }), "top-right");
    map.once("load", () => setMapState("ready"));
    map.on("error", () => setMapState("error"));

    const resizeObserver = new ResizeObserver(() => map.resize());
    resizeObserver.observe(mapContainerRef.current);
    const markers = markersRef.current;
    const itineraryMarkers = itineraryMarkersRef.current;

    return () => {
      resizeObserver.disconnect();
      markers.clear();
      for (const marker of itineraryMarkers.values()) marker.remove();
      itineraryMarkers.clear();
      userMarkerRef.current?.remove();
      userMarkerRef.current = null;
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || mapState !== "ready") return;

    const itineraryPlaceIds = new Set(
      itinerary?.stops.map((stop) => stop.mapboxId) ?? [],
    );
    const visiblePlaces = places.filter(
      (place) => !itineraryPlaceIds.has(place.mapboxId),
    );
    const placeIds = new Set(visiblePlaces.map((place) => place.mapboxId));
    for (const [mapboxId, marker] of markersRef.current) {
      if (!placeIds.has(mapboxId)) {
        marker.remove();
        markersRef.current.delete(mapboxId);
      }
    }

    for (const place of visiblePlaces) {
      if (markersRef.current.has(place.mapboxId)) continue;
      const element = document.createElement("span");
      element.className = "map-place-marker";
      element.setAttribute("aria-label", place.name);
      const marker = new mapboxgl.Marker({ element, anchor: "bottom" })
        .setLngLat([place.longitude, place.latitude])
        .addTo(map);
      markersRef.current.set(place.mapboxId, marker);
    }
  }, [itinerary, places, mapState]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || mapState !== "ready") return;

    const routeSource = map.getSource(ITINERARY_ROUTE_SOURCE_ID);
    if (!itinerary) {
      if (map.getLayer(ITINERARY_ROUTE_LAYER_ID)) {
        map.removeLayer(ITINERARY_ROUTE_LAYER_ID);
      }
      if (routeSource) map.removeSource(ITINERARY_ROUTE_SOURCE_ID);
      return;
    }

    const routeFeature = {
      type: "Feature" as const,
      properties: {},
      geometry: itinerary.route,
    };
    if (routeSource && "setData" in routeSource) {
      routeSource.setData(routeFeature);
    } else {
      map.addSource(ITINERARY_ROUTE_SOURCE_ID, {
        type: "geojson",
        data: routeFeature,
      });
      map.addLayer({
        id: ITINERARY_ROUTE_LAYER_ID,
        type: "line",
        source: ITINERARY_ROUTE_SOURCE_ID,
        layout: {
          "line-cap": "round",
          "line-join": "round",
        },
        paint: {
          "line-color": "#236b68",
          "line-width": 5,
          "line-opacity": 0.86,
        },
      });
    }

    const bounds = new mapboxgl.LngLatBounds();
    for (const stop of itinerary.stops) {
      bounds.extend([stop.longitude, stop.latitude]);
    }
    for (const coordinate of itinerary.route.coordinates) {
      bounds.extend(coordinate);
    }
    map.fitBounds(bounds, {
      padding: { top: 120, right: 48, bottom: 80, left: 48 },
      maxZoom: 14,
      duration: 0,
    });
  }, [itinerary, mapState]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || mapState !== "ready") return;

    for (const marker of itineraryMarkersRef.current.values()) marker.remove();
    itineraryMarkersRef.current.clear();
    if (!itinerary) return;

    for (const stop of itinerary.stops) {
      const element = document.createElement("span");
      element.className = "map-itinerary-marker";
      element.textContent = String(stop.order);
      element.setAttribute(
        "aria-label",
        `Điểm dừng ${stop.order}: ${stop.name}`,
      );
      element.title = `${stop.order}. ${stop.name}`;
      const marker = new mapboxgl.Marker({ element, anchor: "center" })
        .setLngLat([stop.longitude, stop.latitude])
        .addTo(map);
      itineraryMarkersRef.current.set(stop.mapboxId, marker);
    }
  }, [itinerary, mapState]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || mapState !== "ready" || !userLocation) return;

    if (!userMarkerRef.current) {
      const element = document.createElement("span");
      element.className = "map-user-marker";
      element.setAttribute("aria-label", "Vị trí hiện tại của bạn");
      userMarkerRef.current = new mapboxgl.Marker({ element })
        .setLngLat([userLocation.longitude, userLocation.latitude])
        .addTo(map);
    } else {
      userMarkerRef.current.setLngLat([
        userLocation.longitude,
        userLocation.latitude,
      ]);
    }

    if (!itinerary) {
      map.flyTo({
        center: [userLocation.longitude, userLocation.latitude],
        zoom: Math.max(map.getZoom(), 13),
        essential: true,
      });
    }
  }, [itinerary, userLocation, mapState]);

  useEffect(() => {
    for (const [mapboxId, marker] of markersRef.current) {
      marker.getElement().classList.toggle(
        "map-place-marker-active",
        mapboxId === activePlaceId,
      );
    }
    for (const [mapboxId, marker] of itineraryMarkersRef.current) {
      marker.getElement().classList.toggle(
        "map-itinerary-marker-active",
        mapboxId === activePlaceId,
      );
    }
  }, [activePlaceId, itinerary, places, mapState]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || mapState !== "ready" || !focusRequest) return;
    map.flyTo({
      center: [focusRequest.place.longitude, focusRequest.place.latitude],
      zoom: 14,
      essential: true,
    });
  }, [focusRequest, mapState]);

  function resetView() {
    mapRef.current?.flyTo({ center: VIETNAM_CENTER, zoom: 5.25, essential: true });
  }

  return (
    <section className="map-panel" aria-label="Bản đồ du lịch tương tác">
      <div className="map-panel-header">
        <div>
          <p className="eyebrow">MAPBOX EXPLORE</p>
          <h2>Khám phá Việt Nam</h2>
          {itinerary ? (
            <p className="map-itinerary-summary" aria-label="Lộ trình đã chọn">
              {itinerary.title} · {itinerary.stops.length} điểm dừng
            </p>
          ) : null}
        </div>
        <span className={`map-status map-status-${mapState}`}>
          <span className="map-status-dot" />
          {mapState === "ready" ? "Đang tương tác" : "Bản đồ"}
        </span>
      </div>

      <div ref={mapContainerRef} className="map-container" />

      {mapState === "missing-token" ? (
        <div className="map-overlay map-overlay-message">
          <span className="map-overlay-icon" aria-hidden="true">⌖</span>
          <strong>Chưa cấu hình Mapbox</strong>
          <p>Thêm NEXT_PUBLIC_MAPBOX_ACCESS_TOKEN vào frontend/.env để hiển thị bản đồ.</p>
        </div>
      ) : null}

      {mapState === "error" ? (
        <div className="map-overlay map-overlay-message">
          <span className="map-overlay-icon" aria-hidden="true">!</span>
          <strong>Không thể tải bản đồ</strong>
          <p>Kiểm tra access token và kết nối mạng, sau đó tải lại trang.</p>
        </div>
      ) : null}

      <div className="map-caption">
        <span className="map-caption-pin" aria-hidden="true">●</span>
        <span>Kéo để di chuyển · Cuộn để phóng to</span>
        <button type="button" onClick={resetView} disabled={mapState !== "ready"}>
          Về Việt Nam
        </button>
      </div>
    </section>
  );
}
