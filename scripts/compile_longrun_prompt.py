#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from longrun_web.compiler import compile_prompt  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Compile LongRun prompt into structured JSON output")
    parser.add_argument("--text", required=True)
    parser.add_argument("--interaction", default="initial_compile")
    parser.add_argument("--ai-profile")
    parser.add_argument("--pack-version", default="v1")
    parser.add_argument("--previous-json")
    args = parser.parse_args()

    previous = json.loads(args.previous_json) if args.previous_json else None
    result = compile_prompt(
        args.text,
        previous_draft=previous,
        interaction=args.interaction,
        profile_name=args.ai_profile,
        pack_version=args.pack_version,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
