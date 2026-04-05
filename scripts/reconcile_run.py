#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from _longrun_lib import (  # noqa: E402
    clear_active_run_if_matches,
    ensure_status_defaults,
    infer_completed_workstreams,
    local_verify,
    now_iso,
    read_json,
    refresh_artifact_inventory,
    resolve_run_target,
    status_path,
    sync_plan_markdown,
    write_json_atomic,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Reconcile LongRun run state with existing artifacts")
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--run-id", default="active")
    parser.add_argument("--print", action="store_true", dest="do_print")
    args = parser.parse_args()

    target = resolve_run_target(args.workspace, args.run_id)
    current = ensure_status_defaults(read_json(status_path(target), {}))
    updated = refresh_artifact_inventory(target, current)

    updated["completedWorkstreams"] = infer_completed_workstreams(target, updated)
    if updated.get("state") in {"complete", "blocked"}:
        updated["activeWorkstreams"] = []
        clear_active_run_if_matches(target)
    else:
        active = [str(item) for item in updated.get("activeWorkstreams") or [] if item]
        updated["activeWorkstreams"] = [item for item in active if item not in updated["completedWorkstreams"]]

    sync_plan_markdown(target, updated)
    verification = local_verify(target, status_override=updated)
    updated["verification"] = {
        "state": "passed" if verification.get("ok") else "failed",
        "hardFailures": verification.get("hardFailures", []),
        "softWarnings": verification.get("softWarnings", []),
        "driftFindings": verification.get("driftFindings", []),
        "recommendedAction": verification.get("recommendedAction"),
        "failureClass": verification.get("failureClass"),
        "lastVerifiedAt": now_iso(),
    }
    recovery = updated.get("recoveryState") or {}
    recovery["failureClass"] = verification.get("failureClass")
    recovery["lastRecommendedAction"] = verification.get("recommendedAction")
    updated["recoveryState"] = recovery
    updated["reconciledAt"] = now_iso()
    updated["updatedAt"] = now_iso()

    write_json_atomic(status_path(target), updated)

    result = {
        "ok": True,
        "runId": target.run_id,
        "verification": updated.get("verification"),
        "completedWorkstreams": updated.get("completedWorkstreams"),
        "artifacts": len(updated.get("artifacts") or []),
    }
    if args.do_print:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
