import type { ReactNode } from "react";
import type { ChatMessage as ChatMessageType, ChatPlace } from "@/types/chat";

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
        <button
          key={`${place.mapboxId}-${match.index}`}
          type="button"
          className="place-mention"
          onMouseEnter={() => onPlaceHover(place)}
          onClick={() => onPlaceClick(place)}
        >
          {match[0]}
        </button>,
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
        <p className="message-content">
          {renderContent(message.content, message.places, onPlaceHover, onPlaceClick)}
        </p>
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
