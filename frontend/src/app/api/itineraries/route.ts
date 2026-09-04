import { NextResponse } from "next/server";
import { getAuthorizationHeader, unauthorizedResponse } from "@/lib/auth-proxy";

const CONNECTION_ERROR = "Không thể tải lịch trình hiện tại.";

export async function GET() {
  const authorization = await getAuthorizationHeader();
  if (!authorization) return unauthorizedResponse();

  const backendUrl = process.env.DOTNET_BACKEND_URL;
  if (!backendUrl) {
    return NextResponse.json({ error: CONNECTION_ERROR }, { status: 502 });
  }

  try {
    const upstream = await fetch(
      `${backendUrl.replace(/\/$/, "")}/api/itineraries/latest`,
      {
        headers: { Accept: "application/json", Authorization: authorization },
        cache: "no-store",
      },
    );
    if (upstream.status === 404) {
      return NextResponse.json(null, { status: 200 });
    }
    const payload: unknown = await upstream.json().catch(() => null);
    return NextResponse.json(payload, { status: upstream.status });
  } catch {
    return NextResponse.json({ error: CONNECTION_ERROR }, { status: 502 });
  }
}
