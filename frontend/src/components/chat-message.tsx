import type { ChatMessage as ChatMessageType } from "@/types/chat";

type ChatMessageProps = {
  message: ChatMessageType;
};

export default function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === "user";

  return (
    <article className={`message-row ${isUser ? "message-row-user" : "message-row-assistant"}`}>
      <div className={`message-bubble ${isUser ? "message-bubble-user" : "message-bubble-assistant"}`}>
        <span className="message-author">{isUser ? "Bạn" : "Trợ lý"}</span>
        <p className="message-content">{message.content}</p>
        {!isUser && message.sources && message.sources.length > 0 ? (
          <div className="sources" aria-label="Nguồn tham khảo">
            <span className="sources-heading">Nguồn tham khảo</span>
            <ul>
              {message.sources.map((source) => (
                <li key={`${source.title}-${source.source}`}>
                  <span className="source-title">{source.title}</span>
                  <span className="source-path">{source.source}</span>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
    </article>
  );
}
