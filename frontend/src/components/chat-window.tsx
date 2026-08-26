"use client";

import { useEffect, useRef, useState } from "react";
import ChatComposer from "@/components/chat-composer";
import ChatEmptyState from "@/components/chat-empty-state";
import ChatMessage from "@/components/chat-message";
import type {
  ChatErrorResponse,
  ChatMessage as ChatMessageType,
  ChatPlace,
  ChatSource,
  ChatSuccessResponse,
  CurrentLocationToolCallResponse,
  UserLocation,
} from "@/types/chat";

type ChatWindowProps = {
  onPlacesReceived: (places: ChatPlace[]) => void;
  onCurrentLocationReceived: (location: UserLocation) => void;
  onPlaceHover: (place: ChatPlace) => void;
  onPlaceClick: (place: ChatPlace) => void;
};

const SUGGESTIONS = [
  "Huế có những hoạt động du lịch nào?",
  "Đà Nẵng nên đi đâu trong 2 ngày?",
  "Gợi ý lịch trình Hội An cho người mới đến",
];

const DEFAULT_ERROR = "Không thể nhận câu trả lời. Vui lòng thử lại.";

const LOCATION_ERROR = "Không thể lấy vị trí hiện tại. Hãy bật GPS và quyền vị trí rồi gửi lại câu hỏi.";

function isSource(value: unknown): value is ChatSource {
  if (
    typeof value !== "object" ||
    value === null ||
    typeof (value as ChatSource).title !== "string" ||
    typeof (value as ChatSource).source !== "string"
  ) {
    return false;
  }

  const source = value as ChatSource;
  return source.type === "knowledge_base" || (
    source.type === "mapbox" &&
    typeof source.attribution === "string"
  );
}

function isSuccessResponse(value: unknown): value is ChatSuccessResponse {
  return (
    typeof value === "object" &&
    value !== null &&
    typeof (value as ChatSuccessResponse).answer === "string" &&
    Array.isArray((value as ChatSuccessResponse).sources) &&
    (value as ChatSuccessResponse).sources.every(isSource) &&
    (!("places" in value) || isPlaceList((value as ChatSuccessResponse).places))
  );
}

function isCurrentLocationToolCall(
  value: unknown,
): value is CurrentLocationToolCallResponse {
  if (typeof value !== "object" || value === null) return false;
  const response = value as Partial<CurrentLocationToolCallResponse>;
  return (
    response.type === "client_tool_call" &&
    response.toolCall?.name === "get_current_location"
  );
}

function isPlace(value: unknown): value is ChatPlace {
  if (typeof value !== "object" || value === null) return false;
  const place = value as ChatPlace;
  return (
    typeof place.mapboxId === "string" &&
    typeof place.name === "string" &&
    Number.isFinite(place.longitude) &&
    Number.isFinite(place.latitude)
  );
}

function isPlaceList(value: unknown): value is ChatPlace[] {
  return Array.isArray(value) && value.every(isPlace);
}

function getErrorMessage(value: unknown) {
  if (
    typeof value === "object" &&
    value !== null &&
    typeof (value as ChatErrorResponse).error === "string" &&
    (value as ChatErrorResponse).error.trim()
  ) {
    return (value as ChatErrorResponse).error;
  }

  return DEFAULT_ERROR;
}

export default function ChatWindow({
  onPlacesReceived,
  onCurrentLocationReceived,
  onPlaceHover,
  onPlaceClick,
}: ChatWindowProps) {
  const [messages, setMessages] = useState<ChatMessageType[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const messagesRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const messagesElement = messagesRef.current;

    if (!messagesElement) return;

    messagesElement.scrollTo({
      top: messagesElement.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, loading, error]);

  function getCurrentLocation(): Promise<UserLocation> {
    if (!window.isSecureContext || !navigator.geolocation) {
      return Promise.reject(new Error(LOCATION_ERROR));
    }

    return new Promise((resolve, reject) => {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          const { longitude, latitude } = position.coords;
          if (
            !Number.isFinite(longitude) ||
            !Number.isFinite(latitude) ||
            longitude < -180 ||
            longitude > 180 ||
            latitude < -90 ||
            latitude > 90
          ) {
            reject(new Error(LOCATION_ERROR));
            return;
          }
          resolve({ longitude, latitude });
        },
        () => reject(new Error(LOCATION_ERROR)),
        {
          enableHighAccuracy: true,
          timeout: 10_000,
          maximumAge: 30_000,
        },
      );
    });
  }

  async function requestChat(
    question: string,
    currentLocation?: UserLocation,
  ): Promise<unknown> {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: question,
        ...(currentLocation === undefined
          ? {}
          : { current_location: currentLocation }),
      }),
    });
    const payload: unknown = await response.json().catch(() => null);

    if (!response.ok) {
      throw new Error(getErrorMessage(payload));
    }
    return payload;
  }

  function appendAssistantAnswer(payload: ChatSuccessResponse) {
    const assistantMessage: ChatMessageType = {
      id: crypto.randomUUID(),
      role: "assistant",
      content: payload.answer,
      sources: payload.sources,
      places: payload.places ?? [],
    };

    setMessages((current) => [...current, assistantMessage]);
    onPlacesReceived(payload.places ?? []);
    setInput("");
  }

  async function sendMessage() {
    const question = input.trim();
    if (!question || loading) return;

    const userMessage: ChatMessageType = {
      id: crypto.randomUUID(),
      role: "user",
      content: question,
    };

    setMessages((current) => [...current, userMessage]);
    setError(null);
    setLoading(true);

    try {
      let payload = await requestChat(question);
      if (isCurrentLocationToolCall(payload)) {
        const currentLocation = await getCurrentLocation();
        onCurrentLocationReceived(currentLocation);
        payload = await requestChat(question, currentLocation);
        if (isCurrentLocationToolCall(payload)) {
          throw new Error(LOCATION_ERROR);
        }
      }

      if (!isSuccessResponse(payload)) throw new Error(DEFAULT_ERROR);
      appendAssistantAnswer(payload);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : DEFAULT_ERROR);
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="chat-shell" aria-label="Trợ lý du lịch">
      <header className="chat-header">
        <div className="brand-mark" aria-hidden="true">✦</div>
        <div>
          <p className="eyebrow">TRAVEL RAG</p>
          <h1>Trợ lý du lịch</h1>
        </div>
        <span className="status-pill"><span className="status-dot" /> Sẵn sàng</span>
      </header>

      <div
        ref={messagesRef}
        className="messages"
        aria-live="polite"
        aria-label="Lịch sử trò chuyện"
      >
        {messages.length === 0 ? (
          <ChatEmptyState
            suggestions={SUGGESTIONS}
            onSuggestionSelect={setInput}
          />
        ) : (
          messages.map((message) => (
            <ChatMessage
              key={message.id}
              message={message}
              onPlaceHover={onPlaceHover}
              onPlaceClick={onPlaceClick}
            />
          ))
        )}
        {error ? <p className="error-message" role="alert">{error}</p> : null}
        {loading ? <p className="loading-message">Đang trả lời<span className="loading-dots" aria-hidden="true">...</span></p> : null}
      </div>

      <ChatComposer
        value={input}
        loading={loading}
        onChange={setInput}
        onSubmit={() => void sendMessage()}
      />
    </section>
  );
}
