const CHUNK_SAMPLES = 512;

class CaptureProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.buffer = new Float32Array(CHUNK_SAMPLES);
    this.filled = 0;
  }

  process(inputs) {
    const channel = inputs[0]?.[0];
    if (!channel) return true;

    for (let i = 0; i < channel.length; i++) {
      this.buffer[this.filled++] = channel[i];
      if (this.filled === CHUNK_SAMPLES) {
        const pcm = new Int16Array(CHUNK_SAMPLES);
        for (let j = 0; j < CHUNK_SAMPLES; j++) {
          const clamped = Math.max(-1, Math.min(1, this.buffer[j]));
          pcm[j] = clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff;
        }
        this.port.postMessage(pcm, [pcm.buffer]);
        this.filled = 0;
      }
    }
    return true;
  }
}

registerProcessor('capture-processor', CaptureProcessor);
