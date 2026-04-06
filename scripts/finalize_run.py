#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
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


def display_status(status_name: str) -> str:
    mapping = {
        "complete": "已完成（COMPLETE）",
        "blocked": "已阻塞（BLOCKED）",
    }
    return mapping.get(status_name, status_name.upper())


def build_next_steps(status_name: str, delivered: list[str], verification_items: list[str], risks: list[str], recovery: list[str], blockers: list[str], evidence_file: Path | None) -> list[str]:
    steps: list[str] = []
    if status_name == "complete":
        if delivered:
            steps.append("先打开“交付内容”中的文件，快速确认结果是否符合你的预期。")
        else:
            steps.append("本次没有记录到交付内容；如果这不是你的预期，请先回看任务状态和日志。")
        if not verification_items:
            steps.append("本次没有记录到显式检查步骤；如果这是重要结果，建议补做一次人工抽查。")
        if risks:
            steps.append("处理“仍需注意”里的事项后，再决定是否发布、归档或交给他人继续使用。")
        else:
            steps.append("如果结果已经满足预期，可以归档本次任务，或继续发起下一轮任务。")
    else:
        steps.append("先处理“当前阻塞”中的问题，再决定下一步。")
        steps.append("处理完成后，可执行 `longrun-resume latest` 继续。")

    if recovery:
        steps.append("如需回看这次自动处理过什么，可查看“恢复与处理记录”。")
    if evidence_file and evidence_file.exists():
        steps.append("如需追溯参考来源或排查结论依据，请打开 `sources.jsonl`。")

    steps.append("查看当前状态：`longrun-status latest`")
    return steps


def build_completion_markdown(headline: str, status_name: str, delivered: list[str], verification_items: list[str], risks: list[str], recovery: list[str], blockers: list[str], evidence_file: Path | None) -> str:
    next_steps = build_next_steps(status_name, delivered, verification_items, risks, recovery, blockers, evidence_file)
    lines = [
        "# LongRun 结果摘要",
        "",
        f"状态：{display_status(status_name)}",
        "",
        "## 本次结论",
        f"- {headline}",
        "",
        "## 交付内容",
    ]
    if delivered:
        lines.extend(f"- `{item}`" for item in delivered)
    else:
        lines.append("- 本次没有记录到交付内容。")
    lines.extend(["", "## 已完成的检查"])
    if verification_items:
        lines.extend(f"- {item}" for item in verification_items)
    else:
        lines.append("- 本次没有记录到显式检查步骤。")
    lines.extend(["", "## 仍需注意"])
    if risks:
        lines.extend(f"- {item}" for item in risks)
    else:
        lines.append("- 当前没有额外风险记录。")
    lines.extend(["", "## 恢复与处理记录"])
    if recovery:
        lines.extend(f"- {item}" for item in recovery)
    else:
        lines.append("- 本次没有额外恢复记录。")
    if blockers:
        lines.extend(["", "## 当前阻塞"])
        lines.extend(f"- {item}" for item in blockers)
    lines.extend(["", "## 建议你下一步这样做"])
    lines.extend(f"- {item}" for item in next_steps)
    if evidence_file and evidence_file.exists():
        lines.extend(["", "## 证据与来源", f"- `sources.jsonl`：`{evidence_file}`"])
    return "\n".join(lines) + "\n"


def notify(run_target, event: str, *, title: str, subtitle: str, message: str, open_path: Path | None = None, sound: bool = False) -> None:
    helper = SCRIPT_DIR / "notify_macos.py"
    if not helper.exists():
        return
    cmd = [
        sys.executable,
        str(helper),
        "--workspace", str(run_target.workspace),
        "--run-id", run_target.run_id,
        "--event", event,
        "--title", title,
        "--subtitle", subtitle,
        "--message", message,
    ]
    if open_path:
        cmd.extend(["--open", str(open_path)])
    if sound:
        cmd.append("--sound")
    subprocess.run(cmd, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


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
        verification_items.append("本地校验：" + ("通过" if verification.get("ok") else "未通过"))
        for finding in verification.get("hardFailures", []):
            verification_items.append(f"严重问题：{finding}")
        for finding in verification.get("driftFindings", []):
            verification_items.append(f"状态漂移：{finding}")
        for finding in verification.get("softWarnings", []):
            verification_items.append(f"风险提示：{finding}")

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
        notify(
            target,
            "attention",
            title="LongRun 需要你回来看看",
            subtitle="有一项检查没有通过",
            message="任务还在，当前进度也已经保留下来了。",
            sound=True,
        )
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
    completion_file = completion_path(target)
    if args.status == "complete":
        notify(
            target,
            "complete",
            title="LongRun 已经完成了",
            subtitle="结果已经整理好了",
            message="点一下就能打开结果摘要。",
            open_path=completion_file if completion_file.exists() else None,
            sound=True,
        )
    else:
        notify(
            target,
            "blocked",
            title="LongRun 暂时停住了",
            subtitle="需要你补一个决定或输入",
            message="点一下查看当前情况，再决定下一步。",
            open_path=completion_file if completion_file.exists() else None,
            sound=True,
        )
    if args.do_print:
        print(json.dumps(updated, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
