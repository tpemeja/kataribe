import { describe, expect, it } from 'vitest';

import { Resampler } from './resampler';

function tone(length: number, rate: number, hz = 220): Float32Array {
  const frame = new Float32Array(length);
  for (let i = 0; i < length; i++) frame[i] = Math.sin((2 * Math.PI * hz * i) / rate);
  return frame;
}

describe('Resampler', () => {
  it('produces the target rate across chunk boundaries', () => {
    const resampler = new Resampler(48000, 16000);
    const input = tone(48000, 48000);

    let fed = 0;
    let produced = 0;
    for (let i = 0; i + 1024 <= input.length; i += 1024) {
      produced += resampler.process(input.subarray(i, i + 1024)).length;
      fed += 1024;
    }

    // Sending faster than real time closes the socket, so the ratio has to hold
    // over the whole stream, not just within a chunk.
    expect(produced / fed).toBeCloseTo(16000 / 48000, 3);
  });

  it('passes through untouched when the rates already match', () => {
    const resampler = new Resampler(16000, 16000);

    const pcm = resampler.process(tone(512, 16000));

    expect(pcm.length).toBe(512);
  });

  it('keeps the signal intact rather than emitting silence', () => {
    const resampler = new Resampler(44100, 16000);

    const pcm = resampler.process(tone(4410, 44100));

    const peak = Math.max(...Array.from(pcm, Math.abs));
    expect(peak).toBeGreaterThan(0x4000);
  });
});
