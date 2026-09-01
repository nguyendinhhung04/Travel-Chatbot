import { NextResponse } from "next/server";

const CONNECTION_ERROR = "Không thể tải lịch trình hiện tại.";

export async function GET() {
  const backendUrl = process.env.BACKEND_URL;
  if (!backendUrl) {
    return NextResponse.json({ error: CONNECTION_ERROR }, { status: 502 });
  }

  try {
    const upstream = await fetch(
      `${backendUrl.replace(/\/$/, "")}/api/users/admin/itineraries/latest`,
      { headers: { Accept: "application/json" }, cache: "no-store" },
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
