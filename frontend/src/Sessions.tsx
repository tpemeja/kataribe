import { useEffect, useState } from 'react';

interface Summary {
  id: string;
  started_at: string;
  duration_seconds: number | null;
  voice: string;
  silence_duration_ms: number;
  input_label: string;
  turns: number;
  has_audio: boolean;
}

interface Turn {
  speaker: string;
  text: string;
  started_at: number;
}

interface Detail extends Summary {
  model: string;
  end_of_speech_sensitivity: string;
  transcript: Turn[];
}

const SPEAKER_LABEL: Record<string, string> = { senior: 'お話しされた方', ai: '聞き手' };

export default function Sessions() {
  const [sessions, setSessions] = useState<Summary[]>([]);
  const [open, setOpen] = useState<Detail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch('/api/sessions')
      .then((r) => r.json())
      .then(setSessions)
      .catch(() => setError('Could not reach the API'));
  }, []);

  const show = async (id: string) => {
    if (open?.id === id) return setOpen(null);
    const response = await fetch(`/api/sessions/${id}`);
    setOpen(await response.json());
  };

  if (error) return <p className="empty">{error}</p>;
  if (sessions.length === 0) {
    return <p className="empty">No sessions recorded yet. Run one and it will appear here.</p>;
  }

  return (
    <section className="sessions">
      {sessions.map((session) => (
        <article key={session.id} className="session">
          <button className="summary" onClick={() => show(session.id)}>
            <span className="when">{new Date(session.started_at).toLocaleString()}</span>
            <span className="facts">
              {session.duration_seconds === null
                ? 'unfinished — never stopped'
                : `${session.turns} turns · ${formatLength(session.duration_seconds)}`}
              {` · ${session.voice} · ${session.silence_duration_ms} ms`}
              {session.input_label !== 'microphone' && ` · ${session.input_label}`}
            </span>
          </button>

          {open?.id === session.id && (
            <div className="detail">
              {session.has_audio && (
                <audio controls preload="none" src={`/api/sessions/${session.id}/audio`} />
              )}
              {open.transcript.length === 0 && <p className="empty">No transcript was captured.</p>}
              {open.transcript.map((turn, index) => (
                <p key={index} className={`line ${turn.speaker}`}>
                  <span className="at" title="when the transcript arrived, i.e. the end of the turn">
                    {formatLength(turn.started_at)}
                  </span>
                  <span className="who">{SPEAKER_LABEL[turn.speaker] ?? turn.speaker}</span>
                  <span className="said">{turn.text}</span>
                </p>
              ))}
            </div>
          )}
        </article>
      ))}
    </section>
  );
}

function formatLength(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  return `${minutes}:${String(Math.floor(seconds % 60)).padStart(2, '0')}`;
}
