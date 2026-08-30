import { expect, test } from "@playwright/test";

const itinerary = {
  id: "507f1f77bcf86cd799439011",
  version: 1,
  title: "Hà Nội 3 ngày 2 đêm",
  destination: "Hà Nội",
  durationDays: 3,
  durationNights: 2,
  profile: "driving",
  stops: [
    {
      mapboxId: "poi-2",
      name: "Điểm B",
      longitude: 105.9,
      latitude: 21.1,
      order: 1,
      inputIndex: 1,
    },
    {
      mapboxId: "poi-1",
      name: "Điểm A",
      longitude: 105.8,
      latitude: 21.0,
      order: 2,
      inputIndex: 0,
    },
  ],
  route: {
    type: "LineString",
    coordinates: [[105.9, 21.1], [105.8, 21.0]],
  },
  distanceMeters: 2500,
  durationSeconds: 900,
};

const duplicateMapboxSources = [
  {
    type: "mapbox",
    title: "Mapbox",
    source: "Mapbox Search API",
    attribution: "Mapbox",
  },
  {
    type: "mapbox",
    title: "Mapbox",
    source: "Mapbox Search API",
    attribution: "Mapbox",
  },
];

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => window.localStorage.clear());
});

test("accepts an optimized itinerary and keeps it on a normal answer", async ({
  page,
}) => {
  let requestCount = 0;
  await page.route("**/api/itineraries", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: "null" }),
  );
  await page.route("**/api/chat", async (route) => {
    requestCount += 1;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(
        requestCount === 1
          ? {
              answer: "Điểm B rồi Điểm A.",
              sources: duplicateMapboxSources,
              places: [],
              itinerary,
            }
          : {
              answer: "Đây là câu trả lời thông thường.",
              sources: [],
              places: [],
            },
      ),
    });
  });

  await page.goto("/");
  await page.waitForFunction(
    () => window.localStorage.getItem("travel_chat_messages") !== null,
  );

  const input = page.getByLabel("Câu hỏi du lịch");
  const sendButton = page.getByRole("button", { name: "Gửi câu hỏi" });
  await input.fill("Lên lịch trình Hà Nội 3 ngày 2 đêm");
  await sendButton.click();

  await expect(page.getByText("Điểm B rồi Điểm A.")).toBeVisible();
  await expect(page.getByLabel("Lộ trình đã chọn")).toContainText(
    "Hà Nội 3 ngày 2 đêm · 2 điểm dừng",
  );
  await expect(page.locator(".sources li")).toHaveCount(1);

  await input.fill("Hà Nội có gì?");
  await sendButton.click();
  await expect(page.getByText("Đây là câu trả lời thông thường.")).toBeVisible();
  await expect(page.getByLabel("Lộ trình đã chọn")).toContainText(
    "Hà Nội 3 ngày 2 đêm · 2 điểm dừng",
  );
  expect(requestCount).toBe(2);
});

test("loads an active itinerary and sends its id and version for add stop", async ({
  page,
}) => {
  const persisted = {
    ...itinerary,
    id: "507f1f77bcf86cd799439011",
    version: 3,
    userId: "admin",
    provider: "mapbox",
    generatedAt: "2026-08-28T10:00:00Z",
    createdAt: "2026-08-28T09:00:00Z",
    updatedAt: "2026-08-28T10:00:00Z",
  };
  await page.route("**/api/itineraries", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(persisted),
    }),
  );

  let chatRequest: Record<string, unknown> | null = null;
  await page.route("**/api/chat", async (route) => {
    chatRequest = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        answer: "Đã thêm Công viên Yên Sở vào lịch trình.",
        sources: [],
        places: [],
        itinerary: {
          ...persisted,
          version: 4,
          stops: [
            ...persisted.stops,
            {
              mapboxId: "poi-yen-so",
              name: "Công viên Yên Sở",
              longitude: 105.88,
              latitude: 20.96,
              order: 3,
              inputIndex: 2,
            },
          ],
        },
      }),
    });
  });

  await page.goto("/");
  await expect(page.getByLabel("Lộ trình đã chọn")).toContainText("2 điểm dừng");
  await page.getByLabel("Câu hỏi du lịch").fill(
    "Thêm Công viên Yên Sở vào lịch trình",
  );
  await page.getByRole("button", { name: "Gửi câu hỏi" }).click();

  await expect(page.getByText("Đã thêm Công viên Yên Sở vào lịch trình.")).toBeVisible();
  await expect(page.getByLabel("Lộ trình đã chọn")).toContainText("3 điểm dừng");
  expect(chatRequest).toMatchObject({
    active_itinerary_id: persisted.id,
    active_itinerary_version: 3,
  });
});

test("activates a newly created itinerary before adding another stop", async ({
  page,
}) => {
  await page.route("**/api/itineraries", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: "null" }),
  );

  const created = {
    ...itinerary,
    userId: "admin",
    provider: "mapbox",
    generatedAt: "2026-08-28T10:00:00Z",
    createdAt: "2026-08-28T10:00:00Z",
    updatedAt: "2026-08-28T10:00:00Z",
  };
  let requestCount = 0;
  let addRequest: Record<string, unknown> | null = null;
  await page.route("**/api/chat", async (route) => {
    requestCount += 1;
    if (requestCount === 2) {
      addRequest = route.request().postDataJSON() as Record<string, unknown>;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(
        requestCount === 1
          ? {
              answer: "Đã tạo và lưu lịch trình.",
              sources: [],
              places: [],
              itinerary: created,
            }
          : {
              answer: "Đã thêm MaiLy Coffee vào lịch trình.",
              sources: [],
              places: [],
              itinerary: {
                ...created,
                version: 2,
                stops: [
                  ...created.stops,
                  {
                    mapboxId: "poi-cafe",
                    name: "MaiLy Coffee",
                    longitude: 106.7,
                    latitude: 10.77,
                    order: 3,
                    inputIndex: 2,
                  },
                ],
              },
            },
      ),
    });
  });

  await page.goto("/");
  const input = page.getByLabel("Câu hỏi du lịch");
  const sendButton = page.getByRole("button", { name: "Gửi câu hỏi" });
  await input.fill("Lên lịch trình Hà Nội 3 ngày 2 đêm");
  await sendButton.click();
  await expect(page.getByText("Đã tạo và lưu lịch trình.")).toBeVisible();

  await input.fill("Thêm MaiLy Coffee vào lịch trình");
  await sendButton.click();
  await expect(page.getByText("Đã thêm MaiLy Coffee vào lịch trình.")).toBeVisible();
  await expect(page.getByLabel("Lộ trình đã chọn")).toContainText("3 điểm dừng");
  expect(addRequest).toMatchObject({
    active_itinerary_id: created.id,
    active_itinerary_version: 1,
  });
});
