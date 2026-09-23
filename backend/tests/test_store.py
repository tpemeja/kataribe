from pathlib import Path

from kataribe.store import Store, Turn


def make_store(tmp_path: Path) -> Store:
    return Store(tmp_path)


def test_a_started_session_has_no_recording_yet(tmp_path: Path) -> None:
    store = make_store(tmp_path)

    session_id = store.start(
        model="gemini-3.8-live",
        voice="Sulafat",
        silence_duration_ms=5000,
        end_of_speech_sensitivity="LOW",
    )

    session = store.get(session_id)
    assert session is not None
    assert session.ended_at is None
    assert session.turns == []
    assert store.audio_path(session_id) is None


def test_finishing_keeps_the_transcript_and_the_audio(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    session_id = store.start(
        model="m", voice="Sulafat", silence_duration_ms=5000, end_of_speech_sensitivity="LOW"
    )

    store.finish(
        session_id,
        turns=[
            Turn(speaker="senior", text="長野で生まれました", started_at=1.5),
            Turn(speaker="ai", text="どんな村でしたか", started_at=9.0),
        ],
        audio=b"RIFFfake",
        duration_seconds=12.5,
        input_label="microphone",
    )

    session = store.get(session_id)
    assert session is not None
    assert session.duration_seconds == 12.5
    assert [turn.speaker for turn in session.turns] == ["senior", "ai"]
    assert session.turns[0].text == "長野で生まれました"
    assert session.turns[1].started_at == 9.0
    assert store.audio_path(session_id) is not None


def test_a_session_without_audio_is_still_recorded(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    session_id = store.start(
        model="m", voice="Sulafat", silence_duration_ms=5000, end_of_speech_sensitivity="LOW"
    )

    store.finish(session_id, turns=[], audio=None, duration_seconds=3.0, input_label="microphone")

    assert store.audio_path(session_id) is None
    session = store.get(session_id)
    assert session is not None
    assert session.duration_seconds == 3.0


def test_sessions_are_listed_newest_first(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    ids = [
        store.start(
            model="m", voice="Sulafat", silence_duration_ms=5000, end_of_speech_sensitivity="LOW"
        )
        for _ in range(3)
    ]

    listed = [session.id for session in store.list_sessions()]

    assert set(listed) == set(ids)
    assert listed == sorted(
        listed,
        key=lambda i: next(s.started_at for s in store.list_sessions() if s.id == i),
        reverse=True,
    )
