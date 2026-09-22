import { Resampler } from './resampler';

// Served verbatim from public/ rather than bundled: Vite inlines small modules
// as data: URLs, which AudioWorklet.addModule does not accept everywhere.
const WORKLET_URL = '/capture-processor.js';

export const CAPTURE_RATE = 16000;

export interface CaptureSource {
  stream: MediaStream;
  label: string;
  release: () => void;
}

export interface Capture {
  stop: () => Promise<void>;
  recorded: () => Int16Array;
  inputRate: number;
}

export async function microphone(): Promise<CaptureSource> {
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: {
      channelCount: 1,
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true,
    },
  });
  return {
    stream,
    label: 'microphone',
    release: () => stream.getTracks().forEach((track) => track.stop()),
  };
}

/** Replays a saved session in place of the microphone, so a prompt change can be
 *  tried against a real voice without asking anyone to sit down again. */
export async function recording(file: File): Promise<CaptureSource> {
  const context = new AudioContext();
  const decoded = await context.decodeAudioData(await file.arrayBuffer());

  // Our own downloads are stereo with the senior on the left and the interviewer
  // on the right. Replaying both channels would have the model listening to its
  // own previous answers.
  const senior = decoded.getChannelData(0);
  const buffer = context.createBuffer(1, senior.length, decoded.sampleRate);
  buffer.copyToChannel(senior, 0);

  const source = context.createBufferSource();
  source.buffer = buffer;
  const destination = context.createMediaStreamDestination();
  source.connect(destination);
  source.start();

  return {
    stream: destination.stream,
    label: file.name,
    release: () => {
      try {
        source.stop();
      } catch {
        // Already finished.
      }
      void context.close();
    },
  };
}

export async function startCapture(
  source: CaptureSource,
  onChunk: (pcm: Int16Array) => void,
): Promise<Capture> {
  // A browser may ignore this and run at its own rate, so we read back what we
  // actually got and resample from there.
  const context = new AudioContext({ sampleRate: CAPTURE_RATE });
  await context.audioWorklet.addModule(WORKLET_URL);

  const resampler = new Resampler(context.sampleRate, CAPTURE_RATE);
  const input = context.createMediaStreamSource(source.stream);
  const node = new AudioWorkletNode(context, 'capture-processor');
  const chunks: Int16Array[] = [];

  node.port.onmessage = (event: MessageEvent<Float32Array>) => {
    const pcm = resampler.process(event.data);
    if (pcm.length === 0) return;
    chunks.push(pcm);
    onChunk(pcm);
  };

  input.connect(node);

  return {
    stop: async () => {
      node.port.onmessage = null;
      input.disconnect();
      node.disconnect();
      source.release();
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
