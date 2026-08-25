"use client";

import { useEffect, useRef, useState } from "react";
import mapboxgl from "mapbox-gl";
import "mapbox-gl/dist/mapbox-gl.css";

const VIETNAM_CENTER: [number, number] = [108.2022, 16.0544];
const MAPBOX_TOKEN = process.env.NEXT_PUBLIC_MAPBOX_ACCESS_TOKEN;

export default function MapPanel() {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<mapboxgl.Map | null>(null);
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
    map.addControl(
      new mapboxgl.GeolocateControl({
        positionOptions: { enableHighAccuracy: true },
        trackUserLocation: true,
        showUserHeading: true,
      }),
      "top-right",
    );

    map.once("load", () => setMapState("ready"));
    map.on("error", () => setMapState("error"));

    const resizeObserver = new ResizeObserver(() => map.resize());
    resizeObserver.observe(mapContainerRef.current);

    return () => {
      resizeObserver.disconnect();
      map.remove();
      mapRef.current = null;
    };
  }, []);

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
