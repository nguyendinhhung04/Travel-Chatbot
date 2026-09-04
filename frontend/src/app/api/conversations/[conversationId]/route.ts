import { NextResponse } from "next/server";
import {
  backendAuthUrl,
  getAuthorizationHeader,
  unauthorizedResponse,
} from "@/lib/auth-proxy";

const CONNECTION_ERROR = "Không thể tải cuộc trò chuyện hiện tại.";

type RouteContext = { params: Promise<{ conversationId: string }> };

async function forward(
  request: Request,
  conversationId: string,
  method: "GET" | "DELETE" | "POST",
) {
  const authorization = await getAuthorizationHeader();
  if (!authorization) return unauthorizedResponse();
  const url = backendAuthUrl(`/api/conversations/${encodeURIComponent(conversationId)}${method === "POST" ? "/turns" : ""}`);
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
    if (upstream.status === 204) return new NextResponse(null, { status: 204 });
    const payload = await upstream.json().catch(() => null);
    return NextResponse.json(payload, { status: upstream.status });
  } catch {
    return NextResponse.json({ error: CONNECTION_ERROR }, { status: 502 });
  }
}

export async function GET(request: Request, context: RouteContext) {
  return forward(request, (await context.params).conversationId, "GET");
}

export async function DELETE(request: Request, context: RouteContext) {
  return forward(request, (await context.params).conversationId, "DELETE");
}

export async function POST(request: Request, context: RouteContext) {
  return forward(request, (await context.params).conversationId, "POST");
}
