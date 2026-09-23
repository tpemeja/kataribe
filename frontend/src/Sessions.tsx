import { useEffect, useState } from 'react';

interface Summary {
  id: string;
  status: string;
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

interface Quote {
  text: string;
  turn: number;
}

interface Story {
  id: string;
  title: string;
  summary: string;
  life_stage: string;
  approx_period: string;
  people: string[];
  places: string[];
  quotes: Quote[];
}

interface Detail extends Summary {
  model: string;
  end_of_speech_sensitivity: string;
  transcript: Turn[];
  stories: Story[];
  processing_error: string | null;
}

const SPEAKER_LABEL: Record<string, string> = { senior: 'お話しされた方', ai: '聞き手' };

const STATUS_LABEL: Record<string, string> = {
  recorded: 'not processed',
  queued: 'queued',
  processing: 'reading the conversation…',
  processed: '',
  skipped: 'no senior attached',
  failed: 'processing failed',
};

export default function Sessions() {
  const [sessions, setSessions] = useState<Summary[]>([]);
  const [open, setOpen] = useState<Detail | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = () =>
    fetch('/api/sessions')
      .then((r) => r.json())
      .then(setSessions)
      .catch(() => setError('Could not reach the API'));

  useEffect(() => {
    load();
  }, []);

  // Extraction runs behind the upload, so a session can arrive here still
  // being read. Without this the page looks stuck rather than busy.
  useEffect(() => {
    if (!sessions.some((s) => s.status === 'queued' || s.status === 'processing')) return;
    const timer = setInterval(load, 3000);
    return () => clearInterval(timer);
  }, [sessions]);

  const show = async (id: string) => {
    if (open?.id === id) return setOpen(null);
    setOpen(await (await fetch(`/api/sessions/${id}`)).json());
  };

  // The open session is fetched once when it is opened. A story that arrives
  // after that — which is the normal case, since extraction runs behind the
  // upload — would otherwise never appear without closing and reopening.
  useEffect(() => {
    if (!open || (open.status !== 'queued' && open.status !== 'processing')) return;
    const timer = setInterval(async () => {
      setOpen(await (await fetch(`/api/sessions/${open.id}`)).json());
    }, 3000);
    return () => clearInterval(timer);
  }, [open]);

  if (error) return <p className="empty">{error}</p>;
  if (sessions.length === 0) {
    return <p className="empty">No sessions recorded yet. Run one and it will appear here.</p>;
  }

  return (
    <section className="sessions">
      {sessions.map((session) => (
        <article key={session.id} className="session">
          <button className="summary" onClick={() => show(session.id)}>
            <span className="when">
              {new Date(session.started_at).toLocaleString()}
              {STATUS_LABEL[session.status] && (
                <em className={`badge ${session.status}`}>{STATUS_LABEL[session.status]}</em>
              )}
            </span>
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
              {open.processing_error && <p className="failure">{open.processing_error}</p>}
              {session.has_audio && (
                <audio controls preload="none" src={`/api/sessions/${session.id}/audio`} />
              )}

              {open.stories.length > 0 && (
                <div className="stories">
                  {open.stories.map((story) => (
                    <div key={story.id} className="story">
                      <h3>
                        {story.title}
                        <em>
                          {story.life_stage}
                          {story.approx_period && ` · ${story.approx_period}`}
                        </em>
                      </h3>
                      <p>{story.summary}</p>
                      {[...story.people, ...story.places].length > 0 && (
                        <p className="tags">{[...story.people, ...story.places].join(' · ')}</p>
                      )}
                      {story.quotes.map((quote, i) => (
                        <blockquote key={i}>
                          「{quote.text}」<span className="at">turn {quote.turn}</span>
                        </blockquote>
                      ))}
                    </div>
                  ))}
                </div>
              )}

              {open.transcript.length === 0 && <p className="empty">No transcript was captured.</p>}
              {open.transcript.map((turn, index) => (
                <p key={index} className={`line ${turn.speaker} ${quoted(open, index)}`}>
                  <span
                    className="at"
                    title="when the transcript arrived, i.e. the end of the turn"
                  >
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

/** Marks the turns a story actually drew a quote from, so a claim can be traced
 *  back to the words it came from. */
function quoted(detail: Detail, index: number): string {
  return detail.stories.some((s) => s.quotes.some((q) => q.turn === index)) ? 'quoted' : '';
}

function formatLength(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  return `${minutes}:${String(Math.floor(seconds % 60)).padStart(2, '0')}`;
}
