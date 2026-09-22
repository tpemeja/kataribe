// Served verbatim from public/ rather than bundled: Vite inlines small modules
// as data: URLs, which AudioWorklet.addModule does not accept everywhere.
const WORKLET_URL = '/capture-processor.js';

export const CAPTURE_RATE = 16000;

export interface Capture {
  stop: () => Promise<void>;
  recorded: () => Int16Array;
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

  // Asking for a 16 kHz context lets the browser resample the mic for us.
  const context = new AudioContext({ sampleRate: CAPTURE_RATE });
  await context.audioWorklet.addModule(WORKLET_URL);

  const source = context.createMediaStreamSource(stream);
  const node = new AudioWorkletNode(context, 'capture-processor');
  const chunks: Int16Array[] = [];

  node.port.onmessage = (event: MessageEvent<Int16Array>) => {
    chunks.push(event.data);
    onChunk(event.data);
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
