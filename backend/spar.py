"""Run the interviewer against a simulated interviewee and report the timing.

    uv run python spar.py --persona haru --seconds 90 --patience 5000

Prints who spoke when, flags any moment the interviewer talked over the other
side, and saves a stereo recording you can listen to.
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from tests.live import partner  # noqa: E402
from tests.live.personas import CAST  # noqa: E402

from kataribe.config import Settings  # noqa: E402
from kataribe.gemini import InterviewTuning  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--persona", choices=sorted(CAST), default="haru")
    parser.add_argument("--seconds", type=float, default=75.0)
    parser.add_argument("--patience", type=int, default=None, help="silence_duration_ms")
    parser.add_argument("--out", type=Path, default=Path("var/spar"))
    args = parser.parse_args()

    settings = Settings()
    if not settings.gemini_api_key:
        print("KATARIBE_GEMINI_API_KEY is not set", file=sys.stderr)
        return 1

    persona = CAST[args.persona]
    tuning = InterviewTuning(silence_duration_ms=args.patience) if args.patience else None
    patience = (tuning or InterviewTuning()).silence_duration_ms

    print(f"{persona.name} — {persona.exercises}")
    print(f"patience {patience}ms, {args.seconds:.0f}s\n")

    result = asyncio.run(partner.converse(persona, settings, args.seconds, tuning))

    if result.error:
        print(f"FAILED: {result.error}", file=sys.stderr)
        return 1
    if result.ended:
        print(f"(note: {result.ended})\n")

    print("--- who spoke when ---")
    timeline = [("interviewee", s, e) for s, e in result.senior_intervals]
    timeline += [("interviewer", s, e) for s, e in result.interviewer_intervals]
    for who, start, end in sorted(timeline, key=lambda row: row[1]):
        print(f"  {start:6.1f}s - {end:6.1f}s  {who}")

    print(f"\n--- 聞き手 ---\n{result.interviewer_said or '(silent)'}")
    print(f"\n--- {persona.name} ---\n{result.senior_said or '(silent)'}")

    overlaps = result.overlaps()
    print("\n--- talking over ---")
    if overlaps:
        for at, length in overlaps:
            print(f"  {at:6.1f}s  interviewer cut in for {length:.1f}s")
    else:
        print("  none — the interviewer waited every time")

    recording = args.out / f"{persona.key}-{patience}ms.wav"
    result.save(recording)
    print(f"\nrecording: {recording}  (interviewee left, interviewer right)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
