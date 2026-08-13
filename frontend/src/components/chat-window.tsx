"use client";

import { useEffect, useRef, useState } from "react";
import ChatComposer from "@/components/chat-composer";
import ChatEmptyState from "@/components/chat-empty-state";
import ChatMessage from "@/components/chat-message";
import type {
  ChatErrorResponse,
  ChatMessage as ChatMessageType,
  ChatSource,
  ChatSuccessResponse,
} from "@/types/chat";

const SUGGESTIONS = [
  "Huế có những hoạt động du lịch nào?",
  "Đà Nẵng nên đi đâu trong 2 ngày?",
  "Gợi ý lịch trình Hội An cho người mới đến",
];

const DEFAULT_ERROR = "Không thể nhận câu trả lời. Vui lòng thử lại.";

function isSource(value: unknown): value is ChatSource {
  return (
    typeof value === "object" &&
    value !== null &&
    typeof (value as ChatSource).title === "string" &&
    typeof (value as ChatSource).source === "string"
  );
}

function isSuccessResponse(value: unknown): value is ChatSuccessResponse {
  return (
    typeof value === "object" &&
    value !== null &&
    typeof (value as ChatSuccessResponse).answer === "string" &&
    Array.isArray((value as ChatSuccessResponse).sources) &&
    (value as ChatSuccessResponse).sources.every(isSource)
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

export default function ChatWindow() {
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
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: question }),
      });
      const payload: unknown = await response.json().catch(() => null);

      if (!response.ok) {
        throw new Error(getErrorMessage(payload));
      }

      if (!isSuccessResponse(payload)) {
        throw new Error(DEFAULT_ERROR);
      }

      const assistantMessage: ChatMessageType = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: payload.answer,
        sources: payload.sources,
      };

      setMessages((current) => [...current, assistantMessage]);
      setInput("");
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
          messages.map((message) => <ChatMessage key={message.id} message={message} />)
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
