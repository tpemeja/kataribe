"""What a run of the harness costs, from the published rates.

    uv run python costs.py --live-minutes 12 --judge-calls 5

Rates are list prices as of 2026-09-23; the authority is
https://ai.google.dev/gemini-api/docs/pricing and actual spend is at
https://aistudio.google.com/usage. This is for sizing a change before making
it, not for reconciling a bill.
"""

import argparse

AUDIO_IN_PER_MIN = 0.005
AUDIO_OUT_PER_MIN = 0.018
FLASH_IN_PER_TOKEN = 0.75 / 1_000_000
FLASH_OUT_PER_TOKEN = 3.75 / 1_000_000

# A judge call sends the interviewer prompt plus both sides of one exchange.
JUDGE_IN_TOKENS = 1_600
JUDGE_OUT_TOKENS = 150

# The interviewee talks most of the time; the interviewer answers briefly.
SPEAKING_SHARE = 0.25


def session_cost(minutes: float, sessions: int = 1) -> float:
    """Audio flows the whole time a session is open, including the silence."""
    per_session = minutes * (AUDIO_IN_PER_MIN + SPEAKING_SHARE * AUDIO_OUT_PER_MIN)
    return per_session * sessions


def judge_cost(calls: int) -> float:
    return calls * (JUDGE_IN_TOKENS * FLASH_IN_PER_TOKEN + JUDGE_OUT_TOKENS * FLASH_OUT_PER_TOKEN)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live-minutes", type=float, default=0.0)
    parser.add_argument("--sessions", type=int, default=1, help="concurrent per minute counted")
    parser.add_argument("--judge-calls", type=int, default=0)
    args = parser.parse_args()

    audio = session_cost(args.live_minutes, args.sessions)
    judged = judge_cost(args.judge_calls)

    print(f"  live audio  {args.live_minutes:6.1f} min x{args.sessions}   ${audio:7.4f}")
    print(f"  judge       {args.judge_calls:6d} calls        ${judged:7.4f}")
    print(f"  total                          ${audio + judged:7.4f}")


if __name__ == "__main__":
    main()
