from functools import lru_cache
from importlib import resources

from kataribe.languages import Language, get

__all__ = ["interviewer_instruction"]


@lru_cache
def interviewer_instruction(language: Language | None = None) -> str:
    chosen = language or get(None)
    return (resources.files(__package__) / chosen.prompt_file).read_text(encoding="utf-8").strip()
