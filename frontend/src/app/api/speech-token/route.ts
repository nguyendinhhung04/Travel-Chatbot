const CONNECTION_ERROR = "Không thể khởi tạo nhận dạng giọng nói.";

export const dynamic = "force-dynamic";

export async function POST() {
  const backendUrl = process.env.DOTNET_BACKEND_URL;
  if (!backendUrl) {
    return Response.json(
      { error: CONNECTION_ERROR },
      { status: 503, headers: { "Cache-Control": "no-store" } },
    );
  }

  try {
    const upstream = await fetch(
      `${backendUrl.replace(/\/$/, "")}/api/speech/ephemeral-token`,
      {
        method: "POST",
        headers: { Accept: "application/json" },
        cache: "no-store",
      },
    );
    const payload: unknown = await upstream.json().catch(() => null);
    return Response.json(payload, {
      status: upstream.status,
      headers: { "Cache-Control": "no-store" },
    });
  } catch {
    return Response.json(
      { error: CONNECTION_ERROR },
      { status: 502, headers: { "Cache-Control": "no-store" } },
    );
  }
}
