#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from _longrun_lib import read_json, resolve_run_target, status_path, sync_plan_markdown  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description='Sync LongRun plan.md managed status board')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--run-id', default='active')
    parser.add_argument('--print', action='store_true', dest='do_print')
    args = parser.parse_args()

    target = resolve_run_target(args.workspace, args.run_id)
    status = read_json(status_path(target), {})
    path = sync_plan_markdown(target, status)
    if args.do_print:
        print(json.dumps({'ok': True, 'plan': str(path), 'runId': target.run_id}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
