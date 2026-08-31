const TARGET_SAMPLE_RATE = 16000;
const SAMPLES_PER_CHUNK = 1600;

class Pcm16WorkletProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.inputBuffer = [];
    this.inputOffset = 0;
    this.outputBuffer = [];
    this.port.onmessage = (event) => {
      if (event.data === "flush") this.flush();
    };
  }

  process(inputs) {
    const channel = inputs[0]?.[0];
    if (!channel) return true;

    for (let index = 0; index < channel.length; index += 1) {
      this.inputBuffer.push(channel[index]);
    }

    const ratio = sampleRate / TARGET_SAMPLE_RATE;
    while (this.inputOffset + ratio <= this.inputBuffer.length) {
      const leftIndex = Math.floor(this.inputOffset);
      const rightIndex = Math.min(leftIndex + 1, this.inputBuffer.length - 1);
      const fraction = this.inputOffset - leftIndex;
      const sample =
        this.inputBuffer[leftIndex] * (1 - fraction) +
        this.inputBuffer[rightIndex] * fraction;
      const clamped = Math.max(-1, Math.min(1, sample));
      this.outputBuffer.push(
        clamped < 0 ? Math.round(clamped * 0x8000) : Math.round(clamped * 0x7fff),
      );
      this.inputOffset += ratio;
    }

    const consumed = Math.floor(this.inputOffset);
    if (consumed > 0) {
      this.inputBuffer = this.inputBuffer.slice(consumed);
      this.inputOffset -= consumed;
    }

    this.emitFullChunks();
    return true;
  }

  flush() {
    this.emitFullChunks();
    if (this.outputBuffer.length === 0) return;
    const remainder = Int16Array.from(this.outputBuffer);
    this.outputBuffer = [];
    this.port.postMessage(
      { type: "chunk", buffer: remainder.buffer },
      [remainder.buffer],
    );
  }

  emitFullChunks() {
    while (this.outputBuffer.length >= SAMPLES_PER_CHUNK) {
      const chunk = Int16Array.from(
        this.outputBuffer.splice(0, SAMPLES_PER_CHUNK),
      );
      this.port.postMessage(
        { type: "chunk", buffer: chunk.buffer },
        [chunk.buffer],
      );
    }
  }
}

registerProcessor("pcm16-worklet", Pcm16WorkletProcessor);
