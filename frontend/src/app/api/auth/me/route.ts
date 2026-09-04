import { NextResponse } from "next/server";
import {
  backendAuthUrl,
  getAuthorizationHeader,
  unauthorizedResponse,
} from "@/lib/auth-proxy";

export async function GET() {
  const authorization = await getAuthorizationHeader();
  if (!authorization) return unauthorizedResponse();
  const url = backendAuthUrl("/api/auth/me");
  if (!url) return NextResponse.json({ error: "Backend chưa được cấu hình." }, { status: 502 });

  try {
    const upstream = await fetch(url, {
      headers: { Accept: "application/json", Authorization: authorization },
      cache: "no-store",
    });
    const payload = await upstream.json().catch(() => null);
    return upstream.ok
      ? NextResponse.json({ user: payload }, { status: upstream.status })
      : NextResponse.json(payload, { status: upstream.status });
  } catch {
    return NextResponse.json({ error: "Không thể kết nối đến backend." }, { status: 502 });
  }
}
