import { expect, test } from "@playwright/test";

const user = {
  id: "507f1f77bcf86cd799439014",
  email: "test@example.com",
  displayName: "Test User",
  createdAt: "2026-01-01T00:00:00Z",
};

test("redirects an unauthenticated user from chat to login", async ({ page }) => {
  await page.route("**/api/auth/me", (route) =>
    route.fulfill({ status: 401, contentType: "application/json", body: JSON.stringify({ error: "unauthorized" }) }),
  );

  await page.goto("/chat");

  await expect(page).toHaveURL(/\/login\?next=%2Fchat|\/login\?next=\/chat/);
  await expect(page.getByRole("heading", { name: "Đăng nhập" })).toBeVisible();
});

test("login stores an HttpOnly auth cookie and opens chat", async ({ page, context }) => {
  await page.route("**/api/auth/login", (route) =>
    context.addCookies([{
      name: "travel_auth_token",
      value: "test-token",
      url: "http://localhost:3100",
      httpOnly: true,
      sameSite: "Lax",
    }]).then(() => route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ accessToken: "test-token", user }),
    })),
  );
  await page.route("**/api/auth/me", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ user }) }),
  );
  await page.route("**/api/itineraries", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: "null" }),
  );

  await page.goto("/login");
  await page.getByLabel("Email").fill(user.email);
  await page.getByLabel("Mật khẩu").fill("password123");
  await page.getByRole("button", { name: "Đăng nhập" }).click();

  await expect(page).toHaveURL(/\/chat$/);
  const cookies = await context.cookies();
  const authCookie = cookies.find((cookie) => cookie.name === "travel_auth_token");
  expect(authCookie?.httpOnly).toBe(true);
});

test("logout returns the user to login", async ({ page }) => {
  await page.route("**/api/auth/me", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ user }) }),
  );
  await page.route("**/api/itineraries", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: "null" }),
  );
  await page.route("**/api/auth/logout", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true }) }),
  );

  await page.goto("/chat");
  await page.getByRole("button", { name: "Đăng xuất" }).click();

  await expect(page).toHaveURL(/\/login$/);
});
