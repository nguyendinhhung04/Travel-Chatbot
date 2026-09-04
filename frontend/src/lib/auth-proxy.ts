import { cookies } from "next/headers";
import { NextResponse } from "next/server";

export const AUTH_COOKIE_NAME = "travel_auth_token";
export const AUTH_COOKIE_MAX_AGE = 60 * 60;

export async function getAuthorizationHeader(): Promise<string | null> {
  const token = (await cookies()).get(AUTH_COOKIE_NAME)?.value;
  return token ? `Bearer ${token}` : null;
}

export function unauthorizedResponse() {
  return NextResponse.json(
    { error: "Bạn cần đăng nhập để sử dụng tính năng này." },
    { status: 401 },
  );
}

export function setAuthCookie(response: NextResponse, token: string) {
  response.cookies.set({
    name: AUTH_COOKIE_NAME,
    value: token,
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: AUTH_COOKIE_MAX_AGE,
  });
}

export function clearAuthCookie(response: NextResponse) {
  response.cookies.set({
    name: AUTH_COOKIE_NAME,
    value: "",
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 0,
  });
}

export function backendAuthUrl(path: string) {
  const backendUrl = process.env.DOTNET_BACKEND_URL;
  return backendUrl
    ? `${backendUrl.replace(/\/$/, "")}${path}`
    : null;
}
