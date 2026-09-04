import { expect, test, type Page } from "@playwright/test";

const QUESTION = "Quán cafe nào gần tôi?";
const CURRENT_LOCATION = {
  longitude: 106.6822,
  latitude: 10.7626,
};

test.beforeEach(async ({ page }) => {
  await page.route("**/api/auth/me", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ user: { id: "507f1f77bcf86cd799439014", email: "test@example.com", displayName: "Test User", createdAt: "2026-01-01T00:00:00Z" } }),
    }),
  );
  await page.route("**/api/itineraries", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: "null" }),
  );
});

async function openHydratedApp(page: Page) {
  await page.goto("/");
  await expect(page.getByLabel("Câu hỏi du lịch")).toBeVisible();
}

test("renders the travel assistant", async ({ page }) => {
  await openHydratedApp(page);

  await expect(
    page.getByRole("heading", { name: "Trợ lý du lịch" }),
  ).toBeVisible();
  await expect(page.getByLabel("Câu hỏi du lịch")).toBeEditable();
  await expect(page.getByRole("button", { name: "Gửi câu hỏi" })).toBeDisabled();
});

test("gets GPS on demand and retries the same request once", async ({
  context,
  page,
}) => {
  await context.grantPermissions(["geolocation"], {
    origin: "http://localhost:3100",
  });
  await context.setGeolocation(CURRENT_LOCATION);

  const requestBodies: Array<Record<string, unknown>> = [];
  await page.route("**/api/chat", async (route) => {
    const body = route.request().postDataJSON() as Record<string, unknown>;
    requestBodies.push(body);

    if (requestBodies.length === 1) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          type: "client_tool_call",
          toolCall: {
            name: "get_current_location",
            arguments: {},
          },
        }),
      });
      return;
    }

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        answer: "Đã tìm thấy địa điểm gần bạn.",
        sources: [],
        places: [],
      }),
    });
  });

  await openHydratedApp(page);
  await page.getByLabel("Câu hỏi du lịch").fill(QUESTION);
  const sendButton = page.getByRole("button", { name: "Gửi câu hỏi" });
  await expect(sendButton).toBeEnabled();
  await sendButton.click();

  await expect(page.getByText("Đã tìm thấy địa điểm gần bạn.")).toBeVisible();
  expect(requestBodies).toHaveLength(2);
  expect(requestBodies[0]).toMatchObject({ message: QUESTION, history: [] });
  expect(requestBodies[0]).not.toHaveProperty("current_location");
  expect(requestBodies[1]).toMatchObject({
    message: QUESTION,
    history: [],
    current_location: CURRENT_LOCATION,
  });

});

test("does not retry when browser geolocation is denied", async ({ page }) => {
  await page.addInitScript(() => {
    const permissionDeniedError = {
      code: 1,
      message: "Permission denied",
      PERMISSION_DENIED: 1,
      POSITION_UNAVAILABLE: 2,
      TIMEOUT: 3,
    } as GeolocationPositionError;
    Object.defineProperty(navigator, "geolocation", {
      configurable: true,
      value: {
        getCurrentPosition: (
          _success: PositionCallback,
          error?: PositionErrorCallback | null,
        ) => error?.(permissionDeniedError),
      },
    });
  });

  let requestCount = 0;
  await page.route("**/api/chat", async (route) => {
    requestCount += 1;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        type: "client_tool_call",
        toolCall: {
          name: "get_current_location",
          arguments: {},
        },
      }),
    });
  });

  await openHydratedApp(page);
  await page.getByLabel("Câu hỏi du lịch").fill(QUESTION);
  await page.getByRole("button", { name: "Gửi câu hỏi" }).click();

  await expect(
    page.getByRole("alert").filter({ hasText: "Không thể lấy vị trí hiện tại" }),
  ).toBeVisible();
  expect(requestCount).toBe(1);
});

test("new conversation clears the workspace-owned messages", async ({ page }) => {
  await page.route("**/api/chat", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ answer: "A fresh answer", sources: [], places: [] }),
    }),
  );

  await openHydratedApp(page);
  await page.getByLabel("Câu hỏi du lịch").fill("Một câu hỏi");
  await page.getByRole("button", { name: "Gửi câu hỏi" }).click();
  await expect(page.getByText("A fresh answer")).toBeVisible();

  await page.locator(".new-chat-button").click();

  await expect(page.getByText("A fresh answer")).not.toBeVisible();
  await expect(page.locator(".empty-state h2")).toBeVisible();
});

test("stops after one GPS retry when the server requests location again", async ({
  context,
  page,
}) => {
  await context.grantPermissions(["geolocation"], {
    origin: "http://localhost:3100",
  });
  await context.setGeolocation(CURRENT_LOCATION);

  let requestCount = 0;
  await page.route("**/api/chat", async (route) => {
    requestCount += 1;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        type: "client_tool_call",
        toolCall: {
          name: "get_current_location",
          arguments: {},
        },
      }),
    });
  });

  await openHydratedApp(page);
  await page.getByLabel("Câu hỏi du lịch").fill(QUESTION);
  const sendButton = page.getByRole("button", { name: "Gửi câu hỏi" });
  await expect(sendButton).toBeEnabled();
  await sendButton.click();

  await expect(
    page.getByRole("alert").filter({ hasText: "Không thể lấy vị trí hiện tại" }),
  ).toBeVisible();
  expect(requestCount).toBe(2);
});
