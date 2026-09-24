"""Languages the interviewer can work in.

Japanese is the product. French and English exist so the whole loop can be
exercised without a Japanese speaker in the room — turn-taking, following a
change of subject, backing off, extraction, memory. All of that is the same
behaviour in any language.

What is not the same: honorific register, and the kanji homophones that make a
name come back misspelled. Those have no French or English equivalent, so a
green run in a development language says nothing about them.

Each language keeps its own defaults for exactly that reason. A pause length
that feels right in French must not become the one an elderly Japanese speaker
gets — only the Japanese figure below was measured against Japanese speech.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Language:
    code: str
    locale: str
    label: str
    endonym: str
    prompt_file: str
    voice: str
    silence_duration_ms: int
    measured: bool
    """Whether silence_duration_ms came from a measurement or is a starting guess."""

    opening: str
    """A stage direction sent when the session opens, so the interviewer speaks
    first rather than waiting to be spoken to. Nobody should have to work out
    that they are meant to start."""


LANGUAGES: dict[str, Language] = {
    "ja": Language(
        code="ja",
        locale="ja-JP",
        label="Japanese",
        endonym="日本語",
        prompt_file="interviewer_ja.md",
        voice="Sulafat",
        # Measured: 3500ms cut into a 2.5s pause for thought, 6000ms sat
        # through 4s. See docs/roadmap.md.
        silence_duration_ms=5000,
        measured=True,
        opening="（その方が席につかれました。こちらから、やさしく声をかけてください。）",
    ),
    "fr": Language(
        code="fr",
        locale="fr-FR",
        label="French",
        endonym="Français",
        prompt_file="interviewer_fr.md",
        voice="Sulafat",
        # A starting point, not a measurement. Nobody has run the pause test
        # against French speech; this was lowered from 2500 because the wait
        # between turns felt dead, and French is only ever used for testing.
        silence_duration_ms=1500,
        measured=False,
        opening="(La personne vient de s'asseoir. Adressez-lui la parole doucement.)",
    ),
    "en": Language(
        code="en",
        locale="en-US",
        label="English",
        endonym="English",
        prompt_file="interviewer_en.md",
        voice="Sulafat",
        silence_duration_ms=2500,
        measured=False,
        opening="(They have just sat down. Speak to them gently, first.)",
    ),
}

DEFAULT = LANGUAGES["ja"]


def get(code: str | None) -> Language:
    return LANGUAGES.get(code or "", DEFAULT)
