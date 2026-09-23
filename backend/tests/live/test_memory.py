"""Does the interviewer remember the last conversation?

A demo must-have, and until this existed it had never been shown to work: the
plan was being written and the context assembled, but no second session had
ever been run against one.
"""

from pathlib import Path

import pytest

from kataribe import brain
from kataribe.config import Settings
from kataribe.processing import process_session
from kataribe.store import Store, Turn
from tests.live import checks, session
from tests.live.session import Speech

pytestmark = pytest.mark.live

BIRTH = "こんにちは。私は昭和二十二年に、長野の小さな村で生まれました。"
FATHER = "父は、村で小さな織物の工場をやっておりました。"


async def test_the_second_session_opens_by_recalling_the_first(
    settings: Settings, tmp_path: Path
) -> None:
    store = Store(tmp_path)
    senior_id = store.add_senior(
        name="田中ハル", name_reading="たなかはる", birth_year=1947, birthplace="長野"
    )

    # Session one: she tells them where she was born and what her father did.
    first = await session.run([Speech(BIRTH), Speech(FATHER)], settings)
    assert first.closed is None, first.closed
    assert first.heard, "The first session heard nothing, so there is nothing to remember"

    session_id = store.start(
        model=settings.live_model,
        voice="Sulafat",
        silence_duration_ms=5000,
        end_of_speech_sensitivity="LOW",
        senior_id=senior_id,
    )
    turns = [Turn(speaker="senior", text=first.heard, started_at=0.0)]
    store.finish(session_id, turns=turns, audio=None, duration_seconds=30.0, input_label="test")
    process_session(settings, store, session_id)

    stored = store.get(session_id)
    assert stored is not None and stored.status == "processed", (
        f"Processing did not finish: {stored and stored.processing_error}"
    )
    plan = store.get_plan(senior_id)
    assert plan.story_so_far, "Nothing was written down to recall"

    # Session two: the same person, a week later. She says only hello.
    senior = store.get_senior(senior_id)
    assert senior is not None
    second = await session.run(
        [Speech("こんにちは。")], settings, context=brain.context_for(senior, plan)
    )

    assert second.closed is None, second.closed
    assert second.spoken, "The interviewer said nothing at the start of the second session"

    verdict = checks.judge(
        settings,
        "This is the interviewer's opening line in a second conversation with "
        "the same person. It must show that it remembers the previous one — "
        "referring to something she told it before, such as where she was born "
        "or what her father did. A greeting that could have opened a first "
        "conversation with a stranger fails.",
        senior=f"前回伺ったこと: {plan.story_so_far}\n今日、彼女が言ったこと: こんにちは。",
        interviewer=second.spoken,
    )
    assert verdict.passes, f"{verdict.reason}\n\nOpening: {second.spoken}"
