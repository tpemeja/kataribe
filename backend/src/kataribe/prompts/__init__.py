from functools import lru_cache
from importlib import resources

__all__ = ["interviewer_instruction"]


@lru_cache
def interviewer_instruction() -> str:
    return (resources.files(__package__) / "interviewer_ja.md").read_text(encoding="utf-8")
