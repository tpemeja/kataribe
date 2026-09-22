import { CAPTURE_RATE } from './capture';
import { PLAYBACK_RATE, type PlayedChunk } from './playback';

/**
 * Stereo WAV of the whole conversation: senior on the left, AI on the right.
 * The AI chunks are placed at the time they were actually played, so the two
 * sides line up and the file can be reviewed as a conversation.
 */
export function buildConversationWav(mic: Int16Array, ai: PlayedChunk[]): Blob {
  const left = resample(mic, CAPTURE_RATE, PLAYBACK_RATE);

  let frames = left.length;
  for (const chunk of ai) {
    frames = Math.max(frames, Math.round(chunk.offsetSec * PLAYBACK_RATE) + chunk.pcm.length);
  }

  const right = new Int16Array(frames);
  for (const chunk of ai) {
    const start = Math.round(chunk.offsetSec * PLAYBACK_RATE);
    for (let i = 0; i < chunk.pcm.length && start + i < frames; i++) {
      right[start + i] = chunk.pcm[i];
    }
  }

  return encodeWav(left, right, frames, PLAYBACK_RATE);
}

function resample(input: Int16Array, from: number, to: number): Int16Array {
  if (from === to) return input;
  const ratio = from / to;
  const out = new Int16Array(Math.floor(input.length / ratio));
  for (let i = 0; i < out.length; i++) {
    const position = i * ratio;
    const index = Math.floor(position);
    const next = Math.min(index + 1, input.length - 1);
    const weight = position - index;
    out[i] = input[index] * (1 - weight) + input[next] * weight;
  }
  return out;
}

function encodeWav(left: Int16Array, right: Int16Array, frames: number, rate: number): Blob {
  const blockAlign = 4;
  const dataBytes = frames * blockAlign;
  const view = new DataView(new ArrayBuffer(44 + dataBytes));

  const ascii = (offset: number, text: string) => {
    for (let i = 0; i < text.length; i++) view.setUint8(offset + i, text.charCodeAt(i));
  };

  ascii(0, 'RIFF');
  view.setUint32(4, 36 + dataBytes, true);
  ascii(8, 'WAVE');
  ascii(12, 'fmt ');
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 2, true);
  view.setUint32(24, rate, true);
  view.setUint32(28, rate * blockAlign, true);
  view.setUint16(32, blockAlign, true);
  view.setUint16(34, 16, true);
  ascii(36, 'data');
  view.setUint32(40, dataBytes, true);

  for (let i = 0; i < frames; i++) {
    view.setInt16(44 + i * 4, left[i] ?? 0, true);
    view.setInt16(46 + i * 4, right[i] ?? 0, true);
  }

  return new Blob([view.buffer], { type: 'audio/wav' });
}
