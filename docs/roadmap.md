# Roadmap

Built as vertical slices. Every slice ends with something you can run and show — never a half-wired layer waiting on the next one.

See [plan.md](plan.md) for the product thinking behind this.

## Decisions taken

| Decision | Choice | Why |
| --- | --- | --- |
| Gemini access | Developer API (key + ephemeral tokens) first | Gets a Japanese conversation running in week 1, before any GCP setup. The provider sits behind one adapter, so Vertex is a config swap when the data-residency story matters. |
| Storage | SQLite + local disk, behind a storage port | Zero cloud setup, fast tests, works offline. Firestore and Cloud Storage adapters land when we deploy. |
| Family loop | Family can suggest questions | Relatives submit a question, the AI weaves it into the next session, the answer comes back to them. This is the demo moment that separates us from a memoir app. |
| Repo layout | `backend/` (FastAPI, uv) + `frontend/` (Vite, React, TS) | One Vite app serves kiosk, family view and dev view on separate routes. |

## Demo must-haves

These have to be working on camera. Everything else is cut first if week 4 gets tight.

- Presence detection auto-invite — the senior taps nothing
- Per-story consent to share — the AI asks, the family view obeys
- Cross-session memory — the AI opens by recalling last time and asking what it planned

Audio-linked quotes are built but not a demo gate.

## Slices

| # | Slice | What you can show at the end | Week |
| --- | --- | --- | --- |
| 0 | Walking skeleton | `make dev` runs API and web together; CI green | 1 |
| 1 | It talks | A Japanese voice conversation with Gemini Live in the browser, transcripts on screen | 1 |
| 2 | It remembers the session | Audio and transcripts saved and replayable from a session list | 1 |
| 3 | It has a brain | Stories extracted onto a timeline; gaps found; next questions planned; the AI opens session two by recalling session one | 2 |
| 4 | It notices you | Kiosk mode, presence detection, daily invitation, backing off, big Talk fallback | 3 |
| 5 | It asks permission | Consent requested per story in conversation; family view shows only what was shared, with audio | 3 |
| 6 | The family asks back | Relatives submit questions; the AI asks them next session; answers surface in the family view | 4 |
| 7 | Ready to judge | English dev view, deployed, demo video with subtitles, pitch deck | 4 |

## Schedule

Prototype deadline **2026-10-18**. A real senior tests from week 2.

| Week | Dates | Slices |
| --- | --- | --- |
| 1 | Sep 22–28 | 0, 1, 2 |
| 2 | Sep 29–Oct 5 | 3, plus the first session with a real senior |
| 3 | Oct 6–12 | 4, 5 |
| 4 | Oct 13–18 | 6, 7, second real-senior test, demo video |

## Status

- [x] **0 — Walking skeleton**
- [ ] 1 — It talks
- [ ] 2 — It remembers the session
- [ ] 3 — It has a brain
- [ ] 4 — It notices you
- [ ] 5 — It asks permission
- [ ] 6 — The family asks back
- [ ] 7 — Ready to judge

## Open questions

Tracked in [plan.md](plan.md#open-questions-and-risks). The one that gates slice 1: which Live model handles elderly Japanese speech best, and does it hold the language steady.
