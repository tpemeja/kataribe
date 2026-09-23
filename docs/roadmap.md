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
- [x] **2 — It remembers the session** — sessions, transcripts and audio stored and replayable
- [x] **3 — It has a brain** — stories extracted and verified, timeline, gaps, next questions, context carried into the following session
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

## Linking a quote to its audio needs a separate pass

Slice 5 shows every passage with the senior's own voice behind it, which needs to know where in the recording each phrase sits.

The Live API takes `word_timestamp` on its transcription config and then ignores it: the transcription comes back with text and an empty `words` list, on a raw key as well as through an ephemeral token, with and without `VERBATIM` mode. It is still requested, so offsets arrive free if that changes, but nothing may be built on it.

Stored turns carry a `started_at`, and it is honest about what it is: the moment the transcript *arrived*, which is when the turn ended. In a thirteen second session both turns were stamped at 0:12 and 0:13. Useful for ordering, useless for seeking.

So slice 5 needs the offsets from somewhere else — most likely a transcription pass over the stored recording during slice 3's processing, which would also be a second opinion on accuracy. `gemini-3.5-transcribe-live` is the obvious candidate to try first.

## French and English are for testing, not for shipping

The product is Japanese. French and English exist so the whole loop can be exercised without a Japanese speaker in the room: pick a language when creating a person, and the interview, the extraction and the planning all run in it.

**What a green run in French tells you.** Turn-taking and interruption, whether it follows a change of subject, whether it backs off when refused, whether it invents details, whether it over-recaps, and that extraction, gaps, planning and cross-session memory work. That is most of the behaviour, and it can be judged by anyone who speaks the language.

**What it does not tell you.** Honorific register has no French equivalent, and the kanji homophones that make a name come back misspelled do not exist outside Japanese — the defect does not get fixed there, it simply cannot occur. Neither does it say whether the Japanese sounds warm or stiff to a Japanese ear.

So "it works in French" must never be read as "it works". The Japanese session with a native speaker is still the one that decides.

**Settings are per language** for the same reason. Each language keeps its own voice and pause length, and only the Japanese pause figure was measured against real speech — the others are starting guesses, and the console says so when one is selected. A value that feels right in a French test cannot become the one an elderly Japanese speaker gets.

The extraction and planning instructions are written once, in English, and told which language to write in. Three translated copies would drift apart, and the rules they carry — do not invent, do not paraphrase inside a quotation — are the same in any language. The Japanese live tests were run before and after that change to confirm the Japanese behaviour did not move.

## Known prompt gaps

Measured with `tests/live/test_conversation.py`, which now runs a real multi-turn conversation. Before the harness fix below it only ever reached one exchange, so every earlier figure here described first-turn behaviour and has been discarded.

| What it does | Status |
| --- | --- |
| Raises a refused topic again | **Fixed.** Broken by the prompt rewrite itself, then fixed by giving rule 2 its exception. |
| Steers back instead of following a change of subject | **Mostly works.** Over nine turns it followed her from sunbathing to the weather to the department store to the neighbour to the cat, then repeated an earlier question once. A lapse rather than a rule it ignores. |
| Uses the wrong kanji for a name | **Fix in place, not yet proven.** The name now reaches the prompt from the senior's profile instead of being transcribed. Whether the model always uses the spelling it is given is a separate question, and one run is not an answer. |
| Recaps what it heard before asking | **Open**, and a native speaker's call: whether 〜のですね reads as natural aizuchi or as presumptuous is not something the harness can settle. |

Note that a per-conversation pass rate is harsher than a per-turn one: nine turns give four or five chances to slip, so one lapse fails the whole run.

### Deferred: names come back with the wrong kanji

He introduced himself as 佐藤**茂**; the interviewer called him 佐藤**繁**. Both read *Shigeru*. The model hears a sound and picks a plausible spelling for it.

This matters more than it looks. The output of this product is a memoir a family keeps, and misspelling a grandfather's name in it is not a cosmetic defect. It is also the same failure as naming a town that was never named — the model filling a gap with something plausible.

**No prompt instruction can fix a homophone**, so this is not a wording problem and should not be attacked as one. The fix is to stop transcribing what we already know: the senior's name, birthplace and family names belong in their profile as seed facts, and the interviewer should be given them rather than inferring them from audio. `seniors/{id}` in [plan.md](plan.md#data-model-sketch) already carries them.

Slice 3 introduced that profile and the fix is now in: `brain.context_for` puts the name, its reading, the birth year and the birthplace into the prompt, and the interviewer is told to use that spelling. Recordings made before this may still carry the wrong characters.

The profile only covers the people it lists — the senior, and the family members entered with them. Everyone else arrives through audio alone: the first boss, the neighbour, the schoolteacher, the friend who moved away. Those names have the same homophone problem and nothing to check them against, and they are most of the names a life story contains.

Three things could help, none of them yet built:

- **Do not assert a spelling we do not have.** A name heard once could be stored in kana, as it was heard, rather than in kanji the model chose. An honest 「しげるさん」 is better than a confident, wrong 佐藤繁.
- **Let the family correct them.** Relatives know how their grandfather's friend's name is written. This fits the family loop already planned for slice 6 — a name the senior cannot easily spell out is exactly the kind of thing a family member can fix in one tap, and it turns a defect into a reason for them to open the page.
- **Confirm in conversation, carefully.** The prompt already asks the interviewer to check names lightly, but confirming a *sound* does not settle a *spelling*, and asking an eighty-year-old which characters they mean is not a warm question. This is the weakest of the three.

What remains unproven is whether the model reliably uses the spelling it is handed. It did in one run and greeted with the wrong-name-free 「田中ハルさん」; in another it greeted without using the name at all. Being given a fact is not the same as honouring it, and that needs measuring over several runs rather than asserting.

### The harness was only testing the first exchange

Worth recording, because every conversational figure reported before this was wrong.

`session.receive()` completes at the end of a turn rather than running for the life of the session. The listener task therefore exited after one turn and stopped forwarding audio, so each side answered exactly once and the conversation stopped dead at two turns. Re-entering `receive()` in a loop fixes it: the same 130 second run went from 2 turns to 9.

Two smaller faults fell out of the same investigation. The interviewee was seeded with `send_client_content`, and mixing that with realtime audio left its turn state such that it never spoke again — it is now started with a synthesized hello played to the interviewer, so both sides only ever see audio. And the hesitancy instruction was being given to every persona, which made their turns so long that no conversation reached a second exchange; it now belongs only to the persona whose test is about patience.

## Open questions

Tracked in [plan.md](plan.md#open-questions-and-risks).

Model choice is settled: **`gemini-3.8-live`** (GA) for voice, `gemini-3.8-flash` for the extraction and planning passes. The remaining question that gates slice 1 is empirical — does it handle elderly Japanese speech well, and does it hold the language steady across a long pause?
