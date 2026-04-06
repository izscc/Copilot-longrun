#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from _longrun_lib import read_json, read_text  # noqa: E402

SAMPLE_RUN = Path("/Users/zscc.in/Desktop/AI/Claudecode-thinking/.copilot-mission-control/runs/20260405-071402-claude-code-book")


def run_cmd(*args: str, ok: bool = True) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        [sys.executable, *args],
        text=True,
        capture_output=True,
    )
    if ok and completed.returncode != 0:
        raise AssertionError(
            f"command failed ({completed.returncode}): {' '.join(args)}\nSTDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}"
        )
    return completed


def setup_run(temp_root: Path, name: str, run_id: str) -> tuple[Path, Path, Path]:
    workspace = temp_root / name
    run_dir = workspace / ".copilot-mission-control" / "runs" / run_id
    state_dir = workspace / ".copilot-mission-control" / "state"
    run_dir.mkdir(parents=True, exist_ok=True)
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "active-run-id").write_text(run_id, encoding="utf-8")
    (state_dir / "latest-run-id").write_text(run_id, encoding="utf-8")
    return workspace, run_dir, state_dir


def test_prepare_run_allocates_fresh_timestamped_runs(temp_root: Path) -> None:
    workspace = temp_root / "prepare-workspace"
    workspace.mkdir(parents=True, exist_ok=True)

    first = run_cmd(
        str(SCRIPT_DIR / "prepare_run.py"),
        "--workspace", str(workspace),
        "--task", "发布 iCopilot v1 并上传 release artifact",
        "--session-model", "claude-opus-4.6",
        "--model-control-mode", "launcher-enforced",
        "--launcher-mode", "launcher-preallocated",
        "--print-json",
    )
    first_result = json.loads(first.stdout)
    first_run_id = first_result["runId"]
    assert re.match(r"^\d{8}-\d{6}-[a-z0-9-]+$", first_run_id)
    assert (workspace / ".copilot-mission-control" / "runs" / first_run_id / "mission.md").exists()

    second = run_cmd(
        str(SCRIPT_DIR / "prepare_run.py"),
        "--workspace", str(workspace),
        "--task", "发布 iCopilot v1 并上传 release artifact",
        "--session-model", "claude-opus-4.6",
        "--model-control-mode", "launcher-enforced",
        "--launcher-mode", "launcher-preallocated",
        "--print-json",
    )
    second_result = json.loads(second.stdout)
    second_run_id = second_result["runId"]
    assert second_run_id != first_run_id

    state_dir = workspace / ".copilot-mission-control" / "state"
    assert read_text(state_dir / "active-run-id", "").strip() == second_run_id
    assert read_text(state_dir / "latest-run-id", "").strip() == second_run_id

    second_status = read_json(workspace / ".copilot-mission-control" / "runs" / second_run_id / "status.json", {})
    assert second_status.get("launcherMode") == "launcher-preallocated"
    assert second_status.get("modelControlMode") == "launcher-enforced"
    assert second_status.get("selectedModel") == "claude-opus-4.6"


def test_notify_helper_dry_run(temp_root: Path) -> None:
    workspace, run_dir, _state_dir = setup_run(temp_root, "notify-workspace", "20990101-000004-notify")
    board = workspace / f"LONGRUN-启动看板-{run_dir.name}.md"
    board.write_text("# LongRun 启动看板\n", encoding="utf-8")
    completion = run_dir / "COMPLETION.md"
    completion.write_text("# done\n", encoding="utf-8")

    launched = run_cmd(
        str(SCRIPT_DIR / "notify_macos.py"),
        "--workspace", str(workspace),
        "--run-id", run_dir.name,
        "--event", "launched",
        "--dry-run",
    )
    launched_result = json.loads(launched.stdout)
    assert launched_result["backend"] in {"terminal-notifier", "osascript", "none"}

    complete = run_cmd(
        str(SCRIPT_DIR / "notify_macos.py"),
        "--workspace", str(workspace),
        "--run-id", run_dir.name,
        "--event", "complete",
        "--dry-run",
    )
    complete_result = json.loads(complete.stdout)
    assert complete_result["backend"] in {"terminal-notifier", "osascript", "none"}


def test_finalize_gate_and_force_complete(temp_root: Path) -> None:
    workspace, run_dir, state_dir = setup_run(temp_root, "gate-workspace", "20990101-000001-gate")
    reports_dir = workspace / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "runId": run_dir.name,
        "state": "running",
        "phase": "execute",
        "profile": "coding",
        "language": "zh-CN",
        "summary": "gate test",
        "deliverables": ["reports/missing.md"],
        "completedWorkstreams": [],
        "activeWorkstreams": ["implementation"],
        "selectedModel": "session-inherited",
        "modelControlMode": "session-inherited",
        "fallbackChain": [],
        "recoveryState": {"phaseAttempts": {}},
    }
    run_cmd(str(SCRIPT_DIR / "write_status.py"), "--workspace", str(workspace), "--run-id", run_dir.name, "--replace-json", json.dumps(payload, ensure_ascii=False))

    first = run_cmd(
        str(SCRIPT_DIR / "finalize_run.py"),
        "--workspace", str(workspace),
        "--run-id", run_dir.name,
        "--status", "complete",
        "--headline", "gate should fail",
        "--local-verify",
        ok=False,
    )
    if first.returncode == 0:
        raise AssertionError("finalize without force should fail when local verification fails")

    status = read_json(run_dir / "status.json", {})
    assert status.get("state") == "running"
    assert status.get("phase") == "verify"
    assert status.get("verification", {}).get("state") == "failed"
    assert (run_dir / "COMPLETION.md").exists() is False
    assert read_text(state_dir / "active-run-id", "").strip() == run_dir.name

    forced = run_cmd(
        str(SCRIPT_DIR / "finalize_run.py"),
        "--workspace", str(workspace),
        "--run-id", run_dir.name,
        "--status", "complete",
        "--headline", "forced complete",
        "--local-verify",
        "--force-complete",
    )
    assert forced.returncode == 0

    status = read_json(run_dir / "status.json", {})
    assert status.get("state") == "complete"
    assert status.get("finalizationMode") == "forced"
    assert status.get("verification", {}).get("state") == "failed"
    assert (run_dir / "COMPLETION.md").exists()
    assert read_text(state_dir / "active-run-id", "").strip() == ""


def test_complete_requires_deliverables_and_task_list(temp_root: Path) -> None:
    workspace, run_dir, state_dir = setup_run(temp_root, "tasklist-workspace", "20990101-000003-tasklist")
    (workspace / "reports").mkdir(parents=True, exist_ok=True)
    (workspace / "task-list.md").write_text(
        "# Task List\n\n- [x] Explore\n- [ ] Final verification\n",
        encoding="utf-8",
    )

    payload = {
        "runId": run_dir.name,
        "state": "running",
        "phase": "verify",
        "profile": "coding",
        "language": "zh-CN",
        "summary": "task list gate",
        "deliverables": [],
        "completedWorkstreams": ["explore", "plan", "execute"],
        "activeWorkstreams": [],
        "selectedModel": "session-inherited",
        "modelControlMode": "session-inherited",
        "fallbackChain": [],
        "recoveryState": {"phaseAttempts": {}},
    }
    run_cmd(str(SCRIPT_DIR / "write_status.py"), "--workspace", str(workspace), "--run-id", run_dir.name, "--replace-json", json.dumps(payload, ensure_ascii=False))

    failed = run_cmd(
        str(SCRIPT_DIR / "finalize_run.py"),
        "--workspace", str(workspace),
        "--run-id", run_dir.name,
        "--status", "complete",
        "--headline", "should fail on empty deliverables and unchecked task list",
        "--local-verify",
        ok=False,
    )
    assert failed.returncode != 0
    status = read_json(run_dir / "status.json", {})
    findings = status.get("verification", {}).get("driftFindings", []) + status.get("verification", {}).get("hardFailures", [])
    assert any("deliverables is empty" in item for item in findings)
    assert any("task-list.md has unchecked required items" in item for item in findings)
    assert read_text(state_dir / "active-run-id", "").strip() == run_dir.name

    (workspace / "task-list.md").write_text(
        "# Task List\n\n- [x] Explore\n- [x] Final verification\n",
        encoding="utf-8",
    )
    (workspace / "reports" / "done.md").write_text("# done\n", encoding="utf-8")
    run_cmd(
        str(SCRIPT_DIR / "write_status.py"),
        "--workspace", str(workspace),
        "--run-id", run_dir.name,
        "--patch-json",
        json.dumps({"deliverables": ["reports/done.md"]}, ensure_ascii=False),
    )
    succeeded = run_cmd(
        str(SCRIPT_DIR / "finalize_run.py"),
        "--workspace", str(workspace),
        "--run-id", run_dir.name,
        "--status", "complete",
        "--headline", "task list and deliverables satisfied",
        "--local-verify",
    )
    assert succeeded.returncode == 0
    status = read_json(run_dir / "status.json", {})
    assert status.get("state") == "complete"
    assert status.get("deliverables") == ["reports/done.md"]
    assert read_text(state_dir / "active-run-id", "").strip() == ""


def test_reconcile_harvest_and_naming(temp_root: Path) -> None:
    workspace, run_dir, state_dir = setup_run(temp_root, "reconcile-workspace", "20990101-000002-reconcile")
    artifacts_dir = run_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "任务总览.md").write_text(
        "# 任务总览\n\n来源一：https://example.com/report\n\n参考代码：`scripts/_longrun_lib.py`\n",
        encoding="utf-8",
    )
    (artifacts_dir / "最终总结.md").write_text("# 最终总结\n\n已完成。\n", encoding="utf-8")
    (run_dir / "final-summary.md").write_text("# legacy summary\n", encoding="utf-8")

    run_cmd(
        str(SCRIPT_DIR / "write_status.py"),
        "--workspace", str(workspace),
        "--run-id", run_dir.name,
        "--init-from-prompt", "请调研 GitHub Copilot CLI LongRun 的设计并生成中文总结",
    )
    run_cmd(
        str(SCRIPT_DIR / "write_status.py"),
        "--workspace", str(workspace),
        "--run-id", run_dir.name,
        "--patch-json",
        json.dumps(
            {
                "state": "complete",
                "phase": "finalize",
                "deliverables": ["artifacts/最终总结.md", "final-summary.md"],
                "activeWorkstreams": ["draft"],
                "completedWorkstreams": [],
            },
            ensure_ascii=False,
        ),
    )

    plan_file = run_dir / "plan.md"
    plan_file.write_text(
        read_text(plan_file, "")
        + "\n## LongRun Status Board\n\n| Key | Value |\n| --- | --- |\n| State | running |\n\n- [ ] Finalize\n",
        encoding="utf-8",
    )
    (state_dir / "active-run-id").write_text(run_dir.name, encoding="utf-8")

    harvest = run_cmd(str(SCRIPT_DIR / "harvest_sources.py"), "--workspace", str(workspace), "--run-id", run_dir.name)
    harvest_result = json.loads(harvest.stdout)
    assert harvest_result["added"] >= 1

    run_cmd(str(SCRIPT_DIR / "reconcile_run.py"), "--workspace", str(workspace), "--run-id", run_dir.name)
    verify = run_cmd(str(SCRIPT_DIR / "verify_run.py"), "--workspace", str(workspace), "--run-id", run_dir.name, "--json")
    verify_result = json.loads(verify.stdout)

    status = read_json(run_dir / "status.json", {})
    plan = read_text(plan_file, "")
    sources_count = len([line for line in read_text(run_dir / "sources.jsonl", "").splitlines() if line.strip()])

    assert status.get("naming", {}).get("defaultLocale") == "zh-CN"
    assert status.get("naming", {}).get("defaultVisibleNameStyle") == "简体中文"
    assert any(item.get("displayName") == "任务总览" for item in status.get("artifacts", []))
    assert status.get("completedWorkstreams")
    assert status.get("verification", {}).get("state") == "passed"
    assert verify_result.get("ok") is True
    assert sources_count >= 1
    assert "duplicate unmanaged status sections" not in plan
    assert "| State | running |" not in plan
    assert read_text(state_dir / "active-run-id", "").strip() == ""


def test_historical_run_regression(temp_root: Path) -> None:
    if not SAMPLE_RUN.exists():
        print("historical regression: skipped (sample run not found)")
        return

    workspace = temp_root / "historical-workspace"
    state_dir = workspace / ".copilot-mission-control" / "state"
    runs_dir = workspace / ".copilot-mission-control" / "runs"
    state_dir.mkdir(parents=True, exist_ok=True)
    runs_dir.mkdir(parents=True, exist_ok=True)

    target_run = runs_dir / SAMPLE_RUN.name
    shutil.copytree(SAMPLE_RUN, target_run)
    (state_dir / "active-run-id").write_text(SAMPLE_RUN.name, encoding="utf-8")
    (state_dir / "latest-run-id").write_text(SAMPLE_RUN.name, encoding="utf-8")

    before_sources = len([line for line in read_text(target_run / "sources.jsonl", "").splitlines() if line.strip()])
    run_cmd(str(SCRIPT_DIR / "harvest_sources.py"), "--workspace", str(workspace), "--run-id", SAMPLE_RUN.name)
    run_cmd(str(SCRIPT_DIR / "reconcile_run.py"), "--workspace", str(workspace), "--run-id", SAMPLE_RUN.name)
    verify = run_cmd(str(SCRIPT_DIR / "verify_run.py"), "--workspace", str(workspace), "--run-id", SAMPLE_RUN.name, "--json")
    verify_result = json.loads(verify.stdout)

    status = read_json(target_run / "status.json", {})
    plan = read_text(target_run / "plan.md", "")
    after_sources = len([line for line in read_text(target_run / "sources.jsonl", "").splitlines() if line.strip()])

    assert after_sources > before_sources
    assert status.get("completedWorkstreams")
    assert "## LongRun Status Board" in plan
    assert "| State | running |" not in plan
    assert verify_result.get("ok") is True
    assert read_text(state_dir / "active-run-id", "").strip() == ""


def main() -> int:
    temp_root = Path(tempfile.mkdtemp(prefix="longrun-selftest-"))
    try:
        test_prepare_run_allocates_fresh_timestamped_runs(temp_root)
        test_notify_helper_dry_run(temp_root)
        test_finalize_gate_and_force_complete(temp_root)
        test_complete_requires_deliverables_and_task_list(temp_root)
        test_reconcile_harvest_and_naming(temp_root)
        test_historical_run_regression(temp_root)
        print("selftest: ok")
        return 0
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
