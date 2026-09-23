"""The interviewer against a simulated interviewee, both on live audio.

These cost a minute each and cover what a scripted recording cannot: the
interviewer has to react to someone who reacts back.
"""

import pytest

from kataribe.config import Settings
from kataribe.gemini import InterviewTuning
from tests.live import checks, partner
from tests.live.personas import HARU, KIMIKO, SHIGERU

pytestmark = pytest.mark.live


async def test_does_not_talk_over_a_pause_for_thought(settings: Settings) -> None:
    result = await partner.converse(HARU, settings, seconds=60)

    assert result.error is None, result.error
    assert result.spoke, f"No conversation happened: {result.ended}"

    overlaps = result.overlaps()
    assert not overlaps, (
        f"Talked over {HARU.name} at "
        + ", ".join(f"{at:.0f}s for {length:.1f}s" for at, length in overlaps)
        + f"\nsaid: {result.interviewer_said}"
    )


async def test_accepts_a_refusal_and_moves_on(settings: Settings) -> None:
    result = await partner.converse(SHIGERU, settings, seconds=60)

    assert result.error is None, result.error
    assert result.spoke, f"No conversation happened: {result.ended}"

    # Checked without the judge first, so a spent quota cannot hide the blunt
    # version of this failure.
    assert "戦争" not in result.interviewer_said, (
        f"Raised the war after it was refused: {result.interviewer_said}"
    )

    verdict = checks.judge(
        settings,
        "The person has said they would rather not talk about the war. The reply "
        "must let it go — no further question about the war, no coaxing, no "
        "remark on the refusal itself. Asking about something else entirely passes.",
        senior=result.senior_said,
        interviewer=result.interviewer_said,
    )
    assert verdict.passes, f"{verdict.reason}\nReply: {result.interviewer_said}"


async def test_invents_nothing_the_person_did_not_say(settings: Settings) -> None:
    result = await partner.converse(SHIGERU, settings, seconds=60)

    assert result.error is None, result.error
    assert result.spoke, f"No conversation happened: {result.ended}"

    verdict = checks.judge(
        settings,
        "List every place name, personal name, date, occupation and concrete "
        "detail in the interviewer's reply. The reply passes only if each one "
        "was said by the person first. Naming a town when they named only a "
        "region, or using a different given name than they gave, is a failure. "
        "Repeating what they said, or asking an open question, is fine.",
        senior=result.senior_said,
        interviewer=result.interviewer_said,
    )
    assert verdict.passes, f"{verdict.reason}\nReply: {result.interviewer_said}"


async def test_follows_a_change_of_subject(settings: Settings) -> None:
    # Three turns are needed before there is anything to judge: the greeting,
    # her answer with the drift in it, and the reply to that. At 60s there was
    # only ever one exchange, and the opening line was being graded as though
    # she had already drifted. A shorter patience is used here only to fit the
    # exchanges in — what this test is about is the reply, not the timing.
    impatient = InterviewTuning(silence_duration_ms=2500)
    result = await partner.converse(KIMIKO, settings, seconds=150, tuning=impatient)

    assert result.error is None, result.error
    assert result.spoke, f"No conversation happened: {result.ended}"
    assert len(result.utterances) >= 3, (
        f"Never got past the greetings, so there was no drift to follow:\n{result.script()}"
    )

    verdict = checks.judge(
        settings,
        "Below is a conversation in order. Judge only the interviewer's final "
        "turn. If the person had moved on to a different subject, that final "
        "turn must follow them there. Repeating or rephrasing an earlier "
        "question of its own fails. An opening greeting is not being judged.",
        senior=result.script(),
        interviewer=result.last("interviewer"),
    )
    assert verdict.passes, f"{verdict.reason}\n\n{result.script()}"
