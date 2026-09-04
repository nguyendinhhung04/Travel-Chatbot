"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

type AuthMode = "login" | "register";

function errorMessage(payload: unknown) {
  if (typeof payload !== "object" || payload === null) return "Yêu cầu không thành công.";
  const value = payload as { error?: unknown };
  return typeof value.error === "string" ? value.error : "Yêu cầu không thành công.";
}

export default function AuthForm({ mode }: { mode: AuthMode }) {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const isRegister = mode === "register";

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setPending(true);
    try {
      const response = await fetch(`/api/auth/${mode}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password, ...(isRegister ? { displayName } : {}) }),
      });
      const payload: unknown = await response.json().catch(() => null);
      if (!response.ok) throw new Error(errorMessage(payload));
      router.replace(isRegister ? "/login?registered=1" : "/chat");
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Yêu cầu không thành công.");
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-card" aria-labelledby="auth-title">
        <p className="eyebrow">TRAVEL RAG</p>
        <h1 id="auth-title">{isRegister ? "Tạo tài khoản" : "Đăng nhập"}</h1>
        <p className="auth-description">
          {isRegister ? "Lưu lại các cuộc trò chuyện và lịch trình du lịch của bạn." : "Đăng nhập để tiếp tục cuộc trò chuyện của bạn."}
        </p>
        <form className="auth-form" onSubmit={submit}>
          {isRegister ? (
            <label>Tên hiển thị<input value={displayName} onChange={(event) => setDisplayName(event.target.value)} required maxLength={100} /></label>
          ) : null}
          <label>Email<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required autoComplete="email" /></label>
          <label>Mật khẩu<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} required minLength={8} autoComplete={isRegister ? "new-password" : "current-password"} /></label>
          {error ? <p className="auth-error" role="alert">{error}</p> : null}
          <button className="auth-submit" type="submit" disabled={pending}>{pending ? "Đang xử lý..." : isRegister ? "Đăng ký" : "Đăng nhập"}</button>
        </form>
        <p className="auth-switch">
          {isRegister ? "Đã có tài khoản? " : "Chưa có tài khoản? "}
          <Link href={isRegister ? "/login" : "/register"}>{isRegister ? "Đăng nhập" : "Đăng ký"}</Link>
        </p>
      </section>
    </main>
  );
}
