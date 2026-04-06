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
    completion_path,
    ensure_status_defaults,
    local_verify,
    now_iso,
    read_json,
    refresh_artifact_inventory,
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


def build_completion_markdown(headline: str, status_name: str, delivered: list[str], verification_items: list[str], risks: list[str], recovery: list[str], blockers: list[str], evidence_file: Path | None) -> str:
    lines = [
        "# LongRun Completion",
        "",
        f"Status: {status_name.upper()}",
        "",
        "## Outcome",
        f"- {headline}",
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
    if risks:
        lines.extend(f"- {item}" for item in risks)
    else:
        lines.append("- None")
    lines.extend(["", "## Recovery Decisions"])
    if recovery:
        lines.extend(f"- {item}" for item in recovery)
    else:
        lines.append("- None")
    if blockers:
        lines.extend(["", "## Blockers"])
        lines.extend(f"- {item}" for item in blockers)
    if evidence_file and evidence_file.exists():
        lines.extend(["", "## Evidence Trail", f"- `sources.jsonl`: `{evidence_file}`"])
    return "\n".join(lines) + "\n"


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
    parser.add_argument("--force-complete", action="store_true")
    parser.add_argument("--print", action="store_true", dest="do_print")
    args = parser.parse_args()

    target = resolve_run_target(args.workspace, args.run_id)
    status_file = status_path(target)
    current = ensure_status_defaults(read_json(status_file, {}))

    delivered = coerce_list(args.delivered_artifact) or list(current.get("deliverables") or [])
    provisional = dict(current)
    provisional["state"] = args.status
    provisional["phase"] = "finalize"
    provisional["summary"] = args.headline
    provisional["deliverables"] = delivered
    provisional = refresh_artifact_inventory(target, provisional)

    verification = local_verify(target, status_override=provisional, finalize_candidate=True) if args.local_verify else {
        "ok": True,
        "deliverables": [],
        "hardFailures": [],
        "softWarnings": [],
        "driftFindings": [],
        "recommendedAction": "continue",
        "failureClass": None,
    }

    verification_items = coerce_list(args.verification_item)
    if args.local_verify:
        verification_items.append("local verification: " + ("passed" if verification.get("ok") else "failed"))
        for finding in verification.get("hardFailures", []):
            verification_items.append(f"hard failure: {finding}")
        for finding in verification.get("driftFindings", []):
            verification_items.append(f"drift finding: {finding}")
        for finding in verification.get("softWarnings", []):
            verification_items.append(f"soft warning: {finding}")

    risks = coerce_list(args.risk)
    recovery = coerce_list(args.recovery_note)
    blockers = coerce_list(args.blocker)

    if args.status == "complete" and args.local_verify and not verification.get("ok") and not args.force_complete:
        failed = refresh_artifact_inventory(target, current)
        failed["phase"] = "verify"
        failed["summary"] = current.get("summary") or args.headline
        failed["verification"] = {
            "state": "failed",
            "hardFailures": verification.get("hardFailures", []),
            "softWarnings": verification.get("softWarnings", []),
            "driftFindings": verification.get("driftFindings", []),
            "recommendedAction": verification.get("recommendedAction"),
            "failureClass": verification.get("failureClass"),
            "lastVerifiedAt": now_iso(),
        }
        failed_recovery = failed.get("recoveryState") or {}
        failed_recovery["failureClass"] = verification.get("failureClass")
        failed_recovery["lastRecommendedAction"] = verification.get("recommendedAction")
        failed_recovery["retryCount"] = int(failed_recovery.get("retryCount") or 0) + 1
        failed["recoveryState"] = failed_recovery
        failed["updatedAt"] = now_iso()
        write_json_atomic(status_file, failed)
        sync_plan_markdown(target, failed)
        if args.do_print:
            print(json.dumps(failed, ensure_ascii=False, indent=2))
        return 1

    updated = refresh_artifact_inventory(target, provisional)
    updated["state"] = args.status
    updated["phase"] = "finalize"
    updated["summary"] = args.headline
    updated["deliverables"] = delivered or verification.get("deliverables", [])
    updated["completedWorkstreams"] = list(updated.get("completedWorkstreams") or [])
    updated["activeWorkstreams"] = []
    updated["verification"] = {
        "state": "passed" if verification.get("ok") else "failed",
        "hardFailures": verification.get("hardFailures", []),
        "softWarnings": verification.get("softWarnings", []),
        "driftFindings": verification.get("driftFindings", []),
        "recommendedAction": verification.get("recommendedAction"),
        "failureClass": verification.get("failureClass"),
        "lastVerifiedAt": now_iso() if args.local_verify else updated.get("verification", {}).get("lastVerifiedAt"),
    }
    updated["finalizationMode"] = "forced" if args.force_complete and args.status == "complete" else "normal"
    updated["updatedAt"] = now_iso()
    updated["completedAt"] = now_iso()
    recovery_state = updated.get("recoveryState") or {}
    recovery_state["failureClass"] = verification.get("failureClass")
    recovery_state["lastRecommendedAction"] = verification.get("recommendedAction")
    updated["recoveryState"] = recovery_state
    if args.status == "blocked":
        updated["lastError"] = updated.get("lastError") or {"message": "; ".join(blockers) if blockers else args.headline}

    evidence_file = sources_path(target)
    completion_text = build_completion_markdown(
        headline=args.headline,
        status_name=args.status,
        delivered=updated.get("deliverables") or [],
        verification_items=verification_items,
        risks=risks,
        recovery=recovery,
        blockers=blockers,
        evidence_file=evidence_file,
    )
    write_text_atomic(completion_path(target), completion_text)
    write_json_atomic(status_file, updated)
    sync_plan_markdown(target, updated)
    clear_active_run_if_matches(target)
    if args.do_print:
        print(json.dumps(updated, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
