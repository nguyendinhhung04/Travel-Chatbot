import { NextResponse } from "next/server";
import { backendAuthUrl } from "@/lib/auth-proxy";

export async function POST(request: Request) {
  const url = backendAuthUrl("/api/auth/register");
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
    return NextResponse.json(payload, { status: upstream.status });
  } catch {
    return NextResponse.json({ error: "Không thể kết nối đến backend." }, { status: 502 });
  }
}
