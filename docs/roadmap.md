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
| VAD patience | Tunable in the console, not hardcoded | Default 800 ms of silence ends a turn — far too short for someone retrieving a sixty-year-old memory. The right number is an empirical question about real speech, so we find it with a real speaker and bake in what wins. |
| Interviewer prompt | Full first draft, Japanese source with an English gloss | A test session with a toy prompt tells us nothing about whether the interview *feels* right. The Japanese file ships; the English one exists so the team can review changes and the dev view can show them. |
| Session recording | Stereo WAV built in the browser | Senior left, AI right, aligned on a shared timeline. Without it the first real session is unreviewable after the fact. |
| Token security | Config locked server-side into the ephemeral token | The interviewer persona is the product; the browser gets a token that cannot rewrite it. Tuning values are requested by the client but validated and locked by the backend. |

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
- [~] **1 — It talks** — built; waiting on a live test with a Japanese speaker

- [ ] 2 — It remembers the session
- [ ] 3 — It has a brain
- [ ] 4 — It notices you
- [ ] 5 — It asks permission
- [ ] 6 — The family asks back
- [ ] 7 — Ready to judge

## Running the week-1 test

```bash
make dev          # API on :8000, console on :5173
```

Open <http://localhost:5173> in Chrome, then **hard-reload** (Cmd-Shift-R). The audio worklet is served from `public/` and browsers cache it across restarts.

### Pre-flight, on your own, before anyone else is in the room

Press **Start conversation**, allow the microphone, say anything for ten seconds, and watch the browser console:

```
[kataribe] mic 16000 Hz -> 16000 Hz
[kataribe] sent 5.0s, peak 34%
```

- **`peak 0%`** means the microphone is delivering silence. Nothing else will work; fix the input device first.
- **`peak 99%`** every time means it is clipping. Move back from the mic.
- **Anything about "Closed 1007"** means the session is being rejected. Stop and report it rather than continuing.

Do not spend a native speaker's time until this reads sensibly and Japanese words appear in the transcript.

### The session itself

Pick a voice, set the pause slider, press **Start conversation**. Changing a tuning value starts a fresh session, because the values are locked into the token when it is minted — so work in short runs rather than one long one.

What the tester is judging — a native Japanese speaker, not necessarily elderly:

1. **Does it interrupt?** Pause mid-sentence for two or three seconds, as if retrieving a memory. Raise the slider until the interviewer waits. That number is the main output of this test. Measured against synthesized speech, for a starting point:

   | Patience | Pause | Result |
   | --- | --- | --- |
   | 3500 ms | 1.5 s | waited |
   | 3500 ms | 2.5 s | **cut in** |
   | 6000 ms | 2.5 s | waited |
   | 6000 ms | 4.0 s | waited |

   The gap the model sees is longer than the pause itself, so budget roughly double. The default is now 5000 ms and the slider reaches 8000 ms.
2. **Does it stay in Japanese?** It should never drift to English, even after a long silence.
3. **Is the transcription good enough to build stories from?** Names and place names especially — those become the timeline in slice 3.
4. **Does the interviewer behave?** One question at a time, short turns, follows a change of subject, backs off when told to, closes warmly with a topic for next time.
5. **Which voice?** Seven are shortlisted. Pick by ear.

Download the recording afterwards — senior on the left channel, interviewer on the right.

### Replaying a session

The console takes a downloaded recording in place of the microphone, so a prompt edit or a new slider value can be tried against the same words rather than asking someone to sit down again. Only the left channel is sent, so the interviewer never hears its own previous answers.

It is the fastest way to iterate, and the only way to compare two prompts on identical input. It does not replace a live session: a replay cannot react, so it tells you nothing about interruption or turn-taking.

A recording worth keeping belongs in `backend/tests/live/recordings/`, where `make eval` will replay it as a fixture — that is how this suite stops being graded on synthesized speech.

### Slice 1 is done when

- [ ] A five-minute Japanese conversation runs with no disconnect
- [ ] The interviewer does not talk over a three-second pause for thought, at a known slider value
- [ ] It never drifts out of Japanese
- [ ] A native speaker says the transcript matches what was actually said, names and places included
- [ ] A voice is chosen
- [ ] The recording downloads and plays back as a conversation

Write the slider value and the voice into the defaults once they are known: `InterviewTuning` in `backend/src/kataribe/gemini.py`.

### Sparring with a simulated interviewee

`make spar` puts the interviewer in a live conversation with an AI playing the person being interviewed, so timing can be worked on without asking anyone to sit down. Both sides are real audio, so pauses, barge-in and turn-taking are genuine.

```bash
make spar                                    # 田中ハル, the default
make spar PERSONA=shigeru SECONDS=90         # a longer session
make spar PERSONA=kimiko PATIENCE=2500       # sweep the slider
```

Three personas, each pressing a different rule:

| Persona | Exercises |
| --- | --- |
| `haru` | Pauses two or three seconds mid-memory — the interviewer must not fill them |
| `shigeru` | Refuses to discuss the war — the interviewer must drop it |
| `kimiko` | Drifts to another subject — the interviewer must follow rather than steer back |

Each prints who spoke when, flags any moment the interviewer talked over the other side, and saves a stereo recording under `backend/var/spar/`. Their biographies are fixed, so once stories are being extracted the extraction can be graded against facts we already know.

#### Why sessions used to die after two minutes

Worth recording, because it was nearly missed and it bears on the 5–10 minute sessions the product needs.

Sparring sessions kept dying around 70–130 seconds with `1011 keepalive ping timeout`. It looked like a quirk of the test harness. It was not: the same thing killed the interviewer's own session at 130s, and no test had ever run long enough to notice, since every one of them finished inside a minute.

The cause was ours. The SDK hands the Python websockets library its default 20 second ping timeout, and the Live API does not reliably pong inside that window, so a healthy connection was being hung up on by our own client. The server was never asking us to leave — it sent no `go_away` at any point. With the timeout disabled, one connection ran 391 seconds.

Two things follow:

- Harness clients are built through `tests/live/connection.py`, which turns the ping timeout off.
- The browser does its own keepalive and exposes no such setting, so the product path was never affected by this particular cause. Confirmed rather than assumed: a browser session ran a full six minutes with 34 transcript entries and no drop. `pnpm test:endurance` keeps it that way, nightly.

Session resumption was also verified to work — `SessionResumptionConfig`, a handle on every `session_resumption_update`, and a reconnect that carries the conversation across. It is not needed for this cause, but it is the documented answer for a genuine server-side drop and the mechanism is proven should a long session need it.

### What `make eval` already checks for you

Before spending anyone's time, `make eval` streams synthesized Japanese at the real API and asserts the transcript is accurate, the interviewer waits through a pause, cuts in when patience is lowered, replies in Japanese asking one thing, backs off when a topic is refused, and that the whole loop works in a real browser.

It leaves exactly one thing it cannot judge, which is the point of the human session: **whether the Japanese is good.** A native speaker has not yet reviewed `interviewer_ja.md`, and one known issue is already marked `xfail` — the interviewer sometimes recaps what it heard before asking, which its own prompt forbids. Whether that reads as natural aizuchi or as presumptuous is a call only a native speaker can make.

## Open questions

Tracked in [plan.md](plan.md#open-questions-and-risks).

Model choice is settled: **`gemini-3.8-live`** (GA) for voice, `gemini-3.8-flash` for the extraction and planning passes. The remaining question that gates slice 1 is empirical — does it handle elderly Japanese speech well, and does it hold the language steady across a long pause?
