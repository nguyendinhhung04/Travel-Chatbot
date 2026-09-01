import { expect, test, type Page } from "@playwright/test";

async function openHydratedApp(page: Page) {
  await page.goto("/");
  await page.waitForFunction(
    () => window.localStorage.getItem("travel_chat_messages") !== null,
  );
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.clear();

    class FakeNode {
      connect(target: unknown) {
        return target;
      }

      disconnect() {}
    }

    class FakeAudioWorkletNode extends FakeNode {
      static current: FakeAudioWorkletNode | null = null;
      port = {
        onmessage: null as ((event: MessageEvent) => void) | null,
        postMessage: (message: unknown) => {
          if (message !== "flush") return;
          this.port.onmessage?.({
            data: { type: "chunk", buffer: new ArrayBuffer(3200) },
          } as MessageEvent);
        },
      };

      constructor() {
        super();
        FakeAudioWorkletNode.current = this;
      }
    }

    class FakeAudioContext {
      audioWorklet = { addModule: async () => undefined };
      destination = {};

      createGain() {
        return Object.assign(new FakeNode(), { gain: { value: 1 } });
      }

      createMediaStreamSource() {
        return new FakeNode();
      }

      async resume() {
        window.setTimeout(() => {
          FakeAudioWorkletNode.current?.port.onmessage?.({
            data: { type: "chunk", buffer: new ArrayBuffer(3200) },
          } as MessageEvent);
        }, 20);
      }

      async suspend() {}
      async close() {}
    }

    class FakeWebSocket {
      static OPEN = 1;
      readyState = FakeWebSocket.OPEN;
      onopen: (() => void) | null = null;
      onmessage: ((event: MessageEvent) => void) | null = null;
      onerror: (() => void) | null = null;
      onclose: (() => void) | null = null;

      constructor(public url: string) {
        window.setTimeout(() => this.onopen?.(), 0);
      }

      send(raw: string) {
        const message = JSON.parse(raw) as {
          setup?: unknown;
          realtimeInput?: {
            activityStart?: unknown;
            activityEnd?: unknown;
          };
        };
        const messages = (window as unknown as { __speechMessages?: string[] });
        messages.__speechMessages ??= [];
        messages.__speechMessages.push(raw);

        if (message.setup) {
          const config = window as unknown as { __delaySpeechSetup?: boolean };
          window.setTimeout(() => this.onmessage?.({
            data: new Blob([JSON.stringify({ setupComplete: {} })], {
              type: "application/json",
            }),
          } as MessageEvent), config.__delaySpeechSetup ? 15_000 : 0);
        }
        if (message.realtimeInput?.activityStart) {
          window.setTimeout(() => this.onmessage?.({
            data: JSON.stringify({
              serverContent: {
                interimInputTranscription: { text: "dang nghe" },
              },
            }),
          } as MessageEvent), 10);
        }
        if (message.realtimeInput?.activityEnd) {
          window.setTimeout(() => this.onmessage?.({
            data: JSON.stringify({
              serverContent: {
                inputTranscription: { text: "Xin chao Da Lat" },
              },
            }),
          } as MessageEvent), 20);
        }
      }

      close() {
        this.readyState = 3;
        this.onclose?.();
      }
    }

    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: {
        getUserMedia: async () => ({
          getTracks: () => [{ stop() {} }],
        }),
      },
    });
    Object.assign(window, {
      AudioContext: FakeAudioContext,
      webkitAudioContext: FakeAudioContext,
      AudioWorkletNode: FakeAudioWorkletNode,
      WebSocket: FakeWebSocket,
      __speechMessages: [],
      __delaySpeechSetup: false,
    });
  });
});

test("can stop while Gemini setup is still pending", async ({ page }) => {
  await page.route("**/api/speech-token", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        token: "authTokens/test-token",
        model: "gemini-3.5-transcribe-live",
      }),
    });
  });

  await openHydratedApp(page);
  await page.evaluate(() => {
    (window as unknown as { __delaySpeechSetup: boolean }).__delaySpeechSetup = true;
  });
  const speechButton = page.locator(".speech-button");
  await speechButton.click();
  await expect(speechButton).toBeEnabled();
  await expect(speechButton).toHaveAttribute("aria-label", "Dừng ghi âm");
  await speechButton.click();
  await expect(speechButton).toHaveAttribute("aria-label", "Nói");
});

test("streams microphone transcript into the composer and only sends after editing", async ({
  page,
}) => {
  await page.route("**/api/speech-token", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        token: "authTokens/test-token",
        model: "gemini-3.5-transcribe-live",
        expiresAt: new Date(Date.now() + 600_000).toISOString(),
      }),
    });
  });

  let chatRequestCount = 0;
  let sentMessage = "";
  await page.route("**/api/chat", async (route) => {
    chatRequestCount += 1;
    sentMessage = (route.request().postDataJSON() as { message: string }).message;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ answer: "Đã nhận.", sources: [], places: [] }),
    });
  });

  await openHydratedApp(page);
  const composer = page.locator(".composer");
  const textarea = composer.locator("textarea");
  const speechButton = composer.locator(".speech-button");
  await textarea.fill("Tôi muốn đi");
  await speechButton.click();

  await expect(speechButton).toHaveAttribute("aria-label", "Dừng ghi âm");
  await expect(textarea).toHaveValue("Tôi muốn đi dang nghe");
  expect(chatRequestCount).toBe(0);

  await speechButton.click();
  await expect(speechButton).toHaveAttribute("aria-label", "Nói");
  await expect(textarea).toHaveValue("Tôi muốn đi Xin chao Da Lat");
  await textarea.fill("Tôi muốn đi Xin chao Da Lat vào cuối tuần");
  await expect(speechButton).toBeEnabled();

  await composer.getByRole("button", { name: "Gửi câu hỏi" }).click();
  await expect(page.getByText("Đã nhận.")).toBeVisible();
  expect(chatRequestCount).toBe(1);
  expect(sentMessage).toBe("Tôi muốn đi Xin chao Da Lat vào cuối tuần");

  const speechMessages = await page.evaluate(
    () => (window as unknown as { __speechMessages: string[] }).__speechMessages,
  );
  const parsedMessages = speechMessages.map((message) => JSON.parse(message) as {
    setup?: unknown;
    realtimeInput?: {
      activityStart?: unknown;
      activityEnd?: unknown;
      audio?: { data?: string; mimeType?: string };
    };
  });
  expect(parsedMessages.some((message) => message.realtimeInput?.activityStart)).toBe(true);
  expect(parsedMessages.some((message) => message.realtimeInput?.activityEnd)).toBe(true);
  const audioMessage = parsedMessages.find((message) => message.realtimeInput?.audio);
  expect(audioMessage?.realtimeInput?.audio?.mimeType).toBe("audio/pcm;rate=16000");
  expect(
    atob(audioMessage?.realtimeInput?.audio?.data ?? "").length,
  ).toBe(3200);
});
