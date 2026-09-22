/**
 * Streaming linear resampler, float frames in, 16-bit PCM out.
 *
 * The Live API reads timing from the audio it receives, so sending faster than
 * real time closes the socket with "invalid argument". A browser is free to
 * ignore a requested AudioContext rate and hand back 44.1 or 48 kHz, so we
 * resample from whatever rate we actually got rather than trusting the label.
 */
export class Resampler {
  private carry = new Float32Array(0);
  private position = 0;
  private readonly from: number;
  private readonly to: number;

  constructor(from: number, to: number) {
    this.from = from;
    this.to = to;
  }

  process(frame: Float32Array): Int16Array {
    if (this.from === this.to) return toPcm16(frame, frame.length);

    const buffer = new Float32Array(this.carry.length + frame.length);
    buffer.set(this.carry);
    buffer.set(frame, this.carry.length);

    const step = this.from / this.to;
    const samples = new Float32Array(Math.ceil(buffer.length / step) + 1);
    let count = 0;
    let position = this.position;

    while (Math.floor(position) + 1 < buffer.length) {
      const index = Math.floor(position);
      const weight = position - index;
      samples[count++] = buffer[index] * (1 - weight) + buffer[index + 1] * weight;
      position += step;
    }

    const consumed = Math.floor(position);
    this.carry = buffer.slice(consumed);
    this.position = position - consumed;

    return toPcm16(samples, count);
  }
}

function toPcm16(samples: Float32Array, count: number): Int16Array {
  const pcm = new Int16Array(count);
  for (let i = 0; i < count; i++) {
    const clamped = Math.max(-1, Math.min(1, samples[i]));
    pcm[i] = clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff;
  }
  return pcm;
}
