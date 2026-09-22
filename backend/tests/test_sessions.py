import pytest
from fastapi.testclient import TestClient
from google.genai import types

from kataribe.config import Settings, get_settings
from kataribe.gemini import InterviewTuning, build_live_config
from kataribe.main import create_app


def client_with(settings: Settings) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app)


def test_create_session_without_key_is_unavailable() -> None:
    response = client_with(Settings(gemini_api_key="")).post("/api/sessions", json={})

    assert response.status_code == 503


def test_create_session_rejects_unknown_voice() -> None:
    response = client_with(Settings(gemini_api_key="test-key")).post(
        "/api/sessions", json={"voice": "Nonexistent"}
    )

    assert response.status_code == 422


@pytest.mark.parametrize("silence_ms", [199, 8001])
def test_create_session_rejects_silence_outside_tunable_range(silence_ms: int) -> None:
    response = client_with(Settings(gemini_api_key="test-key")).post(
        "/api/sessions", json={"silence_duration_ms": silence_ms}
    )

    assert response.status_code == 422


def test_voices_are_listed() -> None:
    response = client_with(Settings()).get("/api/voices")

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


def test_live_config_requests_word_timestamps_for_quote_linking() -> None:
    config = build_live_config(InterviewTuning())

    assert config.input_audio_transcription is not None
    assert config.input_audio_transcription.word_timestamp is True


def test_live_config_leaves_affective_dialog_off() -> None:
    # Setting it makes any ephemeral-token session reject realtime audio with
    # close code 1007, which is how the browser client connects.
    config = build_live_config(InterviewTuning())

    assert not config.enable_affective_dialog
