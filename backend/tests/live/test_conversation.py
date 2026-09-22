"""The interviewer against a simulated interviewee, both on live audio.

These cost a minute each and cover what a scripted recording cannot: the
interviewer has to react to someone who reacts back.
"""

import pytest

from kataribe.config import Settings
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
    result = await partner.converse(KIMIKO, settings, seconds=60)

    assert result.error is None, result.error
    assert result.spoke, f"No conversation happened: {result.ended}"

    verdict = checks.judge(
        settings,
        "The person drifted from what was asked to something else. The reply "
        "must go with them rather than steering back to the original question. "
        "Following the new subject passes; repeating or rephrasing the original "
        "question fails.",
        senior=result.senior_said,
        interviewer=result.interviewer_said,
    )
    assert verdict.passes, f"{verdict.reason}\nReply: {result.interviewer_said}"
