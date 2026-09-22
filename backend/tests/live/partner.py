"""Runs the interviewer against a simulated interviewee, both on live audio.

Two Live sessions face each other and each one's voice is carried to the other
at real time, because the API drops a session that receives audio faster than
it could have been spoken. Silence is carried too, exactly as an open
microphone would — which is what makes the interviewer's patience testable.
"""

import array
import asyncio
import time
import wave
from dataclasses import dataclass, field
from pathlib import Path

from google.genai import types

from kataribe.config import Settings
from kataribe.gemini import InterviewTuning, mint_session_credentials
from tests.live.connection import live_client
from tests.live.personas import Persona

SEND_RATE = 16000
MODEL_RATE = 24000
FRAME_BYTES = 2048  # 1024 samples, 64ms


def _downsample(pcm: bytes) -> bytes:
    """24 kHz to 16 kHz. Three samples in, two out."""
    src = array.array("h")
    src.frombytes(pcm)
    count = len(src) * 2 // 3
    out = array.array("h", bytes(2 * count))
    for i in range(count):
        position = i * 1.5
        left = int(position)
        right = min(left + 1, len(src) - 1)
        weight = position - left
        out[i] = int(src[left] * (1 - weight) + src[right] * weight)
    return out.tobytes()


class Wire:
    """Carries one speaker's voice to the other, padding with silence."""

    def __init__(self) -> None:
        self._ready = bytearray()
        self._raw = bytearray()
        self.emitted = bytearray()
        self.intervals: list[tuple[float, float]] = []
        self._since: float | None = None

    def push(self, pcm: bytes) -> None:
        self._raw += pcm
        usable = len(self._raw) // 6 * 6
        if usable:
            self._ready += _downsample(bytes(self._raw[:usable]))
            del self._raw[:usable]

    def take(self, size: int, now: float) -> bytes:
        speaking = len(self._ready) > 0
        if len(self._ready) >= size:
            chunk = bytes(self._ready[:size])
            del self._ready[:size]
        else:
            chunk = bytes(self._ready) + b"\x00" * (size - len(self._ready))
            self._ready.clear()

        if speaking and self._since is None:
            self._since = now
        elif not speaking and self._since is not None:
            self.intervals.append((self._since, now))
            self._since = None

        self.emitted += chunk
        return chunk

    def close(self, now: float) -> None:
        if self._since is not None:
            self.intervals.append((self._since, now))
            self._since = None


@dataclass
class Exchange:
    persona: Persona
    senior_said: str = ""
    interviewer_said: str = ""
    senior_intervals: list[tuple[float, float]] = field(default_factory=list)
    interviewer_intervals: list[tuple[float, float]] = field(default_factory=list)
    senior_audio: bytes = b""
    interviewer_audio: bytes = b""
    error: str | None = None
    # A socket can still close for reasons outside our control. Once real
    # conversation has happened that is an ending, not a fault, so it is kept
    # apart from `error` and the transcript stays usable.
    ended: str | None = None

    @property
    def spoke(self) -> bool:
        return bool(self.senior_said and self.interviewer_said)

    def overlaps(self, gap: float = 0.25) -> list[tuple[float, float]]:
        """Moments the interviewer was talking while the interviewee still was."""
        found = []
        for start, end in self.interviewer_intervals:
            for other_start, other_end in self.senior_intervals:
                overlap = min(end, other_end) - max(start, other_start)
                if overlap > gap:
                    found.append((max(start, other_start), overlap))
        return found

    def save(self, path: Path) -> None:
        """Stereo: interviewee left, interviewer right, as the downloads are."""
        frames = min(len(self.senior_audio), len(self.interviewer_audio)) // 2
        left = array.array("h")
        left.frombytes(self.senior_audio[: frames * 2])
        right = array.array("h")
        right.frombytes(self.interviewer_audio[: frames * 2])

        mixed = array.array("h", bytes(4 * frames))
        for i in range(frames):
            mixed[2 * i] = left[i]
            mixed[2 * i + 1] = right[i]

        path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(path), "wb") as handle:
            handle.setnchannels(2)
            handle.setsampwidth(2)
            handle.setframerate(SEND_RATE)
            handle.writeframes(mixed.tobytes())


def _persona_config(persona: Persona) -> types.LiveConnectConfig:
    return types.LiveConnectConfig(
        response_modalities=[types.Modality.AUDIO],
        system_instruction=persona.instruction,
        speech_config=types.SpeechConfig(
            language_code="ja-JP",
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Gacrux")
            ),
        ),
        output_audio_transcription=types.AudioTranscriptionConfig(),
    )


async def converse(
    persona: Persona,
    settings: Settings,
    seconds: float = 60.0,
    tuning: InterviewTuning | None = None,
) -> Exchange:
    credentials = mint_session_credentials(settings, tuning or InterviewTuning())
    interviewer_client = live_client(
        api_key=credentials.token, http_options={"api_version": "v1alpha"}
    )
    senior_client = live_client(api_key=settings.gemini_api_key)

    result = Exchange(persona=persona)
    to_interviewer, to_senior = Wire(), Wire()

    async with (
        interviewer_client.aio.live.connect(
            model=credentials.model, config=types.LiveConnectConfig()
        ) as interviewer,
        senior_client.aio.live.connect(
            model=settings.live_model, config=_persona_config(persona)
        ) as senior,
    ):
        started = time.monotonic()

        async def pump(wire: Wire, session: object) -> None:
            while True:
                now = time.monotonic() - started
                await session.send_realtime_input(  # type: ignore[attr-defined]
                    audio=types.Blob(
                        data=wire.take(FRAME_BYTES, now),
                        mime_type=f"audio/pcm;rate={SEND_RATE}",
                    )
                )
                await asyncio.sleep(FRAME_BYTES / 2 / SEND_RATE)

        async def listen(session: object, into: Wire, side: str) -> None:
            async for message in session.receive():  # type: ignore[attr-defined]
                content = message.server_content
                if content is None:
                    continue
                if content.output_transcription and content.output_transcription.text:
                    text = content.output_transcription.text
                    if side == "senior":
                        result.senior_said += text
                    else:
                        result.interviewer_said += text
                for part in (content.model_turn.parts or []) if content.model_turn else []:
                    if part.inline_data and part.inline_data.data:
                        into.push(part.inline_data.data)

        # The interviewer cannot be nudged with text — its session runs on a
        # constrained token, which rejects client content. The interviewee opens
        # instead, as someone sitting down and saying hello would.
        await senior.send_client_content(
            turns=[{"role": "user", "parts": [{"text": "こんにちは。お話を聞かせてください。"}]}],
            turn_complete=True,
        )

        async def guard(label: str, work: object) -> None:
            try:
                await work  # type: ignore[misc]
            except asyncio.CancelledError:
                raise
            except Exception as error:  # noqa: BLE001
                at = time.monotonic() - started
                note = f"{label} stopped at {at:.0f}s — {type(error).__name__}: {error}"
                if result.spoke:
                    result.ended = result.ended or note
                elif result.error is None:
                    result.error = note

        tasks = [
            asyncio.create_task(guard("sending to interviewer", pump(to_interviewer, interviewer))),
            asyncio.create_task(guard("sending to interviewee", pump(to_senior, senior))),
            asyncio.create_task(guard("interviewee", listen(senior, to_interviewer, "senior"))),
            asyncio.create_task(
                guard("interviewer", listen(interviewer, to_senior, "interviewer"))
            ),
        ]
        try:
            for _ in range(int(seconds * 10)):
                await asyncio.sleep(0.1)
                if result.error or result.ended:
                    break
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            ended = time.monotonic() - started
            to_interviewer.close(ended)
            to_senior.close(ended)

    result.senior_intervals = to_interviewer.intervals
    result.interviewer_intervals = to_senior.intervals
    result.senior_audio = bytes(to_interviewer.emitted)
    result.interviewer_audio = bytes(to_senior.emitted)
    return result
