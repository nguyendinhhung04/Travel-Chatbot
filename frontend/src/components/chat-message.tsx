import { useState, type ReactNode } from "react";
import type { ChatMessage as ChatMessageType, ChatPlace } from "@/types/chat";

/* Mapbox Places returns photo hosts dynamically, so they cannot be safely allowlisted
   for the Next.js image optimizer. The browser loads these temporary provider URLs. */
/* eslint-disable @next/next/no-img-element */

type ChatMessageProps = {
  message: ChatMessageType;
  onPlaceHover: (place: ChatPlace) => void;
  onPlaceClick: (place: ChatPlace) => void;
};

function normalizePlaceText(value: string) {
  return value.normalize("NFKC").toLocaleLowerCase("vi-VN");
}

function escapeRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function formatCategory(value: string) {
  return value.replaceAll("_", " ");
}

function safeHttpUrl(value: string | null | undefined) {
  if (!value) return null;
  try {
    const url = new URL(value);
    return url.protocol === "https:" || url.protocol === "http:" ? url.href : null;
  } catch {
    return null;
  }
}

function PlaceCard({ place }: { place: ChatPlace }) {
  const photo = place.photos?.find((item) => safeHttpUrl(item.url));
  const photoUrl = safeHttpUrl(photo?.url);
  const websiteUrl = safeHttpUrl(place.website);
  const [imageFailed, setImageFailed] = useState(false);
  const category = place.primaryCategory ?? place.categories?.[0];
  const isClosed = place.permanentlyClosed === true ||
    place.operationalStatus === "inactive" ||
    place.operationalStatus === "closed";

  return (
    <span className="place-card" role="group" aria-label={`Thông tin ${place.name}`}>
      {photo && photoUrl && !imageFailed ? (
        <img
          className="place-card-image"
          src={photoUrl}
          alt=""
          width={photo.width ?? undefined}
          height={photo.height ?? undefined}
          onError={() => setImageFailed(true)}
        />
      ) : null}
      <span className="place-card-body">
        <span className="place-card-heading">
          <strong>{place.name}</strong>
          {isClosed ? <span className="place-card-status place-card-status-closed">Đã đóng cửa</span> : null}
        </span>
        {place.brand && place.brand !== place.name ? (
          <span className="place-card-line">{place.brand}</span>
        ) : null}
        {category ? (
          <span className="place-card-category">{formatCategory(category)}</span>
        ) : null}
        {place.fullAddress ? (
          <span className="place-card-line">{place.fullAddress}</span>
        ) : null}
        {place.openingHours ? (
          <span className="place-card-line"><b>Giờ mở cửa:</b> {place.openingHours}</span>
        ) : null}
        {place.rating != null ? (
          <span className="place-card-line"><b>Đánh giá:</b> {place.rating.toFixed(1)}/5</span>
        ) : null}
        {place.phone ? (
          <a className="place-card-link" href={`tel:${place.phone}`}>{place.phone}</a>
        ) : null}
        {websiteUrl ? (
          <a
            className="place-card-link"
            href={websiteUrl}
            target="_blank"
            rel="noreferrer"
          >
            Website
          </a>
        ) : null}
      </span>
    </span>
  );
}

function PlaceMention({
  place,
  text,
  onPlaceHover,
  onPlaceClick,
}: {
  place: ChatPlace;
  text: string;
  onPlaceHover: (place: ChatPlace) => void;
  onPlaceClick: (place: ChatPlace) => void;
}) {
  const [hovered, setHovered] = useState(false);
  const [pinned, setPinned] = useState(false);

  return (
    <span
      className="place-mention-wrapper"
      onMouseEnter={() => {
        setHovered(true);
        onPlaceHover(place);
      }}
      onMouseLeave={() => setHovered(false)}
    >
      <button
        type="button"
        className="place-mention"
        aria-expanded={hovered || pinned}
        onClick={() => {
          setPinned((current) => !current);
          onPlaceClick(place);
        }}
      >
        {text}
      </button>
      {hovered || pinned ? <PlaceCard place={place} /> : null}
    </span>
  );
}

function renderContent(
  content: string,
  places: ChatPlace[] | undefined,
  onPlaceHover: (place: ChatPlace) => void,
  onPlaceClick: (place: ChatPlace) => void,
) {
  const usablePlaces = (places ?? [])
    .filter((place) => place.name.trim())
    .sort((left, right) => right.name.length - left.name.length);
  if (usablePlaces.length === 0) return content;

  const placeByName = new Map(
    usablePlaces.map((place) => [normalizePlaceText(place.name), place]),
  );
  const pattern = usablePlaces.map((place) => escapeRegExp(place.name)).join("|");
  const matcher = new RegExp(pattern, "giu");
  const parts: ReactNode[] = [];
  let cursor = 0;
  let match: RegExpExecArray | null;

  while ((match = matcher.exec(content)) !== null) {
    if (match.index > cursor) parts.push(content.slice(cursor, match.index));
    const place = placeByName.get(normalizePlaceText(match[0]));
    if (!place) {
      parts.push(match[0]);
    } else {
      parts.push(
        <PlaceMention
          key={`${place.mapboxId}-${match.index}`}
          place={place}
          text={match[0]}
          onPlaceHover={onPlaceHover}
          onPlaceClick={onPlaceClick}
        />,
      );
    }
    cursor = match.index + match[0].length;
  }

  if (cursor === 0) return content;
  if (cursor < content.length) parts.push(content.slice(cursor));
  return parts;
}

export default function ChatMessage({
  message,
  onPlaceHover,
  onPlaceClick,
}: ChatMessageProps) {
  const isUser = message.role === "user";

  return (
    <article className={`message-row ${isUser ? "message-row-user" : "message-row-assistant"}`}>
      <div className={`message-bubble ${isUser ? "message-bubble-user" : "message-bubble-assistant"}`}>
        <span className="message-author">{isUser ? "Bạn" : "Trợ lý"}</span>
        <div className="message-content">
          {renderContent(message.content, message.places, onPlaceHover, onPlaceClick)}
        </div>
        {!isUser && message.sources && message.sources.length > 0 ? (
          <div className="sources" aria-label="Nguồn tham khảo">
            <span className="sources-heading">Nguồn tham khảo</span>
            <ul>
              {message.sources.map((source) => (
                <li key={`${source.type}-${source.title}-${source.source}`}>
                  <span className="source-title">{source.title}</span>
                  <span className="source-path">
                    {source.type === "mapbox" ? source.attribution : source.source}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
    </article>
  );
}
