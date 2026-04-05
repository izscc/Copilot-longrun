#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from _longrun_lib import (  # noqa: E402
    LongRunError,
    ensure_dir,
    init_status_payload,
    now_iso,
    parse_json_argument,
    read_json,
    resolve_run_target,
    status_path,
    shallow_merge,
    sync_plan_markdown,
    write_json_atomic,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Atomic LongRun status writer")
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--run-id", default="active")
    parser.add_argument("--replace-json")
    parser.add_argument("--patch-json")
    parser.add_argument("--init-from-prompt")
    parser.add_argument("--explicit-model")
    parser.add_argument("--session-model")
    parser.add_argument("--model-control-mode")
    parser.add_argument("--print", action="store_true", dest="do_print")
    args = parser.parse_args()

    try:
        target = resolve_run_target(args.workspace, args.run_id)
    except LongRunError:
        if not args.run_id or args.run_id in {"active", "latest"}:
            raise
        target = resolve_run_target(args.workspace, args.run_id)

    ensure_dir(target.run_dir)
    path = status_path(target)
    if args.replace_json:
        payload = parse_json_argument(args.replace_json, {})
    elif args.init_from_prompt:
        payload = init_status_payload(
            target.run_id,
            args.init_from_prompt,
            explicit_model=args.explicit_model,
            session_model=args.session_model or os.environ.get("LONGRUN_SELECTED_MODEL"),
            model_control_mode=args.model_control_mode or os.environ.get("LONGRUN_MODEL_CONTROL_MODE"),
        )
    else:
        current = read_json(path, {})
        patch = parse_json_argument(args.patch_json, {})
        payload = shallow_merge(current, patch)
    payload["runId"] = target.run_id
    payload["updatedAt"] = now_iso()
    write_json_atomic(path, payload)
    sync_plan_markdown(target, payload)
    if args.do_print:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
