"use client";

import { useEffect, useRef, useState } from "react";
import ChatComposer from "@/components/chat-composer";
import ChatEmptyState from "@/components/chat-empty-state";
import ChatMessage from "@/components/chat-message";
import QuickRecommendations from "@/components/quick-recommendations";
import { getMockRecommendations } from "@/data/mock-recommendations";
import type {
  ChatErrorResponse,
  ChatMessage as ChatMessageType,
  ChatPlace,
  PlaceRecommendation,
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

const MAX_CONVERSATION_TURNS = 3;
const MAX_HISTORY_MESSAGES = MAX_CONVERSATION_TURNS * 2;
const CHAT_STORAGE_KEY = "travel_chat_messages";

function trimMessages(messages: ChatMessageType[]) {
  return messages.slice(-MAX_HISTORY_MESSAGES);
}

function withoutPendingUserMessage(messages: ChatMessageType[]) {
  return messages.at(-1)?.role === "user" ? messages.slice(0, -1) : messages;
}

function isStoredMessage(value: unknown): value is ChatMessageType {
  if (typeof value !== "object" || value === null) return false;

  const message = value as Partial<ChatMessageType>;
  return (
    (message.role === "user" || message.role === "assistant") &&
    typeof message.content === "string" &&
    message.content.trim().length > 0
  );
}

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

function isRecommendation(value: unknown): value is PlaceRecommendation {
  if (!isPlace(value)) return false;
  const recommendation = value as PlaceRecommendation;
  return (
    typeof recommendation.category === "string" &&
    typeof recommendation.distance === "string" &&
    (recommendation.accent === "sunset" ||
      recommendation.accent === "river" ||
      recommendation.accent === "garden")
  );
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
  const [storageLoaded, setStorageLoaded] = useState(false);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const messagesRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      try {
        const stored = window.localStorage.getItem(CHAT_STORAGE_KEY);
        if (stored) {
          const parsed: unknown = JSON.parse(stored);
          if (Array.isArray(parsed)) {
            const restoredMessages = trimMessages(parsed.filter(isStoredMessage)).map(
              (message) => ({
                ...message,
                id: crypto.randomUUID(),
                recommendations: Array.isArray(message.recommendations)
                  ? message.recommendations.filter(isRecommendation)
                  : [],
              }),
            );
            setMessages(restoredMessages);
            onPlacesReceived(
              restoredMessages.flatMap((message) => message.places ?? []).filter(isPlace),
            );
          }
        }
      } catch {
        try {
          window.localStorage.removeItem(CHAT_STORAGE_KEY);
        } catch {
          // Ignore storage cleanup failures and keep the in-memory state empty.
        }
      } finally {
        setStorageLoaded(true);
      }
    }, 0);

    return () => window.clearTimeout(timeoutId);
  }, [onPlacesReceived]);

  useEffect(() => {
    if (!storageLoaded) return;
    try {
      const completedMessages = withoutPendingUserMessage(messages);
      const messagesWithoutTemporaryPlaceData = trimMessages(completedMessages).map(
        ({ role, content, sources }) => ({ role, content, sources }),
      );
      window.localStorage.setItem(
        CHAT_STORAGE_KEY,
        JSON.stringify(messagesWithoutTemporaryPlaceData),
      );
    } catch {
      // Continue with in-memory history when browser storage is unavailable.
    }
  }, [messages, storageLoaded]);

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
    history: Array<Pick<ChatMessageType, "role" | "content">>,
    currentLocation?: UserLocation,
  ): Promise<unknown> {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: question,
        history,
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

  function appendAssistantAnswer(payload: ChatSuccessResponse, question: string) {
    const recommendations = getMockRecommendations(question);
    const places = [...(payload.places ?? []), ...recommendations];
    const assistantMessage: ChatMessageType = {
      id: crypto.randomUUID(),
      role: "assistant",
      content: payload.answer,
      sources: payload.sources,
      places,
      recommendations,
    };

    setMessages((current) => trimMessages([...current, assistantMessage]));
    onPlacesReceived(places);
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

    const history = withoutPendingUserMessage(messages)
      .slice(-MAX_HISTORY_MESSAGES)
      .map(({ role, content }) => ({ role, content }));

    setMessages((current) => [...current, userMessage]);
    setError(null);
    setLoading(true);

    try {
      let payload = await requestChat(question, history);
      if (isCurrentLocationToolCall(payload)) {
        const currentLocation = await getCurrentLocation();
        onCurrentLocationReceived(currentLocation);
        payload = await requestChat(question, history, currentLocation);
        if (isCurrentLocationToolCall(payload)) {
          throw new Error(LOCATION_ERROR);
        }
      }

      if (!isSuccessResponse(payload)) throw new Error(DEFAULT_ERROR);
      appendAssistantAnswer(payload, question);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : DEFAULT_ERROR);
    } finally {
      setLoading(false);
    }
  }

  function startNewConversation() {
    setMessages([]);
    setError(null);
    setInput("");
    try {
      window.localStorage.removeItem(CHAT_STORAGE_KEY);
    } catch {
      // Ignore storage cleanup failures.
    }
  }

  const latestMessage = messages.at(-1);
  const recommendations = latestMessage?.role === "assistant"
    ? latestMessage.recommendations ?? []
    : [];

  return (
    <section className="chat-shell" aria-label="Trợ lý du lịch">
      <header className="chat-header">
        <div className="brand-mark" aria-hidden="true">✦</div>
        <div>
          <p className="eyebrow">TRAVEL RAG</p>
          <h1>Trợ lý du lịch</h1>
        </div>
        <span className="status-pill"><span className="status-dot" /> Sẵn sàng</span>
        <button
          type="button"
          className="new-chat-button"
          onClick={startNewConversation}
          disabled={loading}
        >
          Cuộc trò chuyện mới
        </button>
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

      <QuickRecommendations
        recommendations={recommendations}
        onPlaceHover={onPlaceHover}
        onPlaceClick={onPlaceClick}
      />

      <ChatComposer
        value={input}
        loading={loading}
        onChange={setInput}
        onSubmit={() => void sendMessage()}
      />
    </section>
  );
}
