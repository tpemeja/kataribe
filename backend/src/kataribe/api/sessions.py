import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from kataribe.config import Settings, get_settings
from kataribe.gemini import VOICES, InterviewTuning, mint_session_credentials

router = APIRouter(prefix="/api", tags=["sessions"])


class SessionRequest(BaseModel):
    voice: str = "Sulafat"
    silence_duration_ms: int = Field(default=1500, ge=200, le=4000)
    end_of_speech_sensitivity: Literal["LOW", "HIGH"] = "LOW"


class SessionResponse(BaseModel):
    token: str
    model: str
    expires_at: datetime.datetime
    voice: str
    silence_duration_ms: int


@router.get("/voices")
def list_voices() -> dict[str, str]:
    return VOICES


@router.post("/sessions")
def create_session(
    request: SessionRequest,
    settings: Annotated[Settings, Depends(get_settings)],
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

    return SessionResponse(
        token=credentials.token,
        model=credentials.model,
        expires_at=credentials.expires_at,
        voice=tuning.voice,
        silence_duration_ms=tuning.silence_duration_ms,
    )
