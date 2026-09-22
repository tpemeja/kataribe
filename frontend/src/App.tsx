import { useEffect, useRef, useState } from 'react';

import './App.css';
import {
  startInterview,
  type Interview,
  type Phase,
  type Speaker,
  type Tuning,
} from './interview';

interface Entry {
  speaker: Speaker;
  text: string;
}

type SessionPhase = 'idle' | 'starting' | 'live' | 'stopping';

const SPEAKER_LABEL: Record<Speaker, string> = { senior: 'お話しされた方', ai: '聞き手' };

const PHASE_LABEL: Record<Phase, [string, string]> = {
  listening: ['聞いています', 'listening — nothing appears until you pause'],
  thinking: ['考えています', 'heard you, preparing a reply'],
  speaking: ['お話ししています', 'speaking'],
};

export default function App() {
  const [voices, setVoices] = useState<Record<string, string>>({});
  const [tuning, setTuning] = useState<Tuning>({
    voice: 'Sulafat',
    silenceDurationMs: 5000,
    endOfSpeechSensitivity: 'LOW',
  });
  const [phase, setPhase] = useState<SessionPhase>('idle');
  const [status, setStatus] = useState('Ready');
  const [entries, setEntries] = useState<Entry[]>([]);
  const [recordingUrl, setRecordingUrl] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [level, setLevel] = useState(0);
  const [turn, setTurn] = useState<Phase>('listening');
  const [replay, setReplay] = useState<File | null>(null);

  const interview = useRef<Interview | null>(null);
  const transcriptEnd = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    fetch('/api/voices')
      .then((r) => r.json())
      .then(setVoices)
      .catch(() => setStatus('Could not reach the API — is the backend running?'));
  }, []);

  useEffect(() => {
    if (phase !== 'live') return;
    const started = Date.now();
    const timer = setInterval(() => setElapsed(Math.floor((Date.now() - started) / 1000)), 1000);
    return () => clearInterval(timer);
  }, [phase]);

  useEffect(() => {
    transcriptEnd.current?.scrollIntoView({ behavior: 'smooth' });
  }, [entries]);

  const appendTranscript = (speaker: Speaker, delta: string) => {
    setEntries((current) => {
      const last = current[current.length - 1];
      if (last?.speaker === speaker) {
        return [...current.slice(0, -1), { speaker, text: last.text + delta }];
      }
      return [...current, { speaker, text: delta }];
    });
  };

  const start = async () => {
    setPhase('starting');
    setEntries([]);
    setElapsed(0);
    setLevel(0);
    setTurn('listening');
    if (recordingUrl) URL.revokeObjectURL(recordingUrl);
    setRecordingUrl(null);

    try {
      interview.current = await startInterview(
        tuning,
        {
          onTranscript: appendTranscript,
          onStatus: setStatus,
          onLevel: setLevel,
          onPhase: setTurn,
          onClosed: (reason) => {
            setStatus(reason);
            setPhase('idle');
          },
        },
        replay ?? undefined,
      );
      setPhase('live');
    } catch (error) {
      setStatus(error instanceof Error ? error.message : String(error));
      setPhase('idle');
    }
  };

  const stop = async () => {
    setPhase('stopping');
    setStatus('Saving the recording');
    try {
      const wav = await interview.current?.stop();
      if (wav) setRecordingUrl(URL.createObjectURL(wav));
      setStatus('Finished');
    } catch (error) {
      setStatus(error instanceof Error ? error.message : String(error));
    }
    interview.current = null;
    setPhase('idle');
  };

  const busy = phase === 'starting' || phase === 'stopping';
  const live = phase === 'live';

  return (
    <div className="app">
      <header>
        <h1>
          語り部 <span className="subtitle">interview tuning console</span>
        </h1>
        <div className={`status ${live ? 'live' : ''}`}>
          {live && <span className="dot" />}
          {status}
          {live && <span className="elapsed">{formatElapsed(elapsed)}</span>}
        </div>
      </header>

      <section className="controls">
        <label>
          <span>Voice</span>
          <select
            value={tuning.voice}
            disabled={live || busy}
            onChange={(e) => setTuning({ ...tuning, voice: e.target.value })}
          >
            {Object.entries(voices).map(([name, character]) => (
              <option key={name} value={name}>
                {name} — {character}
              </option>
            ))}
          </select>
        </label>

        <label className="slider">
          <span>
            Pause before replying
            <strong>{tuning.silenceDurationMs} ms</strong>
          </span>
          <input
            type="range"
            min={200}
            max={8000}
            step={100}
            value={tuning.silenceDurationMs}
            disabled={live || busy}
            onChange={(e) => setTuning({ ...tuning, silenceDurationMs: Number(e.target.value) })}
          />
          <small>
            The model's own default is 800 ms. Measured here: 3500 ms still cuts into a 2.5 s
            pause, 6000 ms sits through 4 s. Budget roughly double the pause you want tolerated.
          </small>
        </label>

        <label>
          <span>End-of-speech sensitivity</span>
          <select
            value={tuning.endOfSpeechSensitivity}
            disabled={live || busy}
            onChange={(e) =>
              setTuning({
                ...tuning,
                endOfSpeechSensitivity: e.target.value as Tuning['endOfSpeechSensitivity'],
              })
            }
          >
            <option value="LOW">LOW — waits for a clear finish</option>
            <option value="HIGH">HIGH — cuts in sooner</option>
          </select>
        </label>

        <label className="replay">
          <span>
            Input
            {replay && (
              <button className="clear" onClick={() => setReplay(null)} disabled={live || busy}>
                use the microphone
              </button>
            )}
          </span>
          <input
            type="file"
            accept="audio/wav,audio/*"
            disabled={live || busy}
            onChange={(e) => setReplay(e.target.files?.[0] ?? null)}
          />
          <small>
            {replay
              ? `Replaying ${replay.name} instead of the microphone. Only the left channel is sent, so the interviewer does not hear its own previous answers.`
              : 'Live microphone. Choose a downloaded session to replay it instead — the same words, so a prompt or slider change can be compared against the last run.'}
          </small>
        </label>

        <div className="actions">
          {live ? (
            <button className="stop" onClick={stop} disabled={busy}>
              Stop
            </button>
          ) : (
            <button className="start" onClick={start} disabled={busy}>
              {replay ? 'Replay recording' : 'Start conversation'}
            </button>
          )}
          {recordingUrl && (
            <a className="download" href={recordingUrl} download="kataribe-session.wav">
              Download recording
            </a>
          )}
        </div>
      </section>

      {live && (
        <section className={`monitor ${turn}`}>
          <div className="meter" aria-hidden>
            <span style={{ width: `${Math.min(100, level * 260)}%` }} />
          </div>
          <div className="phase">
            <strong>{PHASE_LABEL[turn][0]}</strong>
            <small>{PHASE_LABEL[turn][1]}</small>
          </div>
        </section>
      )}

      <section className="transcript">
        {entries.length === 0 && !live && (
          <p className="empty">
            Start a conversation and speak Japanese. The senior's words appear on the left, the
            interviewer's on the right.
          </p>
        )}
        {entries.length === 0 && live && (
          <p className="empty">
            Nothing reaches the screen while someone is still speaking — the transcript arrives
            only once they pause long enough for the interviewer to take its turn. Watch the bar
            above to confirm the microphone is being heard.
          </p>
        )}
        {entries.map((entry, index) => (
          <article key={index} className={entry.speaker}>
            <span className="who">{SPEAKER_LABEL[entry.speaker]}</span>
            <p>{entry.text}</p>
          </article>
        ))}
        <div ref={transcriptEnd} />
      </section>
    </div>
  );
}

function formatElapsed(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  return `${minutes}:${String(seconds % 60).padStart(2, '0')}`;
}
