import { NextResponse } from "next/server";
import { backendAuthUrl, setAuthCookie } from "@/lib/auth-proxy";

export async function POST(request: Request) {
  const url = backendAuthUrl("/api/auth/login");
  if (!url) return NextResponse.json({ error: "Backend chưa được cấu hình." }, { status: 502 });

  const body = await request.json().catch(() => null);
  try {
    const upstream = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(body),
      cache: "no-store",
    });
    const payload = await upstream.json().catch(() => null);
    if (!upstream.ok) return NextResponse.json(payload, { status: upstream.status });

    const token =
      typeof payload === "object" && payload !== null &&
      typeof (payload as { accessToken?: unknown }).accessToken === "string"
        ? (payload as { accessToken: string }).accessToken
        : null;
    if (!token) return NextResponse.json({ error: "Backend không trả về access token." }, { status: 502 });

    const response = NextResponse.json(
      typeof payload === "object" && payload !== null
        ? { user: (payload as { user?: unknown }).user }
        : null,
      { status: upstream.status },
    );
    setAuthCookie(response, token);
    return response;
  } catch {
    return NextResponse.json({ error: "Không thể kết nối đến backend." }, { status: 502 });
  }
}
