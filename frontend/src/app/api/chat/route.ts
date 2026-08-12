import type { ChatErrorResponse } from "@/types/chat";

const INVALID_MESSAGE = "Vui lòng nhập một câu hỏi du lịch.";
const CONNECTION_ERROR = "Không thể kết nối đến máy chủ chatbot.";

function errorResponse(error: string, status: number) {
  const payload: ChatErrorResponse = { error };
  return Response.json(payload, { status });
}

export async function POST(request: Request) {
  let body: unknown;

  try {
    body = await request.json();
  } catch {
    return errorResponse(INVALID_MESSAGE, 400);
  }

  const message =
    typeof body === "object" && body !== null && "message" in body
      ? (body as { message?: unknown }).message
      : undefined;

  if (typeof message !== "string" || message.trim().length === 0) {
    return errorResponse(INVALID_MESSAGE, 400);
  }

  const backendUrl = process.env.BACKEND_URL;
  if (!backendUrl) {
    return errorResponse(CONNECTION_ERROR, 502);
  }

  try {
    const upstream = await fetch(`${backendUrl.replace(/\/$/, "")}/api/chat/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: message.trim() }),
      cache: "no-store",
    });

    let payload: unknown;
    try {
      payload = await upstream.json();
    } catch {
      return errorResponse(CONNECTION_ERROR, 502);
    }

    return Response.json(payload, { status: upstream.status });
  } catch {
    return errorResponse(CONNECTION_ERROR, 502);
  }
}
