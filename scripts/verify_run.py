#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from _longrun_lib import local_verify, resolve_run_target  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description='Verify LongRun run state and deliverables')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--run-id', default='active')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()

    target = resolve_run_target(args.workspace, args.run_id)
    result = local_verify(target)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print('OK' if result.get('ok') else 'FAIL')
        for item in result.get('deliverables', []):
            print(f'deliverable: {item}')
        for finding in result.get('findings', []):
            print(f'finding: {finding}')
    return 0 if result.get('ok') else 1


if __name__ == '__main__':
    raise SystemExit(main())
