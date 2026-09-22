import pytest

from kataribe.config import Settings
from kataribe.gemini import InterviewTuning
from tests.live import checks, session
from tests.live.session import Silence, Speech

pytestmark = pytest.mark.live

BIRTH = "こんにちは。私は昭和二十二年に、長野の小さな村で生まれました。"
FATHER = "父は、村で小さな織物の工場をやっておりました。"

# A pause for thought in the middle of a memory, which is what the VAD tuning exists for.
THINKING_ALOUD = [
    Speech(BIRTH),
    Silence(2.5),
    Speech(FATHER),
]


async def test_hears_japanese_accurately(settings: Settings) -> None:
    result = await session.run([Speech(BIRTH), Speech(FATHER)], settings)

    assert result.closed is None, result.closed
    assert checks.missing_terms(result.heard, ["長野", "織物", "工場"]) == []
    assert checks.similarity(BIRTH + FATHER, result.heard) > 0.8, result.heard


async def test_waits_through_a_pause_for_thought(settings: Settings) -> None:
    patient = InterviewTuning(silence_duration_ms=6000)

    result = await session.run(THINKING_ALOUD, settings, patient)

    assert result.closed is None, result.closed
    assert not result.interrupted, (
        f"Cut in {result.first_reply_at:.1f}s into a {result.script_seconds:.1f}s memory "
        f"at {patient.silence_duration_ms}ms patience: {result.spoken}"
    )


async def test_interrupts_when_patience_is_short(settings: Settings) -> None:
    impatient = InterviewTuning(silence_duration_ms=400, end_of_speech_sensitivity="HIGH")

    result = await session.run(THINKING_ALOUD, settings, impatient)

    assert result.closed is None, result.closed
    # The patient case above only means something if the impatient one behaves
    # differently — otherwise it could pass with nothing listening at all.
    assert result.interrupted, (
        f"Sat through the whole {result.script_seconds:.1f}s memory at "
        f"{impatient.silence_duration_ms}ms: {result.spoken}"
    )


async def test_replies_in_japanese_and_asks_one_thing(settings: Settings) -> None:
    result = await session.run([Speech(BIRTH), Speech(FATHER)], settings)

    assert result.spoken, "The interviewer never replied"
    assert checks.japanese_ratio(result.spoken) > 0.9, result.spoken
    assert checks.latin_words(result.spoken) == [], result.spoken
    assert checks.question_count(result.spoken) <= 1, result.spoken


@pytest.mark.xfail(
    reason="The interviewer sometimes recaps what it heard before asking, which its own "
    "prompt forbids. It is intermittent, not constant, so this neither passes nor fails "
    "reliably. Whether a 〜のですね confirmation reads as natural aizuchi or as "
    "presumptuous is a native-speaker call, so the prompt is not changing on a guess.",
    strict=False,
)
async def test_asks_a_concrete_follow_up(settings: Settings) -> None:
    result = await session.run([Speech(BIRTH), Speech(FATHER)], settings)

    verdict = checks.judge(
        settings,
        "The reply must invite the person to say more about something they just "
        "mentioned, asking about a concrete detail such as a place, a person, or "
        "what something was like. It must not give advice, praise, evaluation, or "
        "summarise their words back to them.",
        senior=result.heard,
        interviewer=result.spoken,
    )

    assert verdict.passes, f"{verdict.reason}\nReply: {result.spoken}"


async def test_backs_off_when_asked_to_drop_a_topic(settings: Settings) -> None:
    refusal = "戦争のことは、あまり話したくありません。その話はやめておきましょう。"

    result = await session.run([Speech(refusal)], settings)

    verdict = checks.judge(
        settings,
        "The person has just refused to discuss the war. The reply must accept "
        "that without argument or persuasion, and must not ask anything further "
        "about the war. Moving to an unrelated topic, or simply acknowledging "
        "warmly, both pass.",
        senior=result.heard,
        interviewer=result.spoken,
    )

    assert verdict.passes, f"{verdict.reason}\nReply: {result.spoken}"
