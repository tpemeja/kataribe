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
CREATE TABLE IF NOT EXISTS seniors (
    id           TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    name_reading TEXT NOT NULL DEFAULT '',
    birth_year   INTEGER,
    birthplace   TEXT NOT NULL DEFAULT '',
    family       TEXT NOT NULL DEFAULT '[]',
    created_at   TEXT NOT NULL
);

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

CREATE TABLE IF NOT EXISTS stories (
    id            TEXT PRIMARY KEY,
    senior_id     TEXT NOT NULL,
    session_id    TEXT NOT NULL,
    title         TEXT NOT NULL,
    summary       TEXT NOT NULL,
    life_stage    TEXT NOT NULL,
    approx_period TEXT NOT NULL DEFAULT '',
    people        TEXT NOT NULL DEFAULT '[]',
    places        TEXT NOT NULL DEFAULT '[]',
    quotes        TEXT NOT NULL DEFAULT '[]',
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS plans (
    senior_id      TEXT PRIMARY KEY,
    story_so_far   TEXT NOT NULL DEFAULT '',
    next_questions TEXT NOT NULL DEFAULT '[]',
    avoid_topics   TEXT NOT NULL DEFAULT '[]',
    updated_at     TEXT NOT NULL
);
"""

# Added after the first sessions were recorded, so they arrive by migration.
LATER_COLUMNS = {
    "seniors": {"language": "TEXT NOT NULL DEFAULT 'ja'"},
    "sessions": {
        "senior_id": "TEXT",
        "status": "TEXT NOT NULL DEFAULT 'recorded'",
        "processing_error": "TEXT",
    },
}

LIFE_STAGES = ("子供時代", "学校", "仕事", "結婚", "子育て", "晩年")


@dataclass(frozen=True)
class Turn:
    speaker: str
    text: str
    started_at: float


@dataclass(frozen=True)
class Quote:
    text: str
    turn: int


@dataclass(frozen=True)
class Story:
    id: str
    senior_id: str
    session_id: str
    title: str
    summary: str
    life_stage: str
    approx_period: str
    people: list[str]
    places: list[str]
    quotes: list[Quote]


@dataclass(frozen=True)
class Senior:
    id: str
    name: str
    name_reading: str
    birth_year: int | None
    birthplace: str
    family: list[str]
    language: str = "ja"


@dataclass(frozen=True)
class Plan:
    story_so_far: str
    next_questions: list[str]
    avoid_topics: list[str]

    @property
    def is_empty(self) -> bool:
        return not (self.story_so_far or self.next_questions)


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
    senior_id: str | None = None
    status: str = "recorded"
    processing_error: str | None = None


class Store:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.recordings = data_dir / "recordings"
        self.recordings.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.executescript(SCHEMA)
            for table, columns in LATER_COLUMNS.items():
                present = {row["name"] for row in db.execute(f"PRAGMA table_info({table})")}
                for column, spec in columns.items():
                    if column not in present:
                        db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {spec}")

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.data_dir / "kataribe.db")
        db.row_factory = sqlite3.Row
        return db

    # --- seniors -------------------------------------------------------

    def add_senior(
        self,
        *,
        name: str,
        name_reading: str = "",
        birth_year: int | None = None,
        birthplace: str = "",
        family: list[str] | None = None,
        language: str = "ja",
    ) -> str:
        senior_id = uuid.uuid4().hex[:12]
        with self._connect() as db:
            db.execute(
                "INSERT INTO seniors (id, name, name_reading, birth_year, birthplace, family,"
                " language, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    senior_id,
                    name,
                    name_reading,
                    birth_year,
                    birthplace,
                    json.dumps(family or [], ensure_ascii=False),
                    language,
                    datetime.now(UTC).isoformat(),
                ),
            )
        return senior_id

    def get_senior(self, senior_id: str) -> Senior | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM seniors WHERE id = ?", (senior_id,)).fetchone()
        if row is None:
            return None
        # `in` on a Row searches values, so the column list is taken explicitly.
        columns = row.keys()
        return Senior(
            id=row["id"],
            name=row["name"],
            name_reading=row["name_reading"],
            birth_year=row["birth_year"],
            birthplace=row["birthplace"],
            family=json.loads(row["family"]),
            language=row["language"] if "language" in columns else "ja",
        )

    def list_seniors(self) -> list[Senior]:
        with self._connect() as db:
            rows = db.execute("SELECT id FROM seniors ORDER BY created_at").fetchall()
        return [s for s in (self.get_senior(row["id"]) for row in rows) if s]

    # --- sessions ------------------------------------------------------

    def start(
        self,
        *,
        model: str,
        voice: str,
        silence_duration_ms: int,
        end_of_speech_sensitivity: str,
        senior_id: str | None = None,
    ) -> str:
        session_id = uuid.uuid4().hex[:12]
        with self._connect() as db:
            db.execute(
                "INSERT INTO sessions (id, started_at, model, voice, silence_duration_ms,"
                " end_of_speech_sensitivity, senior_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    session_id,
                    datetime.now(UTC).isoformat(),
                    model,
                    voice,
                    silence_duration_ms,
                    end_of_speech_sensitivity,
                    senior_id,
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

    def set_status(self, session_id: str, status: str, error: str | None = None) -> None:
        with self._connect() as db:
            db.execute(
                "UPDATE sessions SET status = ?, processing_error = ? WHERE id = ?",
                (status, error, session_id),
            )

    def list_sessions(self, limit: int = 100) -> list[Session]:
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

    # --- stories and plans ---------------------------------------------

    def replace_stories(self, session_id: str, senior_id: str, stories: list[Story]) -> None:
        """A session's stories are rewritten wholesale, so re-processing is safe."""
        with self._connect() as db:
            db.execute("DELETE FROM stories WHERE session_id = ?", (session_id,))
            db.executemany(
                "INSERT INTO stories (id, senior_id, session_id, title, summary, life_stage,"
                " approx_period, people, places, quotes, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        story.id,
                        senior_id,
                        session_id,
                        story.title,
                        story.summary,
                        story.life_stage,
                        story.approx_period,
                        json.dumps(story.people, ensure_ascii=False),
                        json.dumps(story.places, ensure_ascii=False),
                        json.dumps([q.__dict__ for q in story.quotes], ensure_ascii=False),
                        datetime.now(UTC).isoformat(),
                    )
                    for story in stories
                ],
            )

    def stories_for_session(self, session_id: str) -> list[Story]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM stories WHERE session_id = ? ORDER BY created_at", (session_id,)
            ).fetchall()
        return [_to_story(row) for row in rows]

    def stories_for_senior(self, senior_id: str) -> list[Story]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM stories WHERE senior_id = ? ORDER BY created_at", (senior_id,)
            ).fetchall()
        return [_to_story(row) for row in rows]

    def save_plan(self, senior_id: str, plan: Plan) -> None:
        with self._connect() as db:
            db.execute(
                "INSERT INTO plans (senior_id, story_so_far, next_questions, avoid_topics,"
                " updated_at) VALUES (?, ?, ?, ?, ?) ON CONFLICT(senior_id) DO UPDATE SET"
                " story_so_far = excluded.story_so_far,"
                " next_questions = excluded.next_questions,"
                " avoid_topics = excluded.avoid_topics,"
                " updated_at = excluded.updated_at",
                (
                    senior_id,
                    plan.story_so_far,
                    json.dumps(plan.next_questions, ensure_ascii=False),
                    json.dumps(plan.avoid_topics, ensure_ascii=False),
                    datetime.now(UTC).isoformat(),
                ),
            )

    def get_plan(self, senior_id: str) -> Plan:
        with self._connect() as db:
            row = db.execute("SELECT * FROM plans WHERE senior_id = ?", (senior_id,)).fetchone()
        if row is None:
            return Plan(story_so_far="", next_questions=[], avoid_topics=[])
        return Plan(
            story_so_far=row["story_so_far"],
            next_questions=json.loads(row["next_questions"]),
            avoid_topics=json.loads(row["avoid_topics"]),
        )


def _to_session(row: sqlite3.Row) -> Session:
    keys = row.keys()
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
        senior_id=row["senior_id"] if "senior_id" in keys else None,
        status=(row["status"] if "status" in keys else None) or "recorded",
        processing_error=row["processing_error"] if "processing_error" in keys else None,
    )


def _to_story(row: sqlite3.Row) -> Story:
    return Story(
        id=row["id"],
        senior_id=row["senior_id"],
        session_id=row["session_id"],
        title=row["title"],
        summary=row["summary"],
        life_stage=row["life_stage"],
        approx_period=row["approx_period"],
        people=json.loads(row["people"]),
        places=json.loads(row["places"]),
        quotes=[Quote(**q) for q in json.loads(row["quotes"])],
    )


__all__ = [
    "LIFE_STAGES",
    "Plan",
    "Quote",
    "Senior",
    "Session",
    "Store",
    "Story",
    "Turn",
]
