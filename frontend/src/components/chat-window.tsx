"use client";

import { useEffect, useRef, useState } from "react";
import ChatComposer from "@/components/chat-composer";
import ChatEmptyState from "@/components/chat-empty-state";
import ChatMessage from "@/components/chat-message";
import QuickRecommendations from "@/components/quick-recommendations";
import { getMockRecommendations } from "@/data/mock-recommendations";
import { LiveTranscriptionSession } from "@/lib/live-transcription";
import type {
  ChatErrorResponse,
  ChatItinerary,
  ChatMessage as ChatMessageType,
  ChatPlace,
  PlaceRecommendation,
  ChatSource,
  ChatSuccessResponse,
  CurrentLocationToolCallResponse,
  UserLocation,
} from "@/types/chat";

type ChatWindowProps = {
  activeItineraryId: string | null;
  activeItineraryVersion: number | null;
  onPlacesReceived: (places: ChatPlace[]) => void;
  onItineraryReceived: (itinerary: ChatItinerary | null) => void;
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
type SpeechState = "idle" | "requesting" | "listening" | "stopping";

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
    (!("places" in value) || isPlaceList((value as ChatSuccessResponse).places)) &&
    (!("itinerary" in value) || isItinerary((value as ChatSuccessResponse).itinerary))
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

function isItineraryStop(value: unknown): value is ChatItinerary["stops"][number] {
  if (typeof value !== "object" || value === null) return false;
  const stop = value as Partial<ChatItinerary["stops"][number]>;
  const { longitude, latitude, order, inputIndex } = stop;
  return (
    typeof stop.mapboxId === "string" &&
    stop.mapboxId.trim().length > 0 &&
    typeof stop.name === "string" &&
    stop.name.trim().length > 0 &&
    typeof longitude === "number" &&
    Number.isFinite(longitude) &&
    typeof latitude === "number" &&
    Number.isFinite(latitude) &&
    longitude >= -180 &&
    longitude <= 180 &&
    latitude >= -90 &&
    latitude <= 90 &&
    typeof order === "number" &&
    Number.isInteger(order) &&
    typeof inputIndex === "number" &&
    Number.isInteger(inputIndex) &&
    order >= 1 &&
    inputIndex >= 0 &&
    (stop.reason === undefined || stop.reason === null || typeof stop.reason === "string")
  );
}

function isItinerary(value: unknown): value is ChatItinerary {
  if (typeof value !== "object" || value === null) return false;
  const itinerary = value as Partial<ChatItinerary>;
  const {
    durationDays,
    durationNights,
    distanceMeters,
    durationSeconds,
  } = itinerary;
  if (
    typeof itinerary.id !== "string" ||
    !/^[a-f\d]{24}$/i.test(itinerary.id) ||
    typeof itinerary.version !== "number" ||
    !Number.isInteger(itinerary.version) ||
    itinerary.version < 1 ||
    typeof itinerary.title !== "string" ||
    itinerary.title.trim().length === 0 ||
    typeof itinerary.destination !== "string" ||
    itinerary.destination.trim().length === 0 ||
    typeof durationDays !== "number" ||
    !Number.isInteger(durationDays) ||
    typeof durationNights !== "number" ||
    !Number.isInteger(durationNights) ||
    durationDays < 1 ||
    durationNights < 0 ||
    (itinerary.profile !== "driving" &&
      itinerary.profile !== "walking" &&
      itinerary.profile !== "cycling") ||
    typeof distanceMeters !== "number" ||
    !Number.isFinite(distanceMeters) ||
    typeof durationSeconds !== "number" ||
    !Number.isFinite(durationSeconds) ||
    distanceMeters < 0 ||
    durationSeconds < 0 ||
    !Array.isArray(itinerary.stops) ||
    itinerary.stops.length < 2 ||
    itinerary.stops.length > 12 ||
    !itinerary.stops.every(isItineraryStop) ||
    !itinerary.route ||
    itinerary.route.type !== "LineString" ||
    !Array.isArray(itinerary.route.coordinates) ||
    itinerary.route.coordinates.length < 2
  ) {
    return false;
  }

  const stops = itinerary.stops;
  const mapboxIds = new Set<string>();
  const inputIndexes = new Set<number>();
  for (let index = 0; index < stops.length; index += 1) {
    const stop = stops[index];
    if (
      stop.order !== index + 1 ||
      mapboxIds.has(stop.mapboxId) ||
      inputIndexes.has(stop.inputIndex)
    ) {
      return false;
    }
    mapboxIds.add(stop.mapboxId);
    inputIndexes.add(stop.inputIndex);
  }
  if (
    [...inputIndexes].sort((left, right) => left - right).join(",") !==
    stops.map((_stop, index) => index).join(",")
  ) {
    return false;
  }

  return itinerary.route.coordinates.every(
    (coordinate) =>
      Array.isArray(coordinate) &&
      coordinate.length === 2 &&
      Number.isFinite(coordinate[0]) &&
      Number.isFinite(coordinate[1]) &&
      coordinate[0] >= -180 &&
      coordinate[0] <= 180 &&
      coordinate[1] >= -90 &&
      coordinate[1] <= 90,
  );
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
  activeItineraryId,
  activeItineraryVersion,
  onPlacesReceived,
  onItineraryReceived,
  onCurrentLocationReceived,
  onPlaceHover,
  onPlaceClick,
}: ChatWindowProps) {
  const [messages, setMessages] = useState<ChatMessageType[]>([]);
  const [storageLoaded, setStorageLoaded] = useState(false);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [speechState, setSpeechState] = useState<SpeechState>("idle");
  const [speechError, setSpeechError] = useState<string | null>(null);
  const messagesRef = useRef<HTMLDivElement>(null);
  const speechSessionRef = useRef<LiveTranscriptionSession | null>(null);
  const speechStateRef = useRef<SpeechState>("idle");
  const speechDraftRef = useRef("");
  const speechSegmentsRef = useRef<string[]>([]);
  const speechInterimRef = useRef("");
  const speechFinalizeResolveRef = useRef<(() => void) | null>(null);
  const speechFinalizeTimerRef = useRef<number | null>(null);

  function setSpeechMode(nextState: SpeechState) {
    speechStateRef.current = nextState;
    setSpeechState(nextState);
  }

  function renderSpeechInput() {
    const spokenText = [
      ...speechSegmentsRef.current,
      speechInterimRef.current,
    ]
      .map((text) => text.trim())
      .filter(Boolean)
      .join(" ");
    const draft = speechDraftRef.current.trim();
    setInput(spokenText ? `${draft}${draft ? " " : ""}${spokenText}` : draft);
  }

  function resolveSpeechFinalize() {
    if (speechFinalizeTimerRef.current !== null) {
      window.clearTimeout(speechFinalizeTimerRef.current);
      speechFinalizeTimerRef.current = null;
    }
    speechFinalizeResolveRef.current?.();
    speechFinalizeResolveRef.current = null;
  }

  async function startSpeech() {
    if (loading || speechStateRef.current !== "idle") return;

    speechDraftRef.current = input;
    speechSegmentsRef.current = [];
    speechInterimRef.current = "";
    setSpeechError(null);
    setSpeechMode("requesting");
    const session = new LiveTranscriptionSession({
      onInterim: (text) => {
        speechInterimRef.current = text;
        renderSpeechInput();
      },
      onFinal: (text) => {
        const finalized = text.trim();
        if (finalized) speechSegmentsRef.current.push(finalized);
        speechInterimRef.current = "";
        renderSpeechInput();
        resolveSpeechFinalize();
      },
      onError: (sessionError) => {
        setSpeechError(sessionError.message);
        resolveSpeechFinalize();
        if (speechStateRef.current !== "stopping") {
          setSpeechMode("idle");
          if (speechSessionRef.current === session) {
            speechSessionRef.current = null;
            void session.close();
          }
        }
      },
    });
    speechSessionRef.current = session;

    try {
      await session.start();
      if (speechSessionRef.current !== session) return;
      setSpeechMode("listening");
    } catch (startError) {
      const wasCancelled = speechSessionRef.current !== session;
      if (speechSessionRef.current === session) speechSessionRef.current = null;
      if (wasCancelled) {
        setSpeechMode("idle");
        return;
      }
      setSpeechError(
        startError instanceof Error
          ? startError.message
          : "Không thể khởi tạo microphone.",
      );
      setSpeechMode("idle");
    }
  }

  async function stopSpeech() {
    if (
      speechStateRef.current !== "listening" &&
      speechStateRef.current !== "requesting"
    ) return;
    const session = speechSessionRef.current;
    if (!session) {
      setSpeechMode("idle");
      return;
    }

    const wasRequesting = speechStateRef.current === "requesting";
    setSpeechError(null);
    setSpeechMode("stopping");

    // Allow cancelling while token/WebSocket setup is still pending.
    if (wasRequesting) {
      // The session is still in the requesting phase when stop is clicked.
      // Closing it rejects the pending setup promise and releases the mic.
      speechSessionRef.current = null;
      await session.close();
      setSpeechMode("idle");
      return;
    }

    const finalized = new Promise<void>((resolve) => {
      speechFinalizeResolveRef.current = resolve;
      speechFinalizeTimerRef.current = window.setTimeout(resolve, 2_000);
    });

    try {
      await session.end();
      await finalized;
    } catch (stopError) {
      setSpeechError(
        stopError instanceof Error
          ? stopError.message
          : "Không thể dừng microphone.",
      );
    } finally {
      resolveSpeechFinalize();
      await session.close();
      if (speechSessionRef.current === session) speechSessionRef.current = null;
      setSpeechMode("idle");
    }
  }

  useEffect(() => () => {
    void speechSessionRef.current?.close();
  }, []);

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
        ...(activeItineraryId === null
          ? {}
          : { active_itinerary_id: activeItineraryId }),
        ...(activeItineraryVersion === null
          ? {}
          : { active_itinerary_version: activeItineraryVersion }),
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
    const itineraryPlaceIds = new Set(
      payload.itinerary?.stops.map((stop) => stop.mapboxId) ?? [],
    );
    onPlacesReceived(
      places.filter((place) => !itineraryPlaceIds.has(place.mapboxId)),
    );
    if (payload.itinerary) onItineraryReceived(payload.itinerary);
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
    void speechSessionRef.current?.close();
    speechSessionRef.current = null;
    resolveSpeechFinalize();
    setSpeechMode("idle");
    setSpeechError(null);
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
        speechState={speechState}
        speechError={speechError}
        onChange={setInput}
        onSubmit={() => void sendMessage()}
        onStartSpeech={() => void startSpeech()}
        onStopSpeech={() => void stopSpeech()}
      />
    </section>
  );
}
