"""Japanese speech for the eval fixtures.

Synthesised speech is clean and evenly paced, so it proves the pipeline and
catches regressions — it cannot tell you the model copes with an elderly voice.
Drop a real recording in `recordings/` and reference it by name for that; the
runner treats both the same way.
"""

import hashlib
import shutil
import subprocess
from pathlib import Path

CACHE = Path(__file__).parent / ".audio-cache"
RECORDINGS = Path(__file__).parent / "recordings"
RATE = 16000


def available() -> bool:
    return shutil.which("say") is not None and shutil.which("afconvert") is not None


def synthesize(text: str, voice: str = "Kyoko") -> bytes:
    """Raw 16-bit PCM at 16 kHz, cached so repeated runs cost nothing."""
    key = hashlib.sha256(f"{voice}:{text}".encode()).hexdigest()[:16]
    cached = CACHE / f"{key}.pcm"
    if cached.exists():
        return cached.read_bytes()

    CACHE.mkdir(exist_ok=True)
    source = CACHE / f"{key}.txt"
    aiff = CACHE / f"{key}.aiff"
    wav = CACHE / f"{key}.wav"
    source.write_text(text, encoding="utf-8")

    subprocess.run(
        ["say", "-v", voice, "-f", str(source), "-o", str(aiff)], check=True, capture_output=True
    )
    subprocess.run(
        ["afconvert", "-f", "WAVE", "-d", f"LEI16@{RATE}", "-c", "1", str(aiff), str(wav)],
        check=True,
        capture_output=True,
    )

    pcm = _pcm_from_wav(wav)
    cached.write_bytes(pcm)
    for leftover in (source, aiff, wav):
        leftover.unlink(missing_ok=True)
    return pcm


def recorded(name: str) -> bytes:
    """PCM from a real session recording kept under `recordings/`."""
    path = RECORDINGS / name
    if not path.exists():
        raise FileNotFoundError(f"No recording at {path}")
    return _pcm_from_wav(path)


def _pcm_from_wav(path: Path) -> bytes:
    import wave

    with wave.open(str(path)) as handle:
        if handle.getframerate() != RATE or handle.getnchannels() != 1:
            raise ValueError(
                f"{path.name} must be {RATE} Hz mono, "
                f"got {handle.getframerate()} Hz {handle.getnchannels()}ch"
            )
        return handle.readframes(handle.getnframes())
