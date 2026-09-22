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

/** Nothing reaches the screen while someone is still talking — transcripts only
 *  arrive once the model accepts the turn has ended, which the patience setting
 *  delays on purpose. Without a live level and a phase, a working session is
 *  indistinguishable from a broken one for several seconds. */
export type Phase = 'listening' | 'thinking' | 'speaking';

export interface InterviewCallbacks {
  onTranscript: (speaker: Speaker, delta: string) => void;
  onStatus: (status: string) => void;
  onLevel: (level: number) => void;
  onPhase: (phase: Phase) => void;
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
  let playedAnything = false;

  session = await ai.live.connect({
    model,
    // The interviewer prompt, voice and VAD are locked into the token server-side.
    config: {},
    callbacks: {
      onopen: () => callbacks.onStatus('Listening'),
      onmessage: (message: LiveServerMessage) => {
        const content = message.serverContent;
        if (!content) return;

        if (content.interrupted) {
          playback.flush();
          callbacks.onPhase('listening');
        }

        const heard = content.inputTranscription?.text;
        if (heard) {
          callbacks.onTranscript('senior', heard);
          callbacks.onPhase('thinking');
        }

        const spoken = content.outputTranscription?.text;
        if (spoken) {
          callbacks.onTranscript('ai', spoken);
          callbacks.onPhase('speaking');
        }

        for (const part of content.modelTurn?.parts ?? []) {
          const encoded = part.inlineData?.data;
          if (!encoded) continue;
          if (!playedAnything) {
            playedAnything = true;
            console.info('[kataribe] interviewer started speaking');
          }
          playback.enqueue(decodeBase64(encoded));
        }

        if (content.turnComplete) callbacks.onPhase('listening');
      },
      onerror: (event: ErrorEvent) => callbacks.onClosed(event.message || 'Connection error'),
      onclose: (event: CloseEvent) =>
        callbacks.onClosed(`Closed ${event.code}: ${event.reason || 'no reason given'}`),
    },
  });

  let sent = 0;
  let peak = 0;
  capture = await startCapture((pcm) => {
    sent += pcm.length;
    let loudest = 0;
    for (let i = 0; i < pcm.length; i++) {
      const level = Math.abs(pcm[i]);
      if (level > loudest) loudest = level;
    }
    if (loudest > peak) peak = loudest;
    callbacks.onLevel(loudest / 0x8000);
    // Must be `audio`, not `media`: `media` maps to the legacy mediaChunks
    // field, which the native-audio models accept and then silently ignore.
    session?.sendRealtimeInput({
      audio: { data: encodeBase64(pcm), mimeType: `audio/pcm;rate=${CAPTURE_RATE}` },
    });
  });

  // The socket closes if audio arrives faster than real time, so the mic rate
  // we actually got is the first thing worth seeing when a session misbehaves.
  console.info(`[kataribe] mic ${capture.inputRate} Hz -> ${CAPTURE_RATE} Hz`);
  callbacks.onStatus(
    capture.inputRate === CAPTURE_RATE
      ? 'Listening'
      : `Listening (mic ${capture.inputRate} Hz, resampled)`,
  );

  const heartbeat = setInterval(() => {
    const level = ((peak / 0x8000) * 100).toFixed(0);
    console.info(`[kataribe] sent ${(sent / CAPTURE_RATE).toFixed(1)}s, peak ${level}%`);
    peak = 0;
  }, 5000);

  return {
    stop: async () => {
      clearInterval(heartbeat);
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
