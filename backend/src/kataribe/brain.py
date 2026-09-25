"""Turns a finished conversation into stories, and plans the next one.

Every quote an extraction produces is checked against the transcript before it
is stored. The model is asked for the person's own words, and a quote that is
not found verbatim is dropped rather than kept — a memoir is the one place a
plausible-sounding paraphrase must not end up.
"""

import re
import uuid

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from kataribe.config import Settings
from kataribe.languages import Language, get
from kataribe.store import LIFE_STAGES, Plan, Quote, Senior, Story, Turn

NOISE = re.compile(r"[\s、。「」『』・,.!?！？…ー]")


class ExtractedQuote(BaseModel):
    text: str = Field(description="話し手が言ったとおりの言葉。一字も変えないこと。")
    turn: int = Field(description="その言葉があった発言の番号")


class ExtractedStory(BaseModel):
    title: str
    summary: str
    life_stage: str
    approx_period: str
    people: list[str]
    places: list[str]
    quotes: list[ExtractedQuote]
    consent_quote: str = Field(
        default="",
        description=(
            "The speaker's own words agreeing their family may read this story, "
            "exactly as said. Empty unless they clearly agreed."
        ),
    )


class Extraction(BaseModel):
    stories: list[ExtractedStory]
    refused_topics: list[str]


class NextPlan(BaseModel):
    story_so_far: str
    next_questions: list[str]


def _numbered(turns: list[Turn]) -> str:
    return "\n".join(
        f"[{i}] {'話し手' if t.speaker == 'senior' else '聞き手'}: {t.text}"
        for i, t in enumerate(turns)
    )


def _who(senior: Senior) -> str:
    facts = [f"お名前: {senior.name}"]
    if senior.name_reading:
        facts.append(f"読み: {senior.name_reading}")
    if senior.birth_year:
        facts.append(f"生まれ年: {senior.birth_year}年")
    if senior.birthplace:
        facts.append(f"出身: {senior.birthplace}")
    if senior.family:
        facts.append(f"ご家族: {'、'.join(senior.family)}")
    return "\n".join(facts)


def extract(
    settings: Settings, senior: Senior, turns: list[Turn], language: Language | None = None
) -> Extraction:
    """Instructions are in English; what it writes is in the language spoken.

    One set of instructions rather than one per language: the rules here are
    about not inventing things, which is the same rule everywhere, and three
    copies would drift apart.
    """
    spoken = language or get(senior.language)
    client = genai.Client(api_key=settings.gemini_api_key)
    response = client.models.generate_content(
        model=settings.text_model,
        contents=(
            "Below is a recorded conversation in which an elderly person was "
            "asked about their life. Pull out the events of their life from it.\n\n"
            f"=== About this person (established facts) ===\n{_who(senior)}\n\n"
            f"=== The conversation ===\n{_numbered(turns)}\n\n"
            "=== How to do it ===\n"
            f"- Write everything in {spoken.label}, the language they spoke.\n"
            "- Only what the speaker actually said. Never the interviewer's words.\n"
            "- Do not fill in anything the conversation does not contain.\n"
            "- The title and summary must use the speaker's own words too. Do not\n"
            "  swap in a word they did not use, and do not assert a relationship\n"
            "  they did not state: if they said 'my father's factory' then it is\n"
            "  'my father's factory', not 'the family home's factory'.\n"
            "- quotes must be the speaker's words exactly, not one character\n"
            "  changed. Never summarise or paraphrase inside a quote.\n"
            f"- life_stage must be one of: {', '.join(LIFE_STAGES)}\n"
            "- approx_period as far as the conversation shows it, and empty if\n"
            "  it does not.\n"
            "- If nothing has been told yet, leave stories empty.\n"
            "- consent_quote: if they were asked whether their family may read\n"
            "  this and clearly agreed, put their own words here, exactly as\n"
            "  said. Leave it empty if they were not asked, if they declined, if\n"
            "  they hesitated, or if the answer is at all unclear. A polite noise\n"
            "  that is not an answer is not agreement.\n"
            "- refused_topics: anything they said they did not want to discuss."
        ),
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=Extraction,
            temperature=0.0,
        ),
    )
    result = response.parsed
    if not isinstance(result, Extraction):
        raise RuntimeError(f"Extraction returned nothing usable: {response.text!r}")
    return result


def verify(extraction: Extraction, turns: list[Turn]) -> tuple[list[Story], list[str]]:
    """Keep only quotes that the person actually said. Returns stories and what was dropped."""
    spoken = {i: NOISE.sub("", t.text) for i, t in enumerate(turns) if t.speaker == "senior"}
    stories: list[Story] = []
    dropped: list[str] = []

    for extracted in extraction.stories:
        kept: list[Quote] = []
        for quote in extracted.quotes:
            needle = NOISE.sub("", quote.text)
            if not needle:
                continue
            where = next((i for i, said in spoken.items() if needle in said), None)
            if where is None:
                dropped.append(quote.text)
            else:
                kept.append(Quote(text=quote.text, turn=where))

        stage = extracted.life_stage if extracted.life_stage in LIFE_STAGES else LIFE_STAGES[0]

        # Sharing a life story with a family is not something to infer. It
        # counts only when the person said so and we still have the words: an
        # agreement the model reports but cannot evidence is no agreement.
        consent = NOISE.sub("", extracted.consent_quote)
        agreed = bool(consent) and any(consent in said for said in spoken.values())
        if extracted.consent_quote and not agreed:
            dropped.append(f"(consent) {extracted.consent_quote}")

        stories.append(
            Story(
                id=uuid.uuid4().hex[:12],
                senior_id="",
                session_id="",
                title=extracted.title,
                summary=extracted.summary,
                life_stage=stage,
                approx_period=extracted.approx_period,
                people=extracted.people,
                places=extracted.places,
                quotes=kept,
                visibility="family" if agreed else "private",
                consent_quote=extracted.consent_quote if agreed else "",
            )
        )
    return stories, dropped


def plan_next(
    settings: Settings,
    senior: Senior,
    stories: list[Story],
    avoid: list[str],
    language: Language | None = None,
) -> NextPlan:
    spoken = language or get(senior.language)
    told = (
        "\n".join(f"- [{s.life_stage}] {s.title}: {s.summary}" for s in stories)
        or "(nothing has been told yet)"
    )
    thin = [stage for stage in LIFE_STAGES if not any(s.life_stage == stage for s in stories)]

    client = genai.Client(api_key=settings.gemini_api_key)
    response = client.models.generate_content(
        model=settings.text_model,
        contents=(
            "An elderly person's life story is being collected a little at a "
            "time. Decide what to ask about when you next sit with them.\n\n"
            f"=== About this person ===\n{_who(senior)}\n\n"
            f"=== What they have told us so far ===\n{told}\n\n"
            f"=== Periods not yet covered ===\n{', '.join(thin) or 'none'}\n\n"
            f"=== Topics never to raise ===\n{', '.join(avoid) or 'none'}\n\n"
            "=== What to write ===\n"
            f"- Write everything in {spoken.label}, the language they speak.\n"
            "- story_so_far: two or three sentences covering what they have told\n"
            "  us, used to open the next session with 'last time you told me\n"
            "  about...'. Use only what is written above. Do not imagine a scene,\n"
            "  and do not add an impression or an evaluation. Words like 'it was\n"
            "  very moving' or 'surrounded by rich nature' must never appear\n"
            "  unless they said them.\n"
            "- next_questions: three short questions. Prefer the periods not yet\n"
            "  covered, and people who have been named but not yet described.\n"
            "  Never touch a topic listed above as never to raise.\n"
            "  One question asks one thing."
        ),
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=NextPlan,
            temperature=0.3,
        ),
    )
    result = response.parsed
    if not isinstance(result, NextPlan):
        raise RuntimeError(f"Planning returned nothing usable: {response.text!r}")
    return result


def context_for(senior: Senior, plan: Plan) -> str:
    """The part of the interviewer's prompt that changes between sessions."""
    lines = [
        "## お相手について",
        "",
        "次のことは、すでに分かっています。お尋ねする必要はありません。",
        "お名前は、この表記のとおりにお呼びしてください。",
        "",
        _who(senior),
    ]
    if plan.story_so_far:
        lines += ["", "## 前回までに伺ったお話", "", plan.story_so_far]
    if plan.next_questions:
        lines += [
            "",
            "## 今日、伺えるとよいこと",
            "",
            "順番に聞く必要はありません。相手のお話にあわせて、自然に。",
            "",
            *(f"- {q}" for q in plan.next_questions),
        ]
    if plan.avoid_topics:
        lines += [
            "",
            "## 触れてはいけない話題",
            "",
            "以前、話したくないとおっしゃった話題です。こちらから持ち出さないでください。",
            "",
            *(f"- {t}" for t in plan.avoid_topics),
        ]
    return "\n".join(lines)
