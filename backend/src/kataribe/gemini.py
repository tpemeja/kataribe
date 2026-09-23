import datetime
from dataclasses import dataclass

from google import genai
from google.genai import types

from kataribe.config import Settings
from kataribe.prompts import interviewer_instruction

TOKEN_LIFETIME = datetime.timedelta(minutes=30)
NEW_SESSION_WINDOW = datetime.timedelta(minutes=2)

# Shortlisted from the prebuilt TTS voices for an elderly listener. A native
# speaker picks the final one by ear during the week-1 test.
VOICES: dict[str, str] = {
    "Sulafat": "warm",
    "Vindemiatrix": "gentle",
    "Achird": "friendly",
    "Gacrux": "mature",
    "Callirrhoe": "easy-going",
    "Despina": "smooth",
    "Kore": "firm",
}

END_SENSITIVITY = {
    "LOW": types.EndSensitivity.END_SENSITIVITY_LOW,
    "HIGH": types.EndSensitivity.END_SENSITIVITY_HIGH,
}


@dataclass(frozen=True)
class InterviewTuning:
    voice: str = "Sulafat"
    # Measured: at 3500ms the interviewer cut into a 2.5s pause for thought, and
    # at 6000ms it sat through 4s. The gap the model sees is longer than the
    # pause itself, so tolerating an N second silence needs roughly 2N. Erring
    # towards waiting is the right error for someone recalling a memory.
    silence_duration_ms: int = 5000
    end_of_speech_sensitivity: str = "LOW"


@dataclass(frozen=True)
class SessionCredentials:
    token: str
    model: str
    expires_at: datetime.datetime


def build_live_config(tuning: InterviewTuning, context: str = "") -> types.LiveConnectConfig:
    """`context` carries what is known about this particular person and what was
    said last time. Facts given here are not transcribed, which is how the
    interviewer stops guessing at the kanji in someone's name."""
    instruction = interviewer_instruction()
    if context:
        instruction = f"{instruction}\n\n---\n\n{context}"

    return types.LiveConnectConfig(
        response_modalities=[types.Modality.AUDIO],
        system_instruction=instruction,
        speech_config=types.SpeechConfig(
            language_code="ja-JP",
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=tuning.voice)
            ),
        ),
        # word_timestamp is accepted and then ignored by this model: the
        # transcription comes back with text and an empty `words`, on the raw
        # key as well as through a token, with and without VERBATIM mode. It is
        # left set so we get offsets if support arrives, but nothing may depend
        # on it — linking a quote to its audio needs a separate pass over the
        # stored recording.
        input_audio_transcription=types.AudioTranscriptionConfig(
            language_codes=["ja-JP"], word_timestamp=True
        ),
        output_audio_transcription=types.AudioTranscriptionConfig(language_codes=["ja-JP"]),
        realtime_input_config=types.RealtimeInputConfig(
            automatic_activity_detection=types.AutomaticActivityDetection(
                silence_duration_ms=tuning.silence_duration_ms,
                end_of_speech_sensitivity=END_SENSITIVITY[tuning.end_of_speech_sensitivity],
            )
        ),
        # No enable_affective_dialog here. It works on a direct API-key
        # connection, but any session reached through an ephemeral token
        # rejects realtime audio with close code 1007 once it is set — whether
        # locked into the token or asked for by the client. Emotional
        # sensitivity is carried by the interviewer prompt instead.
        context_window_compression=types.ContextWindowCompressionConfig(
            sliding_window=types.SlidingWindow()
        ),
    )


def mint_session_credentials(
    settings: Settings, tuning: InterviewTuning, context: str = ""
) -> SessionCredentials:
    client = genai.Client(api_key=settings.gemini_api_key)
    now = datetime.datetime.now(tz=datetime.UTC)
    expires_at = now + TOKEN_LIFETIME

    token = client.auth_tokens.create(
        config=types.CreateAuthTokenConfig(
            uses=1,
            expire_time=expires_at,
            new_session_expire_time=now + NEW_SESSION_WINDOW,
            live_connect_constraints=types.LiveConnectConstraints(
                model=settings.live_model,
                config=build_live_config(tuning, context),
            ),
            # Empty list locks exactly the fields set above and nothing more.
            lock_additional_fields=[],
        )
    )

    if not token.name:
        raise RuntimeError("Gemini returned an auth token without a name")

    return SessionCredentials(token=token.name, model=settings.live_model, expires_at=expires_at)
