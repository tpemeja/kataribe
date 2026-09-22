import { GoogleGenAI, type LiveServerMessage, type Session } from '@google/genai';

import { CAPTURE_RATE, startCapture, type Capture } from './audio/capture';
import { Playback } from './audio/playback';
import { buildConversationWav } from './audio/wav';

export type Speaker = 'senior' | 'ai';

export interface Tuning {
  voice: string;
  silenceDurationMs: number;
  endOfSpeechSensitivity: 'LOW' | 'HIGH';
}

export interface InterviewCallbacks {
  onTranscript: (speaker: Speaker, delta: string) => void;
  onStatus: (status: string) => void;
  onClosed: (reason: string) => void;
}

export interface Interview {
  stop: () => Promise<Blob>;
}

interface SessionResponse {
  token: string;
  model: string;
}

export async function startInterview(
  tuning: Tuning,
  callbacks: InterviewCallbacks,
): Promise<Interview> {
  callbacks.onStatus('Requesting a session token');

  const response = await fetch('/api/sessions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      voice: tuning.voice,
      silence_duration_ms: tuning.silenceDurationMs,
      end_of_speech_sensitivity: tuning.endOfSpeechSensitivity,
    }),
  });
  if (!response.ok) {
    throw new Error(`Could not start a session (${response.status}): ${await response.text()}`);
  }
  const { token, model }: SessionResponse = await response.json();

  const playback = new Playback();
  const ai = new GoogleGenAI({ apiKey: token, httpOptions: { apiVersion: 'v1alpha' } });

  callbacks.onStatus('Connecting to Gemini Live');

  let session: Session | undefined;
  let capture: Capture | undefined;

  session = await ai.live.connect({
    model,
    // The interviewer prompt, voice and VAD are locked into the token server-side.
    config: {},
    callbacks: {
      onopen: () => callbacks.onStatus('Listening'),
      onmessage: (message: LiveServerMessage) => {
        const content = message.serverContent;
        if (!content) return;

        if (content.interrupted) playback.flush();

        const heard = content.inputTranscription?.text;
        if (heard) callbacks.onTranscript('senior', heard);

        const spoken = content.outputTranscription?.text;
        if (spoken) callbacks.onTranscript('ai', spoken);

        for (const part of content.modelTurn?.parts ?? []) {
          const encoded = part.inlineData?.data;
          if (encoded) playback.enqueue(decodeBase64(encoded));
        }
      },
      onerror: (event: ErrorEvent) => callbacks.onClosed(event.message || 'Connection error'),
      onclose: (event: CloseEvent) => callbacks.onClosed(event.reason || 'Connection closed'),
    },
  });

  capture = await startCapture((pcm) => {
    // Must be `audio`, not `media`: `media` maps to the legacy mediaChunks
    // field, which the native-audio models accept and then silently ignore.
    session?.sendRealtimeInput({
      audio: { data: encodeBase64(pcm), mimeType: `audio/pcm;rate=${CAPTURE_RATE}` },
    });
  });

  return {
    stop: async () => {
      const mic = capture?.recorded() ?? new Int16Array(0);
      const spoken = playback.recorded();
      await capture?.stop();
      session?.close();
      await playback.close();
      return buildConversationWav(mic, spoken);
    },
  };
}

function encodeBase64(pcm: Int16Array): string {
  const bytes = new Uint8Array(pcm.buffer, pcm.byteOffset, pcm.byteLength);
  let binary = '';
  for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
  return btoa(binary);
}

function decodeBase64(encoded: string): Int16Array {
  const binary = atob(encoded);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return new Int16Array(bytes.buffer, bytes.byteOffset, bytes.byteLength / 2);
}
