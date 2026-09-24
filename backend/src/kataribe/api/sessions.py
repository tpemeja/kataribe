import datetime
import json
from functools import lru_cache
from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from kataribe import brain
from kataribe.config import Settings, get_settings
from kataribe.gemini import VOICES, InterviewTuning, mint_session_credentials
from kataribe.languages import LANGUAGES, get
from kataribe.processing import process_session
from kataribe.store import Store, Turn

router = APIRouter(prefix="/api", tags=["sessions"])


@lru_cache
def _store(data_dir: str) -> Store:
    from pathlib import Path

    return Store(Path(data_dir))


def get_store(settings: Annotated[Settings, Depends(get_settings)]) -> Store:
    return _store(str(settings.data_dir))


class LanguageView(BaseModel):
    code: str
    label: str
    endonym: str
    voice: str
    silence_duration_ms: int
    measured: bool


class SeniorRequest(BaseModel):
    name: str
    name_reading: str = ""
    birth_year: int | None = None
    birthplace: str = ""
    family: list[str] = Field(default_factory=list)
    language: str = "ja"


class SeniorView(SeniorRequest):
    id: str


class QuoteView(BaseModel):
    text: str
    turn: int


class StoryView(BaseModel):
    id: str
    title: str
    summary: str
    life_stage: str
    approx_period: str
    people: list[str]
    places: list[str]
    quotes: list[QuoteView]


class PlanView(BaseModel):
    story_so_far: str
    next_questions: list[str]
    avoid_topics: list[str]


class SessionRequest(BaseModel):
    """Unset tuning falls back to the language's own defaults, so a value found
    while testing in French never becomes the one a Japanese speaker gets."""

    senior_id: str | None = None
    voice: str | None = None
    silence_duration_ms: int | None = Field(default=None, ge=200, le=8000)
    end_of_speech_sensitivity: Literal["LOW", "HIGH"] = "LOW"


class SessionResponse(BaseModel):
    session_id: str
    senior_id: str | None = None
    resuming: bool = False
    token: str
    model: str
    expires_at: datetime.datetime
    voice: str
    silence_duration_ms: int
    language: str
    opening: str


class TurnView(BaseModel):
    speaker: str
    text: str
    started_at: float


class SessionSummary(BaseModel):
    id: str
    status: str
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
    stories: list[StoryView]
    processing_error: str | None = None


@router.get("/voices")
def list_voices() -> dict[str, str]:
    return VOICES


@router.get("/languages")
def list_languages() -> list[LanguageView]:
    return [LanguageView(**language.__dict__) for language in LANGUAGES.values()]


@router.get("/seniors")
def list_seniors(store: Annotated[Store, Depends(get_store)]) -> list[SeniorView]:
    return [SeniorView(**senior.__dict__) for senior in store.list_seniors()]


@router.post("/seniors")
def add_senior(request: SeniorRequest, store: Annotated[Store, Depends(get_store)]) -> SeniorView:
    senior_id = store.add_senior(**request.model_dump())
    return SeniorView(id=senior_id, **request.model_dump())


@router.get("/seniors/{senior_id}/plan")
def read_plan(senior_id: str, store: Annotated[Store, Depends(get_store)]) -> PlanView:
    if store.get_senior(senior_id) is None:
        raise HTTPException(status_code=404, detail=f"No senior {senior_id}")
    return PlanView(**store.get_plan(senior_id).__dict__)


@router.post("/sessions")
def create_session(
    request: SessionRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    store: Annotated[Store, Depends(get_store)],
) -> SessionResponse:
    if not settings.gemini_api_key:
        raise HTTPException(status_code=503, detail="KATARIBE_GEMINI_API_KEY is not configured")
    if request.voice is not None and request.voice not in VOICES:
        raise HTTPException(status_code=422, detail=f"Unknown voice: {request.voice}")

    # What the interviewer already knows about this person, and what it meant to
    # ask today. Locked into the token with everything else.
    context = ""
    plan = None
    senior = None
    if request.senior_id:
        senior = store.get_senior(request.senior_id)
        if senior is None:
            raise HTTPException(status_code=404, detail=f"No senior {request.senior_id}")
        plan = store.get_plan(senior.id)
        context = brain.context_for(senior, plan)

    # The person's language decides the prompt, the locale and the defaults.
    base = InterviewTuning.for_language(senior.language if senior else None)
    tuning = InterviewTuning(
        voice=request.voice or base.voice,
        silence_duration_ms=request.silence_duration_ms or base.silence_duration_ms,
        end_of_speech_sensitivity=request.end_of_speech_sensitivity,
        language=base.language,
    )

    credentials = mint_session_credentials(settings, tuning, context)
    session_id = store.start(
        model=credentials.model,
        voice=tuning.voice,
        silence_duration_ms=tuning.silence_duration_ms,
        end_of_speech_sensitivity=tuning.end_of_speech_sensitivity,
        senior_id=request.senior_id,
    )

    return SessionResponse(
        session_id=session_id,
        senior_id=request.senior_id,
        resuming=bool(plan and not plan.is_empty),
        token=credentials.token,
        model=credentials.model,
        expires_at=credentials.expires_at,
        voice=tuning.voice,
        silence_duration_ms=tuning.silence_duration_ms,
        language=tuning.language,
        opening=get(tuning.language).opening,
    )


@router.post("/sessions/{session_id}/recording", status_code=204)
async def upload_recording(
    session_id: str,
    background: BackgroundTasks,
    settings: Annotated[Settings, Depends(get_settings)],
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
    # Extraction takes seconds and can fail. Neither should cost the upload,
    # which until now held the only copy of the recording.
    store.set_status(session_id, "queued")
    background.add_task(process_session, settings, store, session_id)


@router.get("/sessions")
def list_sessions(store: Annotated[Store, Depends(get_store)]) -> list[SessionSummary]:
    return [
        SessionSummary(
            id=session.id,
            status=session.status,
            started_at=session.started_at,
            duration_seconds=session.duration_seconds,
            voice=session.voice,
            silence_duration_ms=session.silence_duration_ms,
            input_label=session.input_label,
            turns=len(session.turns),
            has_audio=store.audio_path(session.id) is not None,
        )
        for session in store.list_sessions()
    ]


@router.get("/sessions/{session_id}")
def read_session(session_id: str, store: Annotated[Store, Depends(get_store)]) -> SessionDetail:
    session = store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"No session {session_id}")
    return SessionDetail(
        id=session.id,
        status=session.status,
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
        stories=[
            StoryView(
                id=story.id,
                title=story.title,
                summary=story.summary,
                life_stage=story.life_stage,
                approx_period=story.approx_period,
                people=story.people,
                places=story.places,
                quotes=[QuoteView(**q.__dict__) for q in story.quotes],
            )
            for story in store.stories_for_session(session_id)
        ],
        processing_error=session.processing_error,
    )


@router.get("/sessions/{session_id}/audio")
def read_audio(session_id: str, store: Annotated[Store, Depends(get_store)]) -> FileResponse:
    path = store.audio_path(session_id)
    if path is None:
        raise HTTPException(status_code=404, detail=f"No recording for {session_id}")
    return FileResponse(path, media_type="audio/wav", filename=f"kataribe-{session_id}.wav")
