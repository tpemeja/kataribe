"""Extraction against the real model.

`verify` is unit-tested and will drop a quote the person never said. These tests
ask a different question: does the model produce verbatim quotes in the first
place, or is the guard having to catch it every time?
"""

import pytest

from kataribe import brain
from kataribe.config import Settings
from kataribe.store import Senior, Turn
from tests.live import checks

pytestmark = pytest.mark.live

HARU = Senior(
    id="s1",
    name="田中ハル",
    name_reading="たなかはる",
    birth_year=1944,
    birthplace="長野",
    family=["夫 正夫", "娘 ふたり"],
)

CONVERSATION = [
    Turn(
        speaker="ai", text="こんにちは。今日はどんなお話を聞かせていただけますか。", started_at=0.0
    ),
    Turn(
        speaker="senior",
        text="昭和十九年に、長野の山あいの村で生まれました。"
        "父は村で小さな織物の工場をやっておりました。",
        started_at=5.0,
    ),
    Turn(speaker="ai", text="どんな工場でしたか。", started_at=20.0),
    Turn(
        speaker="senior",
        text="小さな工場でしてね、働いていたのは近所の人が七、八人でした。"
        "二十四歳のときに、小学校の先生だった正夫さんと結婚しました。",
        started_at=25.0,
    ),
]


async def test_quotes_come_back_verbatim(settings: Settings) -> None:
    extraction = brain.extract(settings, HARU, CONVERSATION)
    stories, dropped = brain.verify(extraction, CONVERSATION)

    assert stories, "Nothing was extracted from a conversation with two clear memories"
    assert dropped == [], f"Quoted words she never said: {dropped}"
    assert any(story.quotes for story in stories), "Extracted stories with no quotes at all"


async def test_extraction_does_not_add_what_was_not_said(settings: Settings) -> None:
    extraction = brain.extract(settings, HARU, CONVERSATION)
    stories, _ = brain.verify(extraction, CONVERSATION)
    written = "\n".join(f"{s.title}: {s.summary} [{s.approx_period}]" for s in stories)

    verdict = checks.judge(
        settings,
        "Every place, person, date and detail in the extracted stories must "
        "appear in the conversation. Adding a detail that was not said, however "
        "plausible, fails. Leaving something out is fine.",
        senior="\n".join(t.text for t in CONVERSATION if t.speaker == "senior"),
        interviewer=written,
    )
    assert verdict.passes, f"{verdict.reason}\n\n{written}"


async def test_the_recap_repeats_rather_than_embellishes(settings: Settings) -> None:
    # story_so_far is spoken back to the person at the start of the next
    # session, so an invented detail here is told to them as their own memory.
    extraction = brain.extract(settings, HARU, CONVERSATION)
    stories, _ = brain.verify(extraction, CONVERSATION)
    plan = brain.plan_next(settings, HARU, stories, [])

    verdict = checks.judge(
        settings,
        "This is a recap that will be read back to the person as what they said "
        "last time. It must contain only what they actually said. Any scene "
        "setting, impression or evaluation — 'surrounded by rich nature', 'it "
        "was very moving' — fails, as does any detail they did not give.",
        senior="\n".join(t.text for t in CONVERSATION if t.speaker == "senior"),
        interviewer=plan.story_so_far,
    )
    assert verdict.passes, f"{verdict.reason}\n\n{plan.story_so_far}"


async def test_it_plans_questions_about_what_is_still_missing(settings: Settings) -> None:
    extraction = brain.extract(settings, HARU, CONVERSATION)
    stories, _ = brain.verify(extraction, CONVERSATION)
    plan = brain.plan_next(settings, HARU, stories, ["戦争"])

    assert plan.next_questions, "Planned no questions at all"
    assert all("戦争" not in q for q in plan.next_questions), (
        f"Planned to ask about a refused topic: {plan.next_questions}"
    )
    assert all(q.count("?") + q.count("？") <= 1 for q in plan.next_questions), (
        f"A planned question asks more than one thing: {plan.next_questions}"
    )
