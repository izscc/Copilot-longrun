#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from _longrun_lib import local_verify, resolve_run_target  # noqa: E402
from _longrun_lib import ensure_status_defaults, now_iso, read_json, status_path, sync_operator_tasks, sync_plan_markdown, write_json_atomic  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description='Verify LongRun run state and deliverables')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--run-id', default='active')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()

    target = resolve_run_target(args.workspace, args.run_id)
    current = ensure_status_defaults(read_json(status_path(target), {}))
    current = sync_operator_tasks(target, current, checkpoint="verify")
    result = local_verify(target, status_override=current)
    current["verification"] = {
        "state": "passed" if result.get("ok") else "failed",
        "hardFailures": result.get("hardFailures", []),
        "softWarnings": result.get("softWarnings", []),
        "driftFindings": result.get("driftFindings", []),
        "recommendedAction": result.get("recommendedAction"),
        "failureClass": result.get("failureClass"),
        "lastVerifiedAt": now_iso(),
    }
    write_json_atomic(status_path(target), current)
    sync_plan_markdown(target, current)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print('OK' if result.get('ok') else 'FAIL')
        for item in result.get('deliverables', []):
            print(f'deliverable: {item}')
        for finding in result.get('hardFailures', []):
            print(f'hard-failure: {finding}')
        for finding in result.get('driftFindings', []):
            print(f'drift-finding: {finding}')
        for finding in result.get('softWarnings', []):
            print(f'soft-warning: {finding}')
        if result.get('recommendedAction'):
            print(f"recommended-action: {result.get('recommendedAction')}")
    return 0 if result.get('ok') else 1


if __name__ == '__main__':
    raise SystemExit(main())
