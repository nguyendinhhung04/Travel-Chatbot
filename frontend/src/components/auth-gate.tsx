"use client";

import { useEffect, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";

export type AuthUser = {
  id: string;
  email: string;
  displayName: string;
  createdAt: string;
};

export default function AuthGate({ children }: { children: (user: AuthUser) => ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    let active = true;
    fetch("/api/auth/me", { cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) {
          router.replace("/login?next=/chat");
          return;
        }
        const payload: unknown = await response.json();
        if (!active || typeof payload !== "object" || payload === null) return;
        const candidate = (payload as { user?: unknown }).user;
        if (typeof candidate === "object" && candidate !== null) {
          setUser(candidate as AuthUser);
        }
      })
      .catch(() => router.replace("/login?next=/chat"))
      .finally(() => {
        if (active) setChecking(false);
      });

    return () => {
      active = false;
    };
  }, [router]);

  if (checking || !user) {
    return <main className="auth-loading" aria-live="polite">Đang kiểm tra đăng nhập...</main>;
  }

  return children(user);
}
