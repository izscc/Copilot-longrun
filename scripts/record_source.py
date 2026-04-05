#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from _longrun_lib import append_jsonl, now_iso, read_text, resolve_run_target, sources_path, stable_source_id  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Record a research source for LongRun")
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--run-id", default="active")
    parser.add_argument("--title", required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--kind", default="web")
    parser.add_argument("--used-in", required=True)
    parser.add_argument("--source-id")
    args = parser.parse_args()

    target = resolve_run_target(args.workspace, args.run_id)
    payload = {
        "id": args.source_id or stable_source_id(args.url, args.title),
        "title": args.title,
        "url": args.url,
        "kind": args.kind,
        "capturedAt": now_iso(),
        "usedIn": args.used_in,
    }
    existing = set()
    src_path = sources_path(target)
    for line in read_text(src_path, "").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        key = (obj.get("id"), obj.get("url"), obj.get("usedIn"))
        existing.add(key)
    key = (payload["id"], payload["url"], payload["usedIn"])
    if key not in existing:
        append_jsonl(src_path, payload)
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
