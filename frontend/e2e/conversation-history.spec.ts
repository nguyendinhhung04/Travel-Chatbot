import { expect, test } from "@playwright/test";

const user = {
  id: "507f1f77bcf86cd799439014",
  email: "test@example.com",
  displayName: "Test User",
  createdAt: "2026-01-01T00:00:00Z",
};

const summary = {
  id: "507f1f77bcf86cd799439011",
  title: "Saved trip",
  lastMessagePreview: "Assistant response",
  lastTurnIndex: 1,
  createdAt: "2026-01-01T00:00:00Z",
  updatedAt: "2026-01-01T00:00:00Z",
};

const details = {
  conversation: summary,
  messages: [
    {
      id: "507f1f77bcf86cd799439013",
      conversationId: summary.id,
      userId: user.id,
      turnId: "11111111-1111-1111-1111-111111111111",
      turnIndex: 1,
      role: "assistant",
      content: "Assistant response",
      sources: [],
      places: [],
      itinerary: null,
      createdAt: "2026-01-01T00:00:00Z",
    },
    {
      id: "507f1f77bcf86cd799439012",
      conversationId: summary.id,
      userId: user.id,
      turnId: "11111111-1111-1111-1111-111111111111",
      turnIndex: 1,
      role: "user",
      content: "Where should I go?",
      createdAt: "2026-01-01T00:00:00Z",
    },
  ],
};

const historySummary = {
  ...summary,
  lastMessagePreview: "Answer 5",
  lastTurnIndex: 5,
};

const historyDetails = {
  conversation: historySummary,
  messages: Array.from({ length: 5 }, (_, index) => {
    const turnIndex = index + 1;
    const turnId = `${String(turnIndex).repeat(8)}-${String(turnIndex).repeat(4)}-${String(turnIndex).repeat(4)}-${String(turnIndex).repeat(4)}-${String(turnIndex).repeat(12)}`;
    return [
      {
        id: `507f1f77bcf86cd7994391${String(turnIndex).padStart(2, "0")}`,
        conversationId: summary.id,
        userId: user.id,
        turnId,
        turnIndex,
        role: "user",
        content: `Question ${turnIndex}`,
        createdAt: `2026-01-01T00:0${turnIndex}:00Z`,
      },
      {
        id: `507f1f77bcf86cd7994392${String(turnIndex).padStart(2, "0")}`,
        conversationId: summary.id,
        userId: user.id,
        turnId,
        turnIndex,
        role: "assistant",
        content: `Answer ${turnIndex}`,
        sources: [],
        places: [],
        itinerary: null,
        createdAt: `2026-01-01T00:0${turnIndex}:01Z`,
      },
    ];
  }).flat(),
};

test.beforeEach(async ({ page }) => {
  await page.route("**/api/auth/me", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ user }) }),
  );
  await page.route("**/api/itineraries", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: "null" }),
  );
});

test("opens a saved conversation and restores its messages", async ({ page }) => {
  await page.route("**/api/conversations", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([summary]) }),
  );
  await page.route(`**/api/conversations/${summary.id}`, (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(details) }),
  );

  await page.goto("/chat");
  await expect(page.getByText("Saved trip")).toBeVisible();
  await page.locator(".conversation-open").filter({ hasText: "Saved trip" }).click();

  const restoredRows = page.locator(".message-row");
  await expect(restoredRows).toHaveCount(2);
  await expect(restoredRows.nth(0)).toContainText("Where should I go?");
  await expect(restoredRows.nth(1)).toContainText("Assistant response");
  await expect(page.locator(".message-row-user .message-content").getByText("Where should I go?")).toBeVisible();
  await expect(page.locator(".message-row-assistant .message-content").getByText("Assistant response")).toBeVisible();
});

test("saves a successful first answer through the conversation API", async ({ page }) => {
  await page.route("**/api/conversations", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
      return;
    }
    const request = route.request().postDataJSON() as Record<string, unknown>;
    expect(request).toMatchObject({
      userMessage: { content: "Start a trip" },
      assistantMessage: { content: "Saved answer", sources: [], places: [], itinerary: null },
    });
    await route.fulfill({
      status: 201,
      contentType: "application/json",
      body: JSON.stringify({
        ...details,
        conversation: { ...summary, title: "Start a trip", lastMessagePreview: "Saved answer" },
        messages: [],
      }),
    });
  });
  await page.route("**/api/chat", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ answer: "Saved answer", sources: [], places: [] }) }),
  );

  await page.goto("/chat");
  await page.getByLabel("Câu hỏi du lịch").fill("Start a trip");
  await page.getByRole("button", { name: "Gửi câu hỏi" }).click();

  await expect(page.locator(".message-row-assistant .message-content").getByText("Saved answer")).toBeVisible();
  await expect(page.locator(".message-row-user .message-content").getByText("Start a trip")).toBeVisible();
});

test("keeps the full UI history but sends only the latest three complete turns to chat", async ({ page }) => {
  let chatRequest: Record<string, unknown> | undefined;

  await page.route("**/api/conversations", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([historySummary]) }),
  );
  await page.route(`**/api/conversations/${summary.id}`, (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(historyDetails) }),
  );
  await page.route(`**/api/conversations/${summary.id}/turns`, async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(historyDetails) });
  });
  await page.route("**/api/chat", async (route) => {
    chatRequest = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ answer: "Answer 6", sources: [], places: [] }),
    });
  });

  await page.goto("/chat");
  await page.locator(".conversation-open").filter({ hasText: historySummary.title }).click();
  await expect(page.locator(".message-row-user .message-content").getByText("Question 1")).toBeVisible();
  await expect(page.locator(".message-row-assistant .message-content").getByText("Answer 5")).toBeVisible();

  await page.getByLabel("Câu hỏi du lịch").fill("Question 6");
  await page.getByRole("button", { name: "Gửi câu hỏi" }).click();

  await expect(page.getByText("Answer 6")).toBeVisible();
  expect(chatRequest).toMatchObject({ message: "Question 6" });
  expect(chatRequest?.history).toEqual([
    { role: "user", content: "Question 3" },
    { role: "assistant", content: "Answer 3" },
    { role: "user", content: "Question 4" },
    { role: "assistant", content: "Answer 4" },
    { role: "user", content: "Question 5" },
    { role: "assistant", content: "Answer 5" },
  ]);
});

test("deletes the selected conversation", async ({ page }) => {
  await page.route("**/api/conversations", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([summary]) }),
  );
  await page.route(`**/api/conversations/${summary.id}`, (route) => {
    if (route.request().method() === "DELETE") {
      return route.fulfill({ status: 204, body: "" });
    }
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(details) });
  });

  await page.goto("/chat");
  await page.getByRole("button", { name: `Xóa ${summary.title}` }).click();

  await expect(page.getByText("Saved trip")).not.toBeVisible();
});
