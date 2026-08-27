"use client";

import { useRef } from "react";
import type { ChatPlace, PlaceRecommendation } from "@/types/chat";

type QuickRecommendationsProps = {
  recommendations: PlaceRecommendation[];
  onPlaceHover: (place: ChatPlace) => void;
  onPlaceClick: (place: ChatPlace) => void;
};

export default function QuickRecommendations({
  recommendations,
  onPlaceHover,
  onPlaceClick,
}: QuickRecommendationsProps) {
  const listRef = useRef<HTMLDivElement>(null);

  if (recommendations.length === 0) return null;

  function scrollRecommendations(direction: "previous" | "next") {
    listRef.current?.scrollBy({
      left: direction === "next" ? 230 : -230,
      behavior: "smooth",
    });
  }

  return (
    <section className="quick-recommendations" aria-label="Gợi ý nhanh cho bạn">
      <div className="quick-recommendations-header">
        <div className="quick-recommendations-title">
          <span aria-hidden="true">✦</span>
          <strong>Gợi ý nhanh cho bạn</strong>
          <span className="quick-recommendations-mock">Mock</span>
        </div>
        <div className="quick-recommendations-controls">
          <button
            type="button"
            aria-label="Xem gợi ý trước"
            onClick={() => scrollRecommendations("previous")}
          >
            ‹
          </button>
          <button
            type="button"
            aria-label="Xem gợi ý tiếp theo"
            onClick={() => scrollRecommendations("next")}
          >
            ›
          </button>
        </div>
      </div>

      <div ref={listRef} className="quick-recommendations-list">
        {recommendations.map((place) => (
          <button
            key={place.mapboxId}
            type="button"
            className="quick-recommendation-card"
            onMouseEnter={() => onPlaceHover(place)}
            onFocus={() => onPlaceHover(place)}
            onClick={() => onPlaceClick(place)}
            aria-label={`Xem ${place.name} trên bản đồ`}
          >
            <span className={`quick-recommendation-image quick-recommendation-image-${place.accent}`} aria-hidden="true">
              <span>{place.accent === "sunset" ? "⌂" : place.accent === "river" ? "⌁" : "✿"}</span>
            </span>
            <span className="quick-recommendation-content">
              <strong>{place.name}</strong>
              <span className={`quick-recommendation-category quick-recommendation-category-${place.accent}`}>
                {place.category}
              </span>
              <span className="quick-recommendation-distance">{place.distance}</span>
              <span className="quick-recommendation-map-link">Xem trên bản đồ <span aria-hidden="true">⌖</span></span>
            </span>
          </button>
        ))}
      </div>
    </section>
  );
}
