import { useEffect, useState } from 'react';

export interface Senior {
  id: string;
  name: string;
  name_reading: string;
  birth_year: number | null;
  birthplace: string;
  family: string[];
}

interface Props {
  selected: string | null;
  onSelect: (id: string | null) => void;
  disabled: boolean;
}

/** Who is being interviewed. The name is given to the interviewer as a fact
 *  rather than transcribed, which is the only reliable way to stop it choosing
 *  the wrong kanji for a name it has only ever heard. */
export default function Seniors({ selected, onSelect, disabled }: Props) {
  const [seniors, setSeniors] = useState<Senior[] | null>(null);
  const [adding, setAdding] = useState(false);
  const [draft, setDraft] = useState({
    name: '',
    name_reading: '',
    birth_year: '',
    birthplace: '',
  });

  // Once, on mount. Re-running this on every selection change reset the form
  // out from under whoever was typing in it.
  useEffect(() => {
    fetch('/api/seniors')
      .then((r) => r.json())
      .then((list: Senior[]) => {
        setSeniors(list);
        if (list.length > 0) onSelect(list[0].id);
      })
      .catch(() => setSeniors([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const save = async () => {
    const response = await fetch('/api/seniors', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: draft.name,
        name_reading: draft.name_reading,
        birth_year: draft.birth_year ? Number(draft.birth_year) : null,
        birthplace: draft.birthplace,
        family: [],
      }),
    });
    const created: Senior = await response.json();
    setSeniors([...(seniors ?? []), created]);
    onSelect(created.id);
    setAdding(false);
    setDraft({ name: '', name_reading: '', birth_year: '', birthplace: '' });
  };

  // Nothing is rendered until we know whether anyone exists, so the form and
  // the picker never flicker past each other.
  if (seniors === null) return null;

  if (adding || seniors.length === 0) {
    return (
      <label className="interviewee">
        <span>Who is being interviewed</span>
        <div className="fields">
          <input
            placeholder="お名前（漢字）"
            value={draft.name}
            onChange={(e) => setDraft({ ...draft, name: e.target.value })}
          />
          <input
            placeholder="読み（ひらがな）"
            value={draft.name_reading}
            onChange={(e) => setDraft({ ...draft, name_reading: e.target.value })}
          />
          <input
            placeholder="生まれ年"
            value={draft.birth_year}
            onChange={(e) => setDraft({ ...draft, birth_year: e.target.value })}
          />
          <input
            placeholder="出身"
            value={draft.birthplace}
            onChange={(e) => setDraft({ ...draft, birthplace: e.target.value })}
          />
          <button className="start" onClick={save} disabled={!draft.name.trim()}>
            Save
          </button>
          {seniors.length > 0 && (
            <button className="clear" onClick={() => setAdding(false)}>
              cancel
            </button>
          )}
        </div>
        <small>
          The name is given to the interviewer rather than transcribed. Heard from audio alone it
          picks a plausible spelling — 佐藤茂 came back as 佐藤繁.
        </small>
      </label>
    );
  }

  return (
    <label className="interviewee">
      <span>
        Who is being interviewed
        <button className="clear" onClick={() => setAdding(true)} disabled={disabled}>
          add someone
        </button>
      </span>
      <select
        value={selected ?? ''}
        disabled={disabled}
        onChange={(e) => onSelect(e.target.value || null)}
      >
        {seniors.map((senior) => (
          <option key={senior.id} value={senior.id}>
            {senior.name}
            {senior.birth_year ? ` · ${senior.birth_year}` : ''}
            {senior.birthplace ? ` · ${senior.birthplace}` : ''}
          </option>
        ))}
      </select>
    </label>
  );
}
