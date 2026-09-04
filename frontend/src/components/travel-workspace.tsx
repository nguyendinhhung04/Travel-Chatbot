"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import ChatWindow from "@/components/chat-window";
import MapPanel from "@/components/map-panel";
import type {
  ChatItinerary,
  ChatMessage,
  ChatPlace,
  ConversationDetailsResponse,
  ConversationSummary,
  PersistedConversationMessage,
  UserLocation,
} from "@/types/chat";
import { isPersistedItinerary } from "@/utils/itinerary";

const MIN_CHAT_WIDTH = 28;
const MAX_CHAT_WIDTH = 55;

type CompletedTurn = {
  turnId: string;
  userContent: string;
  assistantMessage: ChatMessage;
};

function isConversationDetails(value: unknown): value is ConversationDetailsResponse {
  return typeof value === "object" && value !== null
    && typeof (value as ConversationDetailsResponse).conversation === "object"
    && Array.isArray((value as ConversationDetailsResponse).messages);
}

function toChatMessage(message: PersistedConversationMessage): ChatMessage | null {
  if (message.role !== "user" && message.role !== "assistant") return null;
  return {
    id: message.id,
    role: message.role,
    content: message.content,
    ...(message.sources ? { sources: message.sources } : {}),
    ...(message.places ? { places: message.places } : {}),
    ...(message.itinerary ? { itinerary: message.itinerary } : {}),
  } as ChatMessage;
}

function comparePersistedMessages(
  left: PersistedConversationMessage,
  right: PersistedConversationMessage,
) {
  const turnOrder = left.turnIndex - right.turnIndex;
  if (turnOrder !== 0) return turnOrder;

  const roleOrder = (role: PersistedConversationMessage["role"]) =>
    role === "user" ? 0 : 1;
  const messageRoleOrder = roleOrder(left.role) - roleOrder(right.role);
  if (messageRoleOrder !== 0) return messageRoleOrder;

  return left.createdAt.localeCompare(right.createdAt) || left.id.localeCompare(right.id);
}

export default function TravelWorkspace() {
  const [chatWidth, setChatWidth] = useState(38);
  const [isDragging, setIsDragging] = useState(false);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [places, setPlaces] = useState<ChatPlace[]>([]);
  const [itinerary, setItinerary] = useState<ChatItinerary | null>(null);
  const [userLocation, setUserLocation] = useState<UserLocation | null>(null);
  const [activePlaceId, setActivePlaceId] = useState<string | null>(null);
  const [focusRequest, setFocusRequest] = useState<{
    place: ChatPlace;
    requestId: string;
  } | null>(null);
  const [pendingTurn, setPendingTurn] = useState<CompletedTurn | null>(null);
  const [persistencePending, setPersistencePending] = useState(false);
  const [persistenceError, setPersistenceError] = useState<string | null>(null);
  const [conversationError, setConversationError] = useState<string | null>(null);
  const workspaceRef = useRef<HTMLDivElement>(null);
  const itineraryLoadRef = useRef<AbortController | null>(null);
  const conversationLoadRef = useRef<AbortController | null>(null);
  const persistenceAbortRef = useRef<AbortController | null>(null);
  const persistenceRequestRef = useRef(0);

  const addPlaces = useCallback((nextPlaces: ChatPlace[]) => {
    if (nextPlaces.length === 0) return;
    setPlaces((current) => {
      const byId = new Map(current.map((place) => [place.mapboxId, place]));
      for (const place of nextPlaces) byId.set(place.mapboxId, place);
      return [...byId.values()];
    });
  }, []);

  const replacePlaces = useCallback((nextPlaces: ChatPlace[]) => {
    setPlaces(nextPlaces);
  }, []);

  const updateItinerary = useCallback((nextItinerary: ChatItinerary | null) => {
    setItinerary(nextItinerary);
    if (!nextItinerary) return;

    const itineraryPlaceIds = new Set(
      nextItinerary.stops.map((stop) => stop.mapboxId),
    );
    setPlaces((current) =>
      current.filter((place) => !itineraryPlaceIds.has(place.mapboxId)),
    );
  }, []);

  const resetConversationState = useCallback(() => {
    itineraryLoadRef.current?.abort();
    itineraryLoadRef.current = null;
    conversationLoadRef.current?.abort();
    conversationLoadRef.current = null;
    persistenceAbortRef.current?.abort();
    persistenceAbortRef.current = null;
    persistenceRequestRef.current += 1;
    setActiveConversationId(null);
    setMessages([]);
    replacePlaces([]);
    setItinerary(null);
    setActivePlaceId(null);
    setFocusRequest(null);
    setUserLocation(null);
    setPendingTurn(null);
    setPersistencePending(false);
    setPersistenceError(null);
    setConversationError(null);
  }, [replacePlaces]);

  const upsertConversation = useCallback((conversation: ConversationSummary) => {
    setConversations((current) => [
      conversation,
      ...current.filter((item) => item.id !== conversation.id),
    ].sort((left, right) => right.updatedAt.localeCompare(left.updatedAt)));
  }, []);

  const persistTurn = useCallback(async (turn: CompletedTurn) => {
    persistenceAbortRef.current?.abort();
    const controller = new AbortController();
    persistenceAbortRef.current = controller;
    const requestId = persistenceRequestRef.current + 1;
    persistenceRequestRef.current = requestId;
    setPersistencePending(true);
    setPersistenceError(null);
    const endpoint = activeConversationId
      ? `/api/conversations/${encodeURIComponent(activeConversationId)}/turns`
      : "/api/conversations";
    const assistant = turn.assistantMessage;
    try {
      const response = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: controller.signal,
        body: JSON.stringify({
          turnId: turn.turnId,
          userMessage: { content: turn.userContent },
          assistantMessage: {
            content: assistant.content,
            sources: assistant.sources ?? [],
            places: assistant.places ?? [],
            itinerary: assistant.itinerary ?? null,
          },
        }),
      });
      const payload: unknown = await response.json().catch(() => null);
      if (requestId !== persistenceRequestRef.current) return;
      if (!response.ok || !isConversationDetails(payload)) {
        throw new Error(
          typeof payload === "object" && payload !== null && typeof (payload as { error?: unknown }).error === "string"
            ? (payload as { error: string }).error
            : "Không thể lưu cuộc trò chuyện.",
        );
      }
      setActiveConversationId(payload.conversation.id);
      upsertConversation(payload.conversation);
      setPendingTurn(null);
    } catch (error) {
      if (requestId !== persistenceRequestRef.current) return;
      if (error instanceof DOMException && error.name === "AbortError") return;
      setPersistenceError(error instanceof Error ? error.message : "Không thể lưu cuộc trò chuyện.");
    } finally {
      if (requestId === persistenceRequestRef.current) {
        persistenceAbortRef.current = null;
        setPersistencePending(false);
      }
    }
  }, [activeConversationId, upsertConversation]);

  const handleTurnCompleted = useCallback((turn: CompletedTurn) => {
    setPendingTurn(turn);
    void persistTurn(turn);
  }, [persistTurn]);

  const retryPersistence = useCallback(() => {
    if (pendingTurn) void persistTurn(pendingTurn);
  }, [pendingTurn, persistTurn]);

  const restoreConversation = useCallback((payload: ConversationDetailsResponse) => {
    const sortedMessages = [...payload.messages].sort(comparePersistedMessages);
    const nextMessages = sortedMessages
      .map(toChatMessage)
      .filter((message): message is ChatMessage => message !== null);
    const byPlaceId = new Map<string, ChatPlace>();
    for (const message of nextMessages) {
      for (const place of message.places ?? []) byPlaceId.set(place.mapboxId, place);
    }
    const nextItinerary = [...sortedMessages]
      .reverse()
      .find((message) => message.itinerary)?.itinerary ?? null;
    const itineraryPlaceIds = new Set(
      nextItinerary?.stops.map((stop) => stop.mapboxId) ?? [],
    );
    setMessages(nextMessages);
    setItinerary(nextItinerary);
    replacePlaces([...byPlaceId.values()].filter((place) => !itineraryPlaceIds.has(place.mapboxId)));
    setActivePlaceId(null);
    setFocusRequest(null);
    setUserLocation(null);
  }, [replacePlaces]);

  const openConversation = useCallback(async (conversationId: string) => {
    conversationLoadRef.current?.abort();
    const controller = new AbortController();
    conversationLoadRef.current = controller;
    itineraryLoadRef.current?.abort();
    persistenceAbortRef.current?.abort();
    persistenceAbortRef.current = null;
    persistenceRequestRef.current += 1;
    setPersistencePending(false);
    setConversationError(null);
    setPendingTurn(null);
    setPersistenceError(null);
    setMessages([]);
    replacePlaces([]);
    setItinerary(null);
    setActivePlaceId(null);
    setFocusRequest(null);
    setUserLocation(null);
    try {
      const response = await fetch(`/api/conversations/${encodeURIComponent(conversationId)}`, {
        cache: "no-store",
        signal: controller.signal,
      });
      const payload: unknown = await response.json().catch(() => null);
      if (!response.ok || !isConversationDetails(payload)) {
        throw new Error("Không thể mở cuộc trò chuyện.");
      }
      if (controller.signal.aborted) return;
      setActiveConversationId(payload.conversation.id);
      restoreConversation(payload);
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      setConversationError(error instanceof Error ? error.message : "Không thể mở cuộc trò chuyện.");
    } finally {
      if (conversationLoadRef.current === controller) conversationLoadRef.current = null;
    }
  }, [replacePlaces, restoreConversation]);

  const deleteConversation = useCallback(async (conversationId: string) => {
    setConversationError(null);
    try {
      const response = await fetch(`/api/conversations/${encodeURIComponent(conversationId)}`, {
        method: "DELETE",
      });
      if (!response.ok) throw new Error("Không thể xóa cuộc trò chuyện.");
      setConversations((current) => current.filter((item) => item.id !== conversationId));
      if (activeConversationId === conversationId) resetConversationState();
    } catch (error) {
      setConversationError(error instanceof Error ? error.message : "Không thể xóa cuộc trò chuyện.");
    }
  }, [activeConversationId, resetConversationState]);

  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/conversations", { cache: "no-store", signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) return null;
        return response.json() as Promise<unknown>;
      })
      .then((payload) => {
        if (!Array.isArray(payload)) return;
        setConversations(payload as ConversationSummary[]);
      })
      .catch(() => undefined);
    return () => controller.abort();
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    itineraryLoadRef.current = controller;
    fetch("/api/itineraries", {
      cache: "no-store",
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) return null;
        return response.json() as Promise<unknown>;
      })
      .then((payload) => {
        if (isPersistedItinerary(payload)) updateItinerary(payload);
      })
      .catch(() => undefined);
    return () => {
      controller.abort();
      if (itineraryLoadRef.current === controller) itineraryLoadRef.current = null;
    };
  }, [updateItinerary]);

  function handlePlaceHover(place: ChatPlace) {
    setActivePlaceId(place.mapboxId);
  }

  function handlePlaceClick(place: ChatPlace) {
    setActivePlaceId(place.mapboxId);
    setFocusRequest({ place, requestId: crypto.randomUUID() });
  }

  function updateChatWidth(clientX: number) {
    const workspace = workspaceRef.current;
    if (!workspace) return;

    const bounds = workspace.getBoundingClientRect();
    const nextWidth = ((clientX - bounds.left) / bounds.width) * 100;
    setChatWidth(Math.min(MAX_CHAT_WIDTH, Math.max(MIN_CHAT_WIDTH, nextWidth)));
  }

  function handlePointerDown(event: React.PointerEvent<HTMLDivElement>) {
    event.currentTarget.setPointerCapture(event.pointerId);
    setIsDragging(true);
  }

  function handlePointerMove(event: React.PointerEvent<HTMLDivElement>) {
    if (isDragging) updateChatWidth(event.clientX);
  }

  function handlePointerUp(event: React.PointerEvent<HTMLDivElement>) {
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    setIsDragging(false);
  }

  return (
    <div className="workspace-layout">
      <aside className="conversation-history" aria-label="Lịch sử trò chuyện">
        <div className="conversation-history-header">
          <div>
            <p className="eyebrow">HISTORY</p>
            <h2>Cuộc trò chuyện</h2>
          </div>
          <button type="button" onClick={resetConversationState}>Mới</button>
        </div>
        {conversationError ? <p className="conversation-error" role="alert">{conversationError}</p> : null}
        <div className="conversation-list">
          {conversations.length === 0 ? (
            <p className="conversation-empty">Chưa có cuộc trò chuyện đã lưu.</p>
          ) : conversations.map((conversation) => (
            <div
              className={`conversation-item ${activeConversationId === conversation.id ? "conversation-item-active" : ""}`}
              key={conversation.id}
            >
              <button type="button" className="conversation-open" onClick={() => void openConversation(conversation.id)}>
                <strong>{conversation.title}</strong>
                <span>{conversation.lastMessagePreview || "Chưa có tin nhắn"}</span>
              </button>
              <button
                type="button"
                className="conversation-delete"
                aria-label={`Xóa ${conversation.title}`}
                onClick={() => void deleteConversation(conversation.id)}
              >
                ×
              </button>
            </div>
          ))}
        </div>
      </aside>
      <div
        ref={workspaceRef}
        className={`experience-shell ${isDragging ? "experience-shell-dragging" : ""}`}
        style={{ "--chat-width": `${chatWidth}%` } as React.CSSProperties}
      >
        <ChatWindow
        conversationId={activeConversationId}
        messages={messages}
        onMessagesChange={setMessages}
        onNewConversation={resetConversationState}
        activeItineraryId={itinerary?.id ?? null}
        activeItineraryVersion={itinerary?.version ?? null}
        onPlacesReceived={addPlaces}
        onItineraryReceived={updateItinerary}
        onCurrentLocationReceived={setUserLocation}
        onPlaceHover={handlePlaceHover}
          onPlaceClick={handlePlaceClick}
          onTurnCompleted={handleTurnCompleted}
          persistencePending={persistencePending || pendingTurn !== null}
          persistenceError={persistenceError}
          onRetryPersistence={retryPersistence}
        />
        <div
          className="workspace-divider"
        role="separator"
        aria-label="Điều chỉnh kích thước khung chat và bản đồ"
        aria-orientation="vertical"
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerCancel={handlePointerUp}
        >
          <span className="workspace-divider-grip" aria-hidden="true" />
        </div>
        <MapPanel
          places={places}
          itinerary={itinerary}
          userLocation={userLocation}
          activePlaceId={activePlaceId}
          focusRequest={focusRequest}
        />
      </div>
    </div>
  );
}
