#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from _longrun_lib import append_jsonl, journal_path, now_iso, resolve_run_target  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Append a business journal entry to LongRun state")
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--run-id", default="active")
    parser.add_argument("--phase", required=True)
    parser.add_argument("--actor", required=True)
    parser.add_argument("--action", required=True)
    parser.add_argument("--result", required=True)
    parser.add_argument("--next", required=True)
    parser.add_argument("--details")
    parser.add_argument("--extra-json")
    args = parser.parse_args()

    target = resolve_run_target(args.workspace, args.run_id)
    payload = {
        "ts": now_iso(),
        "phase": args.phase,
        "actor": args.actor,
        "action": args.action,
        "result": args.result,
        "next": args.next,
    }
    if args.details:
        payload["details"] = args.details
    if args.extra_json:
        payload.update(json.loads(args.extra_json))
    append_jsonl(journal_path(target), payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
