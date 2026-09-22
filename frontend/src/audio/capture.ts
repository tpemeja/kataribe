import { Resampler } from './resampler';

// Served verbatim from public/ rather than bundled: Vite inlines small modules
// as data: URLs, which AudioWorklet.addModule does not accept everywhere.
const WORKLET_URL = '/capture-processor.js';

export const CAPTURE_RATE = 16000;

export interface Capture {
  stop: () => Promise<void>;
  recorded: () => Int16Array;
  inputRate: number;
}

export async function startCapture(onChunk: (pcm: Int16Array) => void): Promise<Capture> {
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: {
      channelCount: 1,
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true,
    },
  });

  // A browser may ignore this and run at its own rate, so we read back what we
  // actually got and resample from there.
  const context = new AudioContext({ sampleRate: CAPTURE_RATE });
  await context.audioWorklet.addModule(WORKLET_URL);

  const resampler = new Resampler(context.sampleRate, CAPTURE_RATE);
  const source = context.createMediaStreamSource(stream);
  const node = new AudioWorkletNode(context, 'capture-processor');
  const chunks: Int16Array[] = [];

  node.port.onmessage = (event: MessageEvent<Float32Array>) => {
    const pcm = resampler.process(event.data);
    if (pcm.length === 0) return;
    chunks.push(pcm);
    onChunk(pcm);
  };

  source.connect(node);

  return {
    stop: async () => {
      node.port.onmessage = null;
      source.disconnect();
      node.disconnect();
      stream.getTracks().forEach((track) => track.stop());
      await context.close();
    },
    recorded: () => concat(chunks),
    inputRate: context.sampleRate,
  };
}

function concat(chunks: Int16Array[]): Int16Array {
  const total = chunks.reduce((n, c) => n + c.length, 0);
  const out = new Int16Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    out.set(chunk, offset);
    offset += chunk.length;
  }
  return out;
}
