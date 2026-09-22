"""Plays a scripted Japanese conversation at the real Live API and records what happened.

Audio is streamed in real time through the same ephemeral-token path the browser
uses, so a config that only fails on a real socket fails here too.
"""

import asyncio
import contextlib
import time
from dataclasses import dataclass, field

from google.genai import types

from kataribe.config import Settings
from kataribe.gemini import InterviewTuning, mint_session_credentials
from tests.live import speech
from tests.live.connection import live_client

FRAME_BYTES = 2048  # 1024 samples, matching the browser's worklet
RATE = speech.RATE


@dataclass(frozen=True)
class Speech:
    text: str
    voice: str = "Kyoko"


@dataclass(frozen=True)
class Silence:
    seconds: float


Beat = Speech | Silence


@dataclass
class Reply:
    started_at: float
    text: str = ""


@dataclass
class Conversation:
    script_seconds: float
    heard: str = ""
    replies: list[Reply] = field(default_factory=list)
    audio_bytes: int = 0
    closed: str | None = None

    @property
    def spoken(self) -> str:
        return " ".join(r.text for r in self.replies).strip()

    @property
    def first_reply_at(self) -> float | None:
        return self.replies[0].started_at if self.replies else None

    @property
    def interrupted(self) -> bool:
        """True if the interviewer started talking before the senior had finished."""
        return self.first_reply_at is not None and self.first_reply_at < self.script_seconds


async def run(
    script: list[Beat],
    settings: Settings,
    tuning: InterviewTuning | None = None,
    tail_seconds: float | None = None,
) -> Conversation:
    tuning = tuning or InterviewTuning()
    # The model needs its full patience in silence before it accepts the turn has
    # ended, and then a moment to answer, so the tail has to outlast the setting.
    if tail_seconds is None:
        tail_seconds = tuning.silence_duration_ms / 1000 + 8
    credentials = mint_session_credentials(settings, tuning)
    client = live_client(api_key=credentials.token, http_options={"api_version": "v1alpha"})

    # Audio is paced in real time, so the script's duration is also its wall clock.
    result = Conversation(script_seconds=_budget(script))

    async with client.aio.live.connect(
        model=credentials.model, config=types.LiveConnectConfig()
    ) as session:
        started = time.monotonic()

        async def feed() -> None:
            try:
                for beat in script:
                    audio = (
                        speech.synthesize(beat.text, beat.voice)
                        if isinstance(beat, Speech)
                        else b"\x00" * (int(beat.seconds * RATE) * 2)
                    )
                    await _stream(session, audio)
                await _stream(session, b"\x00" * (int(tail_seconds * RATE) * 2))
            except asyncio.CancelledError:
                raise
            except Exception as error:  # noqa: BLE001
                result.closed = result.closed or f"while sending: {type(error).__name__}: {error}"

        feeder = asyncio.create_task(feed())
        speaking = False

        try:
            async with asyncio.timeout(result.script_seconds + tail_seconds + 10):
                async for message in session.receive():
                    content = message.server_content
                    if content is None:
                        continue

                    if content.input_transcription and content.input_transcription.text:
                        result.heard += content.input_transcription.text

                    if content.output_transcription and content.output_transcription.text:
                        if not speaking:
                            result.replies.append(Reply(started_at=time.monotonic() - started))
                            speaking = True
                        result.replies[-1].text += content.output_transcription.text

                    for part in (content.model_turn.parts or []) if content.model_turn else []:
                        if part.inline_data and part.inline_data.data:
                            result.audio_bytes += len(part.inline_data.data)

                    if content.turn_complete:
                        speaking = False
        except TimeoutError:
            pass
        except Exception as error:  # noqa: BLE001
            result.closed = f"{type(error).__name__}: {error}"
        finally:
            feeder.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await feeder

    return result


async def _stream(session: object, pcm: bytes) -> None:
    for offset in range(0, len(pcm) - FRAME_BYTES, FRAME_BYTES):
        await session.send_realtime_input(  # type: ignore[attr-defined]
            audio=types.Blob(
                data=pcm[offset : offset + FRAME_BYTES], mime_type=f"audio/pcm;rate={RATE}"
            )
        )
        await asyncio.sleep(FRAME_BYTES / 2 / RATE)


def _budget(script: list[Beat]) -> float:
    return sum(
        beat.seconds
        if isinstance(beat, Silence)
        else len(speech.synthesize(beat.text, beat.voice)) / 2 / RATE
        for beat in script
    )
