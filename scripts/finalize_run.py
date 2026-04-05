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
    final_summary_path,
    local_verify,
    now_iso,
    plan_sync_findings,
    read_json,
    resolve_run_target,
    sources_path,
    status_path,
    sync_plan_markdown,
    write_json_atomic,
    write_text_atomic,
)


def coerce_list(values):
    result = []
    for value in values or []:
        if value:
            result.append(value)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Finalize a LongRun mission")
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--run-id", default="active")
    parser.add_argument("--status", choices=["complete", "blocked"], required=True)
    parser.add_argument("--headline", required=True)
    parser.add_argument("--delivered-artifact", action="append", default=[])
    parser.add_argument("--verification-item", action="append", default=[])
    parser.add_argument("--risk", action="append", default=[])
    parser.add_argument("--recovery-note", action="append", default=[])
    parser.add_argument("--blocker", action="append", default=[])
    parser.add_argument("--local-verify", action="store_true")
    parser.add_argument("--print", action="store_true", dest="do_print")
    args = parser.parse_args()

    target = resolve_run_target(args.workspace, args.run_id)
    status_file = status_path(target)
    current = read_json(status_file, {})
    verification = local_verify(target) if args.local_verify else {"ok": True, "deliverables": [], "findings": []}

    delivered = coerce_list(args.delivered_artifact) or list(current.get("deliverables") or []) or verification.get("deliverables", [])
    verification_items = coerce_list(args.verification_item)
    if args.local_verify:
        verification_items.append(
            "local verification: " + ("passed" if verification.get("ok") else "failed")
        )
        for finding in verification.get("findings", []):
            verification_items.append(f"local verification note: {finding}")

    lines = [
        "# Final Summary",
        "",
        f"Status: {args.status.upper()}",
        "",
        "## Outcome",
        f"- {args.headline}",
        "",
        "## Delivered Artifacts",
    ]
    if delivered:
        lines.extend(f"- `{item}`" for item in delivered)
    else:
        lines.append("- None recorded")
    lines.extend(["", "## Verification Performed"])
    if verification_items:
        lines.extend(f"- {item}" for item in verification_items)
    else:
        lines.append("- No explicit verification steps recorded")
    lines.extend(["", "## Remaining Risks / Follow-ups"])
    risks = coerce_list(args.risk)
    if risks:
        lines.extend(f"- {item}" for item in risks)
    else:
        lines.append("- None")
    lines.extend(["", "## Recovery Decisions"])
    recovery = coerce_list(args.recovery_note)
    if recovery:
        lines.extend(f"- {item}" for item in recovery)
    else:
        lines.append("- None")
    blockers = coerce_list(args.blocker)
    if blockers:
        lines.extend(["", "## Blockers"])
        lines.extend(f"- {item}" for item in blockers)
    src_file = sources_path(target)
    if src_file.exists():
        lines.extend(["", "## Evidence Trail", f"- `sources.jsonl`: `{src_file}`"])

    write_text_atomic(final_summary_path(target), "\n".join(lines) + "\n")

    updated = dict(current)
    updated["state"] = args.status
    updated["phase"] = "finalize"
    updated["summary"] = args.headline
    updated["deliverables"] = delivered
    updated["activeWorkstreams"] = []
    updated["updatedAt"] = now_iso()
    updated["completedAt"] = now_iso()
    if args.status == "blocked":
        updated["lastError"] = updated.get("lastError") or {"message": "; ".join(blockers) if blockers else args.headline}
    write_json_atomic(status_file, updated)
    sync_plan_markdown(target, updated)
    clear_active_run_if_matches(target)
    plan_findings = plan_sync_findings(target, updated)
    if plan_findings and args.status == "complete":
        updated["lastError"] = {"message": "; ".join(plan_findings)}
        write_json_atomic(status_file, updated)
    if args.do_print:
        print(json.dumps(updated, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
