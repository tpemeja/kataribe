"""Runs the brain over a finished session.

Kept apart from the API so it can move to its own Cloud Run job later without
anything above it changing.
"""

import logging
from dataclasses import replace

from kataribe import brain
from kataribe.config import Settings
from kataribe.store import Plan, Store

log = logging.getLogger(__name__)


def process_session(settings: Settings, store: Store, session_id: str) -> None:
    session = store.get(session_id)
    if session is None:
        return
    if not session.senior_id:
        store.set_status(session_id, "skipped", "No senior attached to this session")
        return

    senior = store.get_senior(session.senior_id)
    if senior is None:
        store.set_status(session_id, "failed", f"No senior {session.senior_id}")
        return

    store.set_status(session_id, "processing")
    try:
        extraction = brain.extract(settings, senior, session.turns)
        stories, dropped = brain.verify(extraction, session.turns)
        if dropped:
            # Loud on purpose: a quote the person never said is the failure this
            # product can least afford, and the guard existing is not the same
            # as the guard never firing.
            log.warning(
                "session %s: dropped %d quote(s) not found in the transcript: %s",
                session_id,
                len(dropped),
                dropped,
            )

        stored = [replace(story, senior_id=senior.id, session_id=session_id) for story in stories]
        store.replace_stories(session_id, senior.id, stored)

        previous = store.get_plan(senior.id)
        avoid = sorted(set(previous.avoid_topics) | set(extraction.refused_topics))
        everything = store.stories_for_senior(senior.id)
        planned = brain.plan_next(settings, senior, everything, avoid)

        store.save_plan(
            senior.id,
            Plan(
                story_so_far=planned.story_so_far,
                next_questions=planned.next_questions,
                avoid_topics=avoid,
            ),
        )
        store.set_status(session_id, "processed")
    except Exception as error:  # noqa: BLE001
        log.exception("session %s could not be processed", session_id)
        store.set_status(session_id, "failed", f"{type(error).__name__}: {error}")
