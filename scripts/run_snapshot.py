#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from longrun_web.bridge import longrun_lib  # noqa: E402


def tail(path: Path, lines: int = 120) -> list[str]:
    if not path.exists():
        return []
    data = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    return data[-lines:]


def main() -> int:
    parser = argparse.ArgumentParser(description="Emit a machine-readable LongRun run snapshot")
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--run-id", default="active")
    args = parser.parse_args()

    target = longrun_lib.resolve_run_target(args.workspace, args.run_id)
    status = longrun_lib.ensure_status_defaults(longrun_lib.read_json(longrun_lib.status_path(target), {}))
    status = longrun_lib.sync_operator_tasks(target, longrun_lib.refresh_artifact_inventory(target, status), checkpoint="snapshot")
    longrun_lib.write_json_atomic(longrun_lib.status_path(target), status)
    longrun_lib.sync_plan_markdown(target, status)

    payload = {
        "ok": True,
        "runId": target.run_id,
        "status": status,
        "mission": longrun_lib.read_text(target.run_dir / "mission.md", ""),
        "plan": longrun_lib.read_text(target.run_dir / "plan.md", ""),
        "completion": longrun_lib.read_text(longrun_lib.completion_path(target), "")
        or longrun_lib.read_text(longrun_lib.legacy_completion_path(target), ""),
        "journalTail": tail(longrun_lib.journal_path(target)),
        "hookTail": tail(longrun_lib.hook_events_path(target)),
        "artifacts": status.get("artifacts", []),
        "operatorTasks": status.get("operatorTasks", []),
        "sourcesCount": len([line for line in longrun_lib.read_text(longrun_lib.sources_path(target), "").splitlines() if line.strip()]),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
