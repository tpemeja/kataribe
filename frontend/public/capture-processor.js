const CHUNK_SAMPLES = 1024;

// Forwards raw frames at whatever rate the context is running; the main thread
// resamples to the 16 kHz the Live API expects.
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
        const frame = new Float32Array(this.buffer);
        this.port.postMessage(frame, [frame.buffer]);
        this.filled = 0;
      }
    }
    return true;
  }
}

registerProcessor('capture-processor', CaptureProcessor);
