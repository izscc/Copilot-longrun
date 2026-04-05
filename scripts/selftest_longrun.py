#!/usr/bin/env python3
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from _longrun_lib import read_json, read_text  # noqa: E402


def main() -> int:
    temp_root = Path(tempfile.mkdtemp(prefix="longrun-selftest-"))
    try:
        workspace = temp_root / "workspace"
        run_id = "20990101-000000-selftest"
        run_dir = workspace / ".copilot-mission-control" / "runs" / run_id
        state_dir = workspace / ".copilot-mission-control" / "state"
        run_dir.mkdir(parents=True, exist_ok=True)
        state_dir.mkdir(parents=True, exist_ok=True)
        (state_dir / "active-run-id").write_text(run_id, encoding="utf-8")
        (state_dir / "latest-run-id").write_text(run_id, encoding="utf-8")
        deliverable = workspace / "reports" / "selftest.md"
        deliverable.parent.mkdir(parents=True, exist_ok=True)
        deliverable.write_text("# ok\n", encoding="utf-8")
        artifacts = run_dir / "artifacts"
        artifacts.mkdir(parents=True, exist_ok=True)
        (artifacts / "research-market.md").write_text("# Findings\n\n## Evidence\n", encoding="utf-8")

        subprocess.run([
            sys.executable,
            str(SCRIPT_DIR / "write_status.py"),
            "--workspace",
            str(workspace),
            "--run-id",
            run_id,
            "--replace-json",
            '{"runId":"%s","state":"running","phase":"research","profile":"research","deliverables":["reports/selftest.md"],"recoveryState":{"phaseAttempts":{}},"completedWorkstreams":["market"],"activeWorkstreams":[],"selectedModel":"session-inherited","modelControlMode":"session-inherited","fallbackChain":[]}' % run_id,
        ], check=True, stdout=subprocess.DEVNULL)
        subprocess.run([
            sys.executable,
            str(SCRIPT_DIR / "write_journal.py"),
            "--workspace", str(workspace), "--run-id", run_id,
            "--phase", "research", "--actor", "selftest", "--action", "init", "--result", "success", "--next", "finalize"
        ], check=True, stdout=subprocess.DEVNULL)
        subprocess.run([
            sys.executable,
            str(SCRIPT_DIR / "record_source.py"),
            "--workspace", str(workspace), "--run-id", run_id,
            "--title", "Example Source", "--url", "https://example.com", "--used-in", "market"
        ], check=True, stdout=subprocess.DEVNULL)
        subprocess.run([
            sys.executable,
            str(SCRIPT_DIR / "record_source.py"),
            "--workspace", str(workspace), "--run-id", run_id,
            "--title", "Example Source 2", "--url", "https://example.org", "--used-in", "market"
        ], check=True, stdout=subprocess.DEVNULL)
        subprocess.run([
            sys.executable,
            str(SCRIPT_DIR / "finalize_run.py"),
            "--workspace", str(workspace), "--run-id", run_id,
            "--status", "complete", "--headline", "selftest complete",
            "--local-verify",
        ], check=True, stdout=subprocess.DEVNULL)

        status = read_json(run_dir / "status.json", {})
        summary = read_text(run_dir / "final-summary.md", "")
        active = read_text(state_dir / "active-run-id", "")
        plan = read_text(run_dir / "plan.md", "")
        assert status.get("state") == "complete"
        assert "selftest complete" in summary
        assert active == ""
        assert "LongRun Status Board" in plan
        print("selftest: ok")
        return 0
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
