"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import AuthGate, { type AuthUser } from "@/components/auth-gate";
import TravelWorkspace from "@/components/travel-workspace";

function ChatPageContent({ user }: { user: AuthUser }) {
  const router = useRouter();
  const [loggingOut, setLoggingOut] = useState(false);

  async function logout() {
    setLoggingOut(true);
    await fetch("/api/auth/logout", { method: "POST" }).catch(() => undefined);
    router.replace("/login");
  }

  return (
    <main className="page-background">
      <div className="ambient-shape ambient-shape-one" aria-hidden="true" />
      <div className="ambient-shape ambient-shape-two" aria-hidden="true" />
      <div className="chat-page-content">
        <div className="auth-toolbar">
          <span>Xin chào, {user.displayName}</span>
          <button type="button" onClick={() => void logout()} disabled={loggingOut}>
            {loggingOut ? "Đang đăng xuất..." : "Đăng xuất"}
          </button>
        </div>
        <TravelWorkspace />
      </div>
    </main>
  );
}

export default function ChatPage() {
  return (
    <AuthGate>
      {(user) => <ChatPageContent user={user} />}
    </AuthGate>
  );
}
