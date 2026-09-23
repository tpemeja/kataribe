import datetime
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from google.genai import types

from kataribe.config import Settings, get_settings
from kataribe.gemini import InterviewTuning, SessionCredentials, build_live_config
from kataribe.main import create_app


def client_with(settings: Settings) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app)


def stored(tmp_path: Path, **overrides: object) -> TestClient:
    """A client whose sessions land in a throwaway directory."""
    return client_with(Settings(data_dir=tmp_path, **overrides))  # type: ignore[arg-type]


def test_create_session_without_key_is_unavailable(tmp_path: Path) -> None:
    response = client_with(Settings(gemini_api_key="", data_dir=tmp_path)).post(
        "/api/sessions", json={}
    )

    assert response.status_code == 503


def test_create_session_rejects_unknown_voice(tmp_path: Path) -> None:
    response = client_with(Settings(gemini_api_key="test-key", data_dir=tmp_path)).post(
        "/api/sessions", json={"voice": "Nonexistent"}
    )

    assert response.status_code == 422


@pytest.mark.parametrize("silence_ms", [199, 8001])
def test_create_session_rejects_silence_outside_tunable_range(
    silence_ms: int, tmp_path: Path
) -> None:
    response = client_with(Settings(gemini_api_key="test-key", data_dir=tmp_path)).post(
        "/api/sessions", json={"silence_duration_ms": silence_ms}
    )

    assert response.status_code == 422


def test_voices_are_listed(tmp_path: Path) -> None:
    response = client_with(Settings(data_dir=tmp_path)).get("/api/voices")

    assert response.status_code == 200
    assert "Sulafat" in response.json()


def test_live_config_pins_japanese_and_applies_tuning() -> None:
    config = build_live_config(InterviewTuning(voice="Gacrux", silence_duration_ms=2200))

    assert config.speech_config is not None
    assert config.speech_config.language_code == "ja-JP"
    assert config.response_modalities == [types.Modality.AUDIO]

    detection = config.realtime_input_config.automatic_activity_detection
    assert detection is not None
    assert detection.silence_duration_ms == 2200
    assert detection.end_of_speech_sensitivity == types.EndSensitivity.END_SENSITIVITY_LOW


def test_live_config_asks_for_word_timestamps_even_though_they_do_not_come_back() -> None:
    # The model ignores this today. Kept so offsets arrive free if that changes;
    # see the note in gemini.py before building anything on it.
    config = build_live_config(InterviewTuning())

    assert config.input_audio_transcription is not None
    assert config.input_audio_transcription.word_timestamp is True


def test_live_config_leaves_affective_dialog_off() -> None:
    # Setting it makes any ephemeral-token session reject realtime audio with
    # close code 1007, which is how the browser client connects.
    config = build_live_config(InterviewTuning())

    assert not config.enable_affective_dialog


def fake_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """Skip the real token mint; these tests are about storage, not Gemini."""
    monkeypatch.setattr(
        "kataribe.api.sessions.mint_session_credentials",
        lambda settings, tuning: SessionCredentials(
            token="test-token",
            model="gemini-3.8-live",
            expires_at=datetime.datetime.now(datetime.UTC),
        ),
    )


def test_a_session_is_recorded_when_it_starts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_credentials(monkeypatch)
    client = stored(tmp_path, gemini_api_key="k")

    created = client.post("/api/sessions", json={"voice": "Gacrux"}).json()

    listed = client.get("/api/sessions").json()
    assert [s["id"] for s in listed] == [created["session_id"]]
    assert listed[0]["voice"] == "Gacrux"
    assert listed[0]["has_audio"] is False


def test_a_recording_can_be_uploaded_and_read_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_credentials(monkeypatch)
    client = stored(tmp_path, gemini_api_key="k")
    session_id = client.post("/api/sessions", json={}).json()["session_id"]

    upload = client.post(
        f"/api/sessions/{session_id}/recording",
        data={
            "transcript": json.dumps(
                [{"speaker": "senior", "text": "長野で生まれました", "started_at": 1.5}]
            ),
            "duration_seconds": "12.5",
            "input_label": "microphone",
        },
        files={"audio": ("session.wav", b"RIFFfake", "audio/wav")},
    )
    assert upload.status_code == 204

    detail = client.get(f"/api/sessions/{session_id}").json()
    assert detail["duration_seconds"] == 12.5
    assert detail["transcript"] == [
        {"speaker": "senior", "text": "長野で生まれました", "started_at": 1.5}
    ]
    assert client.get(f"/api/sessions/{session_id}/audio").content == b"RIFFfake"


def test_uploading_to_an_unknown_session_is_rejected(tmp_path: Path) -> None:
    response = stored(tmp_path).post(
        "/api/sessions/nope/recording",
        data={"transcript": "[]", "duration_seconds": "1"},
    )

    assert response.status_code == 404
