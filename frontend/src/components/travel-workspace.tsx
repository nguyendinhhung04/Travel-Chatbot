"use client";

import { useRef, useState } from "react";
import ChatWindow from "@/components/chat-window";
import MapPanel from "@/components/map-panel";

const MIN_CHAT_WIDTH = 28;
const MAX_CHAT_WIDTH = 55;

export default function TravelWorkspace() {
  const [chatWidth, setChatWidth] = useState(38);
  const [isDragging, setIsDragging] = useState(false);
  const workspaceRef = useRef<HTMLDivElement>(null);

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
    <div
      ref={workspaceRef}
      className={`experience-shell ${isDragging ? "experience-shell-dragging" : ""}`}
      style={{ "--chat-width": `${chatWidth}%` } as React.CSSProperties}
    >
      <ChatWindow />
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
      <MapPanel />
    </div>
  );
}
