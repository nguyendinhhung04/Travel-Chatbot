import { NextResponse } from "next/server";
import {
  backendAuthUrl,
  getAuthorizationHeader,
  unauthorizedResponse,
} from "@/lib/auth-proxy";

const CONNECTION_ERROR = "Không thể tải cuộc trò chuyện hiện tại.";

async function forward(request: Request, method: "GET" | "POST") {
  const authorization = await getAuthorizationHeader();
  if (!authorization) return unauthorizedResponse();
  const url = backendAuthUrl("/api/conversations");
  if (!url) return NextResponse.json({ error: "Backend chưa được cấu hình." }, { status: 502 });

  try {
    const upstream = await fetch(url, {
      method,
      headers: {
        Accept: "application/json",
        Authorization: authorization,
        ...(method === "POST" ? { "Content-Type": "application/json" } : {}),
      },
      ...(method === "POST" ? { body: await request.text() } : {}),
      cache: "no-store",
    });
    const payload = await upstream.json().catch(() => null);
    return NextResponse.json(payload, { status: upstream.status });
  } catch {
    return NextResponse.json({ error: CONNECTION_ERROR }, { status: 502 });
  }
}

export async function GET(request: Request) {
  return forward(request, "GET");
}

export async function POST(request: Request) {
  return forward(request, "POST");
}
