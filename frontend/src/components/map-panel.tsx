"use client";

import { useEffect, useRef, useState } from "react";
import mapboxgl from "mapbox-gl";
import "mapbox-gl/dist/mapbox-gl.css";
import type { ChatPlace, UserLocation } from "@/types/chat";

const VIETNAM_CENTER: [number, number] = [108.2022, 16.0544];
const MAPBOX_TOKEN = process.env.NEXT_PUBLIC_MAPBOX_ACCESS_TOKEN;

type MapPanelProps = {
  places: ChatPlace[];
  userLocation: UserLocation | null;
  activePlaceId: string | null;
  focusRequest: { place: ChatPlace; requestId: string } | null;
};

export default function MapPanel({
  places,
  userLocation,
  activePlaceId,
  focusRequest,
}: MapPanelProps) {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<mapboxgl.Map | null>(null);
  const markersRef = useRef<Map<string, mapboxgl.Marker>>(new Map());
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

    return () => {
      resizeObserver.disconnect();
      markers.clear();
      userMarkerRef.current?.remove();
      userMarkerRef.current = null;
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || mapState !== "ready") return;

    const placeIds = new Set(places.map((place) => place.mapboxId));
    for (const [mapboxId, marker] of markersRef.current) {
      if (!placeIds.has(mapboxId)) {
        marker.remove();
        markersRef.current.delete(mapboxId);
      }
    }

    for (const place of places) {
      if (markersRef.current.has(place.mapboxId)) continue;
      const element = document.createElement("span");
      element.className = "map-place-marker";
      element.setAttribute("aria-label", place.name);
      const marker = new mapboxgl.Marker({ element, anchor: "bottom" })
        .setLngLat([place.longitude, place.latitude])
        .addTo(map);
      markersRef.current.set(place.mapboxId, marker);
    }
  }, [places, mapState]);

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

    map.flyTo({
      center: [userLocation.longitude, userLocation.latitude],
      zoom: Math.max(map.getZoom(), 13),
      essential: true,
    });
  }, [userLocation, mapState]);

  useEffect(() => {
    for (const [mapboxId, marker] of markersRef.current) {
      marker.getElement().classList.toggle(
        "map-place-marker-active",
        mapboxId === activePlaceId,
      );
    }
  }, [activePlaceId, places, mapState]);

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
