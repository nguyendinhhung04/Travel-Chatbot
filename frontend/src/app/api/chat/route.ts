import type { ChatErrorResponse } from "@/types/chat";
import { getAuthorizationHeader, unauthorizedResponse } from "@/lib/auth-proxy";
import { getRecentCompleteTurns } from "@/utils/llm-history";

const INVALID_MESSAGE = "Vui lòng nhập một câu hỏi du lịch.";
const CONNECTION_ERROR = "Không thể kết nối đến máy chủ chatbot.";

type HistoryMessage = {
  role: "user" | "assistant";
  content: string;
};

function errorResponse(error: string, status: number) {
  const payload: ChatErrorResponse = { error };
  return Response.json(payload, { status });
}

function isCoordinate(value: unknown, minimum: number, maximum: number): value is number {
  return typeof value === "number" && Number.isFinite(value) && value >= minimum && value <= maximum;
}

function isHistoryMessage(value: unknown): value is HistoryMessage {
  if (typeof value !== "object" || value === null) return false;

  const historyMessage = value as Partial<HistoryMessage>;
  return (
    Object.keys(historyMessage).every((key) => key === "role" || key === "content") &&
    (historyMessage.role === "user" || historyMessage.role === "assistant") &&
    typeof historyMessage.content === "string" &&
    historyMessage.content.trim().length > 0
  );
}

export async function POST(request: Request) {
  const authorization = await getAuthorizationHeader();
  if (!authorization) return unauthorizedResponse();

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

  const historyValue =
    typeof body === "object" && body !== null && "history" in body
      ? (body as { history?: unknown }).history
      : undefined;
  if (
    historyValue !== undefined &&
    (!Array.isArray(historyValue) ||
      historyValue.length > 6 ||
      !historyValue.every(isHistoryMessage))
  ) {
    return errorResponse("Invalid chat history.", 400);
  }
  const history = getRecentCompleteTurns((historyValue ?? []) as HistoryMessage[]);

  const activeItineraryId =
    typeof body === "object" && body !== null && "active_itinerary_id" in body
      ? (body as { active_itinerary_id?: unknown }).active_itinerary_id
      : undefined;
  if (
    activeItineraryId !== undefined &&
    (typeof activeItineraryId !== "string" || !/^[a-f\d]{24}$/i.test(activeItineraryId))
  ) {
    return errorResponse("Mã lịch trình không hợp lệ.", 400);
  }

  const activeItineraryVersion =
    typeof body === "object" && body !== null && "active_itinerary_version" in body
      ? (body as { active_itinerary_version?: unknown }).active_itinerary_version
      : undefined;
  if (
    activeItineraryVersion !== undefined &&
    (typeof activeItineraryVersion !== "number" ||
      !Number.isInteger(activeItineraryVersion) ||
      activeItineraryVersion < 1)
  ) {
    return errorResponse("Phiên bản lịch trình không hợp lệ.", 400);
  }
  if ((activeItineraryId === undefined) !== (activeItineraryVersion === undefined)) {
    return errorResponse("Mã và phiên bản lịch trình phải được gửi cùng nhau.", 400);
  }

  const currentLocation =
    typeof body === "object" && body !== null && "current_location" in body
      ? (body as { current_location?: unknown }).current_location
      : undefined;
  let normalizedCurrentLocation:
    | { longitude: number; latitude: number }
    | undefined;
  if (currentLocation !== undefined) {
    if (
      typeof currentLocation !== "object" ||
      currentLocation === null ||
      !isCoordinate(
        (currentLocation as { longitude?: unknown }).longitude,
        -180,
        180,
      ) ||
      !isCoordinate(
        (currentLocation as { latitude?: unknown }).latitude,
        -90,
        90,
      )
    ) {
      return errorResponse("Vị trí hiện tại không hợp lệ.", 400);
    }
    normalizedCurrentLocation = {
      longitude: (currentLocation as { longitude: number }).longitude,
      latitude: (currentLocation as { latitude: number }).latitude,
    };
  }

  const backendUrl = process.env.BACKEND_URL;
  if (!backendUrl) {
    return errorResponse(CONNECTION_ERROR, 502);
  }

  try {
    const upstream = await fetch(`${backendUrl.replace(/\/$/, "")}/api/chat/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: authorization,
      },
      body: JSON.stringify({
        message: message.trim(),
        history,
        ...(activeItineraryId === undefined
          ? {}
          : { active_itinerary_id: activeItineraryId }),
        ...(activeItineraryVersion === undefined
          ? {}
          : { active_itinerary_version: activeItineraryVersion }),
        ...(normalizedCurrentLocation === undefined
          ? {}
          : { current_location: normalizedCurrentLocation }),
      }),
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
