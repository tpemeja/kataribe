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


def extract(settings: Settings, senior: Senior, turns: list[Turn]) -> Extraction:
    client = genai.Client(api_key=settings.gemini_api_key)
    response = client.models.generate_content(
        model=settings.text_model,
        contents=(
            "次は、お年寄りの人生の物語を伺った会話の記録です。\n"
            "この会話から、その方の人生の出来事を取り出してください。\n\n"
            f"=== この方について（確かな事実）===\n{_who(senior)}\n\n"
            f"=== 会話 ===\n{_numbered(turns)}\n\n"
            "=== 取り出し方 ===\n"
            "- 話し手が実際に語ったことだけを書いてください。聞き手の言葉は使わないでください。\n"
            "- 会話に出てこないことを、推測して補わないでください。\n"
            "- title と summary にも、話し手が使った言葉をそのまま使ってください。\n"
            "  「実家」「故郷」「生家」のように、話し手が使っていない言葉で\n"
            "  言いかえないでください。\n"
            "  人や物のつながりを、勝手に決めつけないでください。\n"
            "  たとえば『父の工場』と言われたなら『父の工場』であって、\n"
            "  『実家の工場』ではありません。\n"
            "- quotes には、話し手が言ったとおりの言葉を、一字も変えずに入れてください。\n"
            "  要約したり、言い換えたりしないでください。\n"
            f"- life_stage は次のどれかにしてください: {'、'.join(LIFE_STAGES)}\n"
            "- approx_period は「昭和二十年ごろ」のような、会話から分かる範囲で結構です。\n"
            "  分からなければ空にしてください。\n"
            "- まだ何も語られていなければ、stories は空にしてください。\n"
            "- refused_topics には、話したくないと言われた話題を入れてください。"
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
            )
        )
    return stories, dropped


def plan_next(
    settings: Settings, senior: Senior, stories: list[Story], avoid: list[str]
) -> NextPlan:
    told = (
        "\n".join(f"- [{s.life_stage}] {s.title}: {s.summary}" for s in stories)
        or "（まだ何も伺っていません）"
    )
    thin = [stage for stage in LIFE_STAGES if not any(s.life_stage == stage for s in stories)]

    client = genai.Client(api_key=settings.gemini_api_key)
    response = client.models.generate_content(
        model=settings.text_model,
        contents=(
            "お年寄りの人生の物語を、少しずつ伺っています。\n"
            "次にお会いしたときに何を伺うか、考えてください。\n\n"
            f"=== この方について ===\n{_who(senior)}\n\n"
            f"=== これまでに伺ったお話 ===\n{told}\n\n"
            f"=== まだ伺っていない時期 ===\n{'、'.join(thin) or 'なし'}\n\n"
            f"=== 触れてはいけない話題 ===\n{'、'.join(avoid) or 'なし'}\n\n"
            "=== お願い ===\n"
            "- story_so_far: これまでのお話を、二、三文でまとめてください。\n"
            "  次の会のはじめに『前回は〜のお話を伺いました』と言うために使います。\n"
            "  上に書かれていることだけを使ってください。\n"
            "  情景を想像して付け足したり、感想や評価を書いたりしないでください。\n"
            "  「印象的でした」「豊かな自然に囲まれた」のような、\n"
            "  ご本人が言っていない言葉は、ぜったいに入れないでください。\n"
            "- next_questions: 次に伺いたいことを三つ、日本語の短い質問文で。\n"
            "  まだ伺っていない時期や、名前だけ出てまだ語られていない方を優先してください。\n"
            "  触れてはいけない話題には、けっして触れないでください。\n"
            "  ひとつの質問で聞くことは、ひとつだけにしてください。"
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
