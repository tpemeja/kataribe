"""Assertions about a recorded conversation.

Rules cover the mechanical faults and never flake. The judge covers what rules
cannot express — whether the interviewer actually behaved like the prompt asks.
"""

import re
import time
from difflib import SequenceMatcher

from google import genai
from google.genai import errors, types
from pydantic import BaseModel

from kataribe.config import Settings
from kataribe.prompts import interviewer_instruction

JAPANESE = re.compile(r"[぀-ゟ゠-ヿ一-鿿]")
LATIN_WORD = re.compile(r"[A-Za-z]{3,}")
NOISE = re.compile(r"[\s、。「」『』・,.!?！？]")


class Judgement(BaseModel):
    passes: bool
    reason: str


def japanese_ratio(text: str) -> float:
    letters = [c for c in text if not NOISE.match(c)]
    if not letters:
        return 0.0
    return len(JAPANESE.findall(text)) / len(letters)


def latin_words(text: str) -> list[str]:
    return LATIN_WORD.findall(text)


def question_count(text: str) -> int:
    return text.count("?") + text.count("？")


def similarity(spoken: str, heard: str) -> float:
    """How closely the transcript matches the script, ignoring punctuation."""
    return SequenceMatcher(None, NOISE.sub("", spoken), NOISE.sub("", heard)).ratio()


def missing_terms(text: str, terms: list[str]) -> list[str]:
    return [term for term in terms if term not in text]


def judge(
    settings: Settings, criterion: str, senior: str, interviewer: str, attempts: int = 4
) -> Judgement:
    """Grade one turn against the interviewer's own instructions.

    The judge model returns 503 under load often enough that a single attempt
    turns a passing suite red for no reason, so transient errors are retried.
    """
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            return _ask(settings, criterion, senior, interviewer)
        except errors.ServerError as error:
            last = error
            time.sleep(2**attempt)
    raise AssertionError(f"Judge unreachable after {attempts} attempts: {last}")


def _ask(settings: Settings, criterion: str, senior: str, interviewer: str) -> Judgement:
    client = genai.Client(api_key=settings.gemini_api_key)
    response = client.models.generate_content(
        model=settings.text_model,
        contents=(
            "You are grading one turn of a Japanese life-story interview against "
            "the interviewer's own instructions.\n\n"
            "=== The interviewer was given these instructions ===\n"
            f"{interviewer_instruction()}\n\n"
            "=== What the elderly person said ===\n"
            f"{senior or '(nothing yet)'}\n\n"
            "=== What the interviewer replied ===\n"
            f"{interviewer or '(nothing)'}\n\n"
            "=== Grade only this ===\n"
            f"{criterion}\n\n"
            "Judge only the criterion above, not anything else about the reply. "
            "Be strict: a reply that merely avoids being wrong does not pass if it "
            "fails the criterion. Answer in English."
        ),
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=Judgement,
            temperature=0.0,
        ),
    )
    verdict = response.parsed
    if not isinstance(verdict, Judgement):
        raise RuntimeError(f"Judge returned no verdict: {response.text!r}")
    return verdict
