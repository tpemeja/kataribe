import datetime
import json
from functools import lru_cache
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from kataribe.config import Settings, get_settings
from kataribe.gemini import VOICES, InterviewTuning, mint_session_credentials
from kataribe.store import Store, Turn

router = APIRouter(prefix="/api", tags=["sessions"])


@lru_cache
def _store(data_dir: str) -> Store:
    from pathlib import Path

    return Store(Path(data_dir))


def get_store(settings: Annotated[Settings, Depends(get_settings)]) -> Store:
    return _store(str(settings.data_dir))


class SessionRequest(BaseModel):
    voice: str = "Sulafat"
    silence_duration_ms: int = Field(default=5000, ge=200, le=8000)
    end_of_speech_sensitivity: Literal["LOW", "HIGH"] = "LOW"


class SessionResponse(BaseModel):
    session_id: str
    token: str
    model: str
    expires_at: datetime.datetime
    voice: str
    silence_duration_ms: int


class TurnView(BaseModel):
    speaker: str
    text: str
    started_at: float


class SessionSummary(BaseModel):
    id: str
    started_at: datetime.datetime
    duration_seconds: float | None
    voice: str
    silence_duration_ms: int
    input_label: str
    turns: int
    has_audio: bool


class SessionDetail(SessionSummary):
    model: str
    end_of_speech_sensitivity: str
    transcript: list[TurnView]


@router.get("/voices")
def list_voices() -> dict[str, str]:
    return VOICES


@router.post("/sessions")
def create_session(
    request: SessionRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    store: Annotated[Store, Depends(get_store)],
) -> SessionResponse:
    if not settings.gemini_api_key:
        raise HTTPException(status_code=503, detail="KATARIBE_GEMINI_API_KEY is not configured")
    if request.voice not in VOICES:
        raise HTTPException(status_code=422, detail=f"Unknown voice: {request.voice}")

    tuning = InterviewTuning(
        voice=request.voice,
        silence_duration_ms=request.silence_duration_ms,
        end_of_speech_sensitivity=request.end_of_speech_sensitivity,
    )
    credentials = mint_session_credentials(settings, tuning)
    session_id = store.start(
        model=credentials.model,
        voice=tuning.voice,
        silence_duration_ms=tuning.silence_duration_ms,
        end_of_speech_sensitivity=tuning.end_of_speech_sensitivity,
    )

    return SessionResponse(
        session_id=session_id,
        token=credentials.token,
        model=credentials.model,
        expires_at=credentials.expires_at,
        voice=tuning.voice,
        silence_duration_ms=tuning.silence_duration_ms,
    )


@router.post("/sessions/{session_id}/recording", status_code=204)
async def upload_recording(
    session_id: str,
    store: Annotated[Store, Depends(get_store)],
    transcript: Annotated[str, Form()],
    duration_seconds: Annotated[float, Form()],
    input_label: Annotated[str, Form()] = "microphone",
    audio: Annotated[UploadFile | None, File()] = None,
) -> None:
    if store.get(session_id) is None:
        raise HTTPException(status_code=404, detail=f"No session {session_id}")

    try:
        turns = [Turn(**turn) for turn in json.loads(transcript)]
    except (TypeError, ValueError) as error:
        raise HTTPException(status_code=422, detail=f"Bad transcript: {error}") from error

    store.finish(
        session_id,
        turns=turns,
        audio=await audio.read() if audio else None,
        duration_seconds=duration_seconds,
        input_label=input_label,
    )


@router.get("/sessions")
def list_sessions(store: Annotated[Store, Depends(get_store)]) -> list[SessionSummary]:
    return [
        SessionSummary(
            id=session.id,
            started_at=session.started_at,
            duration_seconds=session.duration_seconds,
            voice=session.voice,
            silence_duration_ms=session.silence_duration_ms,
            input_label=session.input_label,
            turns=len(session.turns),
            has_audio=store.audio_path(session.id) is not None,
        )
        for session in store.list()
    ]


@router.get("/sessions/{session_id}")
def read_session(session_id: str, store: Annotated[Store, Depends(get_store)]) -> SessionDetail:
    session = store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"No session {session_id}")
    return SessionDetail(
        id=session.id,
        started_at=session.started_at,
        duration_seconds=session.duration_seconds,
        voice=session.voice,
        silence_duration_ms=session.silence_duration_ms,
        input_label=session.input_label,
        turns=len(session.turns),
        has_audio=store.audio_path(session.id) is not None,
        model=session.model,
        end_of_speech_sensitivity=session.end_of_speech_sensitivity,
        transcript=[TurnView(**turn.__dict__) for turn in session.turns],
    )


@router.get("/sessions/{session_id}/audio")
def read_audio(session_id: str, store: Annotated[Store, Depends(get_store)]) -> FileResponse:
    path = store.audio_path(session_id)
    if path is None:
        raise HTTPException(status_code=404, detail=f"No recording for {session_id}")
    return FileResponse(path, media_type="audio/wav", filename=f"kataribe-{session_id}.wav")
