import { useEffect, useRef, useState } from 'react';

import './App.css';
import './Family.css';

interface Quote {
  text: string;
  turn: number;
  session_id: string;
  seek_seconds: number;
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

interface Chapter {
  life_stage: string;
  stories: Story[];
}

interface View {
  senior: { name: string; birth_year: number | null; birthplace: string };
  chapters: Chapter[];
  withheld: number;
}

/** What the family sees. Only stories the person agreed to share reach this
 *  page, and the filtering happens in the query rather than here — there is no
 *  path through which a private story arrives and is merely not rendered. */
export default function Family({ seniorId }: { seniorId: string }) {
  const [view, setView] = useState<View | null>(null);
  const [error, setError] = useState<string | null>(null);
  const player = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    fetch(`/api/family/${seniorId}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then(setView)
      .catch(() => setError('We could not find that story.'));
  }, [seniorId]);

  const play = (quote: Quote) => {
    const audio = player.current;
    if (!audio) return;
    const src = `/api/sessions/${quote.session_id}/audio`;
    if (!audio.src.endsWith(src)) audio.src = src;
    audio.currentTime = quote.seek_seconds;
    void audio.play();
  };

  if (error) return <p className="empty">{error}</p>;
  if (!view) return null;

  const told = view.chapters.reduce((n, c) => n + c.stories.length, 0);

  return (
    <div className="family">
      <header>
        <h1>{view.senior.name}</h1>
        <p className="life">
          {view.senior.birth_year && `${view.senior.birth_year}年生まれ`}
          {view.senior.birthplace && ` · ${view.senior.birthplace}`}
        </p>
      </header>

      <audio ref={player} preload="none" />

      {told === 0 && (
        <p className="empty">
          There is nothing here yet. Stories appear once they have been told, and only once they
          have been agreed to be shared.
        </p>
      )}

      {view.chapters.map((chapter) => (
        <section key={chapter.life_stage} className="chapter">
          <h2>{chapter.life_stage}</h2>
          {chapter.stories.map((story) => (
            <article key={story.id} className="told">
              <h3>
                {story.title}
                {story.approx_period && <em>{story.approx_period}</em>}
              </h3>
              <p>{story.summary}</p>
              {story.quotes.map((quote, i) => (
                <blockquote key={i}>
                  <button className="listen" onClick={() => play(quote)} aria-label="Listen">
                    ▶
                  </button>
                  <span>「{quote.text}」</span>
                </blockquote>
              ))}
              {[...story.people, ...story.places].length > 0 && (
                <p className="tags">{[...story.people, ...story.places].join(' · ')}</p>
              )}
            </article>
          ))}
        </section>
      ))}

      {view.withheld > 0 && (
        <p className="withheld">
          {view.withheld === 1
            ? 'One story has been kept private.'
            : `${view.withheld} stories have been kept private.`}{' '}
          Only the person who told them can choose to share them.
        </p>
      )}
    </div>
  );
}
