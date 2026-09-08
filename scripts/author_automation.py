#!/usr/bin/env python3
"""Draft a Home Assistant automation from a sentence, using the local LLM.

The drafting itself lives in `src/python/automation_author.py`, so that the
dashboard's /api/automations endpoints and this command line produce exactly
the same proposal from the same sentence. This file is the command line: it
reads Home Assistant, prints what happened, and writes the proposal file.

It writes a proposal, never automations.yaml. Nothing it produces takes effect
until you install it - from the dashboard, or by copying it in yourself.

Run it ON the board -- Home Assistant and Ollama are both loopback-only:

    python3 scripts/author_automation.py "turn on the porch light at sunset"
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.python.automation_author import (  # noqa: E402
    DEFAULT_ENDPOINT,
    DEFAULT_ENTITIES,
    DEFAULT_MODEL,
    DEFAULT_RETRIES,
    DEFAULT_TIMEOUT,
    AuthorError,
    describe,
    draft_automation,
    ha_get,
    load_dotenv,
    render_proposal,
    select_entities,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    load_dotenv(PROJECT_ROOT / ".env")
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("request", help="what the automation should do, in plain English")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    ap.add_argument("--base-url", default=os.getenv("HOME_ASSISTANT_BASE_URL",
                                                    "http://127.0.0.1:8123"))
    ap.add_argument("--entities", type=int, default=DEFAULT_ENTITIES,
                    help="how many to show the model; more crowds a 4096-token context")
    ap.add_argument("--retries", type=int, default=DEFAULT_RETRIES,
                    help="re-prompts with the validation errors when a draft is invalid")
    ap.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    ap.add_argument("--out-dir", type=Path, default=PROJECT_ROOT / "automation-proposals")
    ap.add_argument("--show-entities", action="store_true",
                    help="print what was put in the prompt")
    args = ap.parse_args()

    token = os.getenv("HOME_ASSISTANT_TOKEN")
    if not token:
        print("HOME_ASSISTANT_TOKEN is not set (looked in .env)", file=sys.stderr)
        return 1

    try:
        states = ha_get(args.base_url, token, "/api/states")
        services = ha_get(args.base_url, token, "/api/services")
    except (HTTPError, URLError, TimeoutError) as exc:
        print(f"could not reach Home Assistant at {args.base_url}: {exc}", file=sys.stderr)
        return 1

    print(f"Home Assistant: {len(states)} entities, {len(services)} service domains")
    if args.show_entities:
        for state in select_entities(states, args.request, args.entities):
            print(describe(state))

    try:
        draft = draft_automation(
            args.request, states, services,
            model=args.model, endpoint=args.endpoint, entities=args.entities,
            retries=args.retries, timeout=args.timeout,
            progress=lambda message: print(f"\n{message}"),
        )
    except AuthorError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except (HTTPError, URLError, TimeoutError) as exc:
        print(f"could not reach Ollama at {args.endpoint}: {exc}", file=sys.stderr)
        return 1

    print(f"showed the model {draft.entities_shown} entities")
    for problem in draft.problems:
        print(f"  invalid: {problem}")
    for hint in draft.hints:
        print(f"  suspect: {hint}")

    print(f"drafted in {draft.elapsed:.1f}s\n")
    print(draft.yaml_text)

    if draft.problems:
        print(f"VALIDATION FAILED after {draft.attempts} attempt(s):")
        for problem in draft.problems:
            print(f"  - {problem}")
        print("\nNot writing a proposal. Re-run, or say which entity you meant.")
        return 1

    print("validation: every entity and service exists in Home Assistant")

    if draft.hints:
        print("\nREVIEW HINTS - the draft is valid, but may not mean what you asked:")
        for hint in draft.hints:
            print(f"  - {hint}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    out = args.out_dir / f"{draft.slug()}.yaml"
    out.write_text(render_proposal(draft, args.model), encoding="utf-8")

    print(f"\nproposal written to {out}")
    print("It is not active. Review it, then install it from the dashboard, or")
    print("append it to automations.yaml and reload automations.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
