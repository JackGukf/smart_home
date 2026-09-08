#!/usr/bin/env python3
"""Write the morning digest of the house.

Python computes the figures and decides which of them are worth saying. That
short list of notes *is* the digest, and it needs no model at all.

Run it by hand to see what it would say:

    python3 scripts/house_digest.py --print

and on a schedule from house-digest.timer, which fires at 04:00.

`--prose` additionally asks the local model to reword the notes into a
paragraph. It is off by default because Qwen3-4B cannot currently do it -
src/python/house_digest.py records the four ways it failed - and because the
notes are already the briefing.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.python.house_digest import (  # noqa: E402
    DEFAULT_ENDPOINT,
    DEFAULT_MODEL,
    build_digest,
    gather_facts,
    write_digest,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIGEST_PATH = PROJECT_ROOT / "house_digest.json"
DEFAULT_HISTORY_PATH = PROJECT_ROOT / "house_digest.jsonl"
DEFAULT_MOTION_LOG = PROJECT_ROOT / "motion_log.jsonl"
DEFAULT_RESOURCE_LOG = Path.home() / "resource-history.log"


def load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def ha_states(base_url: str, token: str) -> list[dict]:
    from urllib.request import Request, urlopen
    request = Request(f"{base_url.rstrip('/')}/api/states",
                      headers={"Authorization": f"Bearer {token}"})
    with urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    load_dotenv(PROJECT_ROOT / ".env")
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base-url", default=os.getenv("HOME_ASSISTANT_BASE_URL",
                                                    "http://127.0.0.1:8123"))
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    ap.add_argument("--motion-log", type=Path, default=DEFAULT_MOTION_LOG)
    ap.add_argument("--resource-log", type=Path, default=DEFAULT_RESOURCE_LOG)
    ap.add_argument("--out", type=Path, default=DEFAULT_DIGEST_PATH)
    ap.add_argument("--history", type=Path, default=DEFAULT_HISTORY_PATH)
    ap.add_argument("--window-hours", type=int, default=24)
    ap.add_argument("--timeout", type=float, default=300.0)
    ap.add_argument("--prose", action="store_true",
                    help="also ask the local model to write a summary. Off by "
                         "default: Qwen3-4B cannot currently do this job (see "
                         "src/python/house_digest.py), and the computed notes "
                         "are the digest.")
    ap.add_argument("--print", dest="show", action="store_true",
                    help="print the digest as well as writing it")
    args = ap.parse_args()

    token = os.getenv("HOME_ASSISTANT_TOKEN")
    if not token:
        print("HOME_ASSISTANT_TOKEN is not set (looked in .env)", file=sys.stderr)
        return 1

    try:
        states = ha_states(args.base_url, token)
    except (HTTPError, URLError, TimeoutError) as exc:
        print(f"could not reach Home Assistant at {args.base_url}: {exc}", file=sys.stderr)
        return 1

    facts = gather_facts(states, args.motion_log, args.resource_log,
                         window_hours=args.window_hours)
    digest = build_digest(facts, endpoint=args.endpoint, model=args.model,
                          timeout=args.timeout, with_prose=args.prose)
    write_digest(digest, args.out, args.history)

    if args.show:
        print(digest["facts_text"])
        print()
        print("--- the briefing ---")
        for note in digest["notes"]:
            print(f"  - {note}")
        print()
        if digest["summary"]:
            print(f"--- {args.model} ---")
            print(digest["summary"])
        elif digest["error"]:
            print(f"(no prose: {digest['error']})")

    print(f"\ndigest written to {args.out}", file=sys.stderr)
    # A digest with facts and no prose is a success: the model is the optional
    # part. Only a failure to produce anything is worth a non-zero exit.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
