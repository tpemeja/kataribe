"""Session storage: SQLite for the records, plain files for the audio.

This module is the seam. Moving to Firestore and Cloud Storage means rewriting
what is here and nothing above it.
"""

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id                        TEXT PRIMARY KEY,
    started_at                TEXT NOT NULL,
    ended_at                  TEXT,
    model                     TEXT NOT NULL,
    voice                     TEXT NOT NULL,
    silence_duration_ms       INTEGER NOT NULL,
    end_of_speech_sensitivity TEXT NOT NULL,
    input_label               TEXT NOT NULL DEFAULT 'microphone',
    duration_seconds          REAL,
    transcript                TEXT
);
"""


@dataclass(frozen=True)
class Turn:
    speaker: str
    text: str
    started_at: float


@dataclass(frozen=True)
class Session:
    id: str
    started_at: datetime
    ended_at: datetime | None
    model: str
    voice: str
    silence_duration_ms: int
    end_of_speech_sensitivity: str
    input_label: str
    duration_seconds: float | None
    turns: list[Turn]

    @property
    def has_audio(self) -> bool:
        return self.duration_seconds is not None


class Store:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.recordings = data_dir / "recordings"
        self.recordings.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.executescript(SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.data_dir / "kataribe.db")
        db.row_factory = sqlite3.Row
        return db

    def start(
        self,
        *,
        model: str,
        voice: str,
        silence_duration_ms: int,
        end_of_speech_sensitivity: str,
    ) -> str:
        session_id = uuid.uuid4().hex[:12]
        with self._connect() as db:
            db.execute(
                "INSERT INTO sessions (id, started_at, model, voice, silence_duration_ms,"
                " end_of_speech_sensitivity) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    session_id,
                    datetime.now(UTC).isoformat(),
                    model,
                    voice,
                    silence_duration_ms,
                    end_of_speech_sensitivity,
                ),
            )
        return session_id

    def finish(
        self,
        session_id: str,
        *,
        turns: list[Turn],
        audio: bytes | None,
        duration_seconds: float,
        input_label: str,
    ) -> None:
        if audio:
            (self.recordings / f"{session_id}.wav").write_bytes(audio)
        with self._connect() as db:
            db.execute(
                "UPDATE sessions SET ended_at = ?, duration_seconds = ?, transcript = ?,"
                " input_label = ? WHERE id = ?",
                (
                    datetime.now(UTC).isoformat(),
                    duration_seconds,
                    json.dumps([turn.__dict__ for turn in turns], ensure_ascii=False),
                    input_label,
                    session_id,
                ),
            )

    def list(self, limit: int = 100) -> list[Session]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM sessions ORDER BY started_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [_to_session(row) for row in rows]

    def get(self, session_id: str) -> Session | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        return _to_session(row) if row else None

    def audio_path(self, session_id: str) -> Path | None:
        path = self.recordings / f"{session_id}.wav"
        return path if path.exists() else None


def _to_session(row: sqlite3.Row) -> Session:
    return Session(
        id=row["id"],
        started_at=datetime.fromisoformat(row["started_at"]),
        ended_at=datetime.fromisoformat(row["ended_at"]) if row["ended_at"] else None,
        model=row["model"],
        voice=row["voice"],
        silence_duration_ms=row["silence_duration_ms"],
        end_of_speech_sensitivity=row["end_of_speech_sensitivity"],
        input_label=row["input_label"],
        duration_seconds=row["duration_seconds"],
        turns=[Turn(**turn) for turn in json.loads(row["transcript"] or "[]")],
    )
