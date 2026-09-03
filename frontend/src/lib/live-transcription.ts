export type LiveTranscriptHandlers = {
  onInterim: (text: string) => void;
  onFinal: (text: string) => void;
  onError: (error: Error) => void;
};

type SpeechToken = {
  token: string;
  model: string;
};

const MODEL = "gemini-3.5-transcribe-live";
const LIVE_API_VERSION = "v1alpha";
const TOKEN_ROUTE = "/api/speech-token";
const AUDIO_MIME_TYPE = "audio/pcm;rate=16000";

function parseToken(value: unknown): SpeechToken {
  if (
    typeof value !== "object" ||
    value === null ||
    typeof (value as Partial<SpeechToken>).token !== "string" ||
    typeof (value as Partial<SpeechToken>).model !== "string"
  ) {
    throw new Error("Token nhận dạng giọng nói không hợp lệ.");
  }

  const token = value as SpeechToken;
  if (!token.token.trim() || token.model !== MODEL) {
    throw new Error("Cấu hình nhận dạng giọng nói không hợp lệ.");
  }
  return token;
}

function errorFromPayload(value: unknown) {
  if (
    typeof value === "object" &&
    value !== null &&
    typeof (value as { error?: unknown }).error === "string"
  ) {
    return (value as { error: string }).error;
  }
  return "Không thể khởi tạo nhận dạng giọng nói.";
}

function arrayBufferToBase64(buffer: ArrayBuffer) {
  const bytes = new Uint8Array(buffer);
  let binary = "";
  for (let index = 0; index < bytes.length; index += 1) {
    binary += String.fromCharCode(bytes[index]);
  }
  return window.btoa(binary);
}

function wait(milliseconds: number) {
  return new Promise<void>((resolve) => window.setTimeout(resolve, milliseconds));
}

export class LiveTranscriptionSession {
  private socket: WebSocket | null = null;
  private stream: MediaStream | null = null;
  private context: AudioContext | null = null;
  private source: MediaStreamAudioSourceNode | null = null;
  private worklet: AudioWorkletNode | null = null;
  private mute: GainNode | null = null;
  private handlers: LiveTranscriptHandlers;
  private setupPromise: Promise<void> | null = null;
  private setupResolve: (() => void) | null = null;
  private setupReject: ((error: Error) => void) | null = null;
  private closed = false;

  constructor(handlers: LiveTranscriptHandlers) {
    this.handlers = handlers;
  }

  async start() {
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      this.context = new AudioContext();
      await this.context.audioWorklet.addModule("/audio/pcm16-worklet.js");
      this.worklet = new AudioWorkletNode(this.context, "pcm16-worklet", {
        numberOfInputs: 1,
        numberOfOutputs: 1,
        channelCount: 1,
        channelCountMode: "explicit",
        channelInterpretation: "speakers",
      });
      this.worklet.port.onmessage = (event: MessageEvent) => {
        if (event.data?.type !== "chunk" || !(event.data.buffer instanceof ArrayBuffer)) {
          return;
        }
        this.sendAudio(event.data.buffer);
      };
      this.mute = this.context.createGain();
      this.mute.gain.value = 0;
      this.source = this.context.createMediaStreamSource(this.stream);
      this.source.connect(this.worklet).connect(this.mute).connect(this.context.destination);

      const tokenResponse = await fetch(TOKEN_ROUTE, {
        method: "POST",
        cache: "no-store",
      });
      const tokenPayload: unknown = await tokenResponse.json().catch(() => null);
      if (!tokenResponse.ok) throw new Error(errorFromPayload(tokenPayload));
      const { token, model } = parseToken(tokenPayload);

      this.setupPromise = new Promise<void>((resolve, reject) => {
        this.setupResolve = resolve;
        this.setupReject = reject;
      });
      this.socket = new WebSocket(
        `wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.${LIVE_API_VERSION}.GenerativeService.BidiGenerateContentConstrained?access_token=${encodeURIComponent(token)}`,
      );
      this.socket.onopen = () => {
        this.socket?.send(JSON.stringify({
          setup: {
            model: `models/${model}`,
            generationConfig: { responseModalities: ["TEXT"] },
            realtimeInputConfig: {
              automaticActivityDetection: { disabled: true },
            },
            inputAudioTranscription: {
              languageCodes: ["vi-VN"],
              mode: "SMART",
            },
          },
        }));
      };
      this.socket.onmessage = (event) => {
        void this.handleMessage(event).catch(() => {
          this.fail(new Error("Gemini Live trả về dữ liệu không hợp lệ."));
        });
      };
      this.socket.onerror = () => this.fail(new Error("Kết nối Gemini Live bị lỗi."));
      this.socket.onclose = () => {
        if (!this.closed) this.fail(new Error("Phiên nhận dạng giọng nói đã đóng."));
      };
      const setupPromise = this.setupPromise;
      await Promise.race([
        setupPromise,
        wait(10_000).then(() => {
          throw new Error("Gemini Live không phản hồi bước khởi tạo.");
        }),
      ]);
      this.socket.send(JSON.stringify({ realtimeInput: { activityStart: {} } }));
      await this.context.resume();
    } catch (error) {
      await this.close();
      throw error instanceof Error
        ? error
        : new Error("Không thể khởi tạo microphone.");
    }
  }

  async end() {
    if (this.closed) return;
    this.worklet?.port.postMessage("flush");
    await wait(60);
    if (this.socket?.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify({ realtimeInput: { activityEnd: {} } }));
    }
    this.source?.disconnect();
    this.worklet?.disconnect();
    this.mute?.disconnect();
    this.stream?.getTracks().forEach((track) => track.stop());
    if (this.context) await this.context.suspend().catch(() => undefined);
  }

  async close() {
    if (this.closed) return;
    this.closed = true;
    this.setupReject?.(new Error("Phiên nhận dạng giọng nói đã đóng."));
    this.socket?.close();
    this.source?.disconnect();
    this.worklet?.disconnect();
    this.mute?.disconnect();
    this.stream?.getTracks().forEach((track) => track.stop());
    await this.context?.close().catch(() => undefined);
    this.socket = null;
    this.stream = null;
    this.context = null;
    this.source = null;
    this.worklet = null;
    this.mute = null;
  }

  private sendAudio(buffer: ArrayBuffer) {
    if (this.socket?.readyState !== WebSocket.OPEN || this.closed) return;
    this.socket.send(JSON.stringify({
      realtimeInput: {
        audio: { data: arrayBufferToBase64(buffer), mimeType: AUDIO_MIME_TYPE },
      },
    }));
  }

  private async handleMessage(event: MessageEvent) {
    let rawMessage: string;
    if (typeof event.data === "string") {
      rawMessage = event.data;
    } else if (event.data instanceof Blob) {
      rawMessage = await event.data.text();
    } else if (event.data instanceof ArrayBuffer) {
      rawMessage = new TextDecoder().decode(event.data);
    } else {
      return;
    }

    let message: unknown;
    try {
      message = JSON.parse(rawMessage);
    } catch {
      this.fail(new Error("Gemini Live trả về dữ liệu không hợp lệ."));
      return;
    }

    if (typeof message !== "object" || message === null) return;
    const value = message as {
      setupComplete?: unknown;
      error?: { message?: string };
      serverContent?: {
        interimInputTranscription?: { text?: string };
        inputTranscription?: { text?: string };
      };
    };
    if (value.error) {
      this.fail(new Error(value.error.message || "Gemini Live trả về lỗi."));
      return;
    }
    if (value.setupComplete !== undefined) {
      this.setupResolve?.();
      this.setupResolve = null;
      this.setupReject = null;
    }
    const content = value.serverContent;
    const interim = content?.interimInputTranscription?.text;
    const finalized = content?.inputTranscription?.text;
    if (typeof interim === "string") this.handlers.onInterim(interim);
    if (typeof finalized === "string") this.handlers.onFinal(finalized);
  }

  private fail(error: Error) {
    this.setupReject?.(error);
    this.setupResolve = null;
    this.setupReject = null;
    this.handlers.onError(error);
  }
}
