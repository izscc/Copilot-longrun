from __future__ import annotations

import json
import os
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any, Iterator

from .bridge import REPO_ROOT, longrun_lib


def workspace_root() -> Path:
    return Path(os.environ.get("LONGRUN_WEB_WORKSPACE", os.getcwd())).expanduser().resolve()


def launcher_dir(workspace: Path | None = None) -> Path:
    root = workspace or workspace_root()
    return root / ".copilot-mission-control" / "launcher"


def copilot_longrun_path() -> Path:
    return REPO_ROOT / "scripts" / "copilot-longrun"


def python_script(name: str) -> Path:
    return REPO_ROOT / "scripts" / name


def run_command(args: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=str(cwd or workspace_root()), text=True, capture_output=True)


def _json_or_error(completed: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    stdout = (completed.stdout or "").strip()
    stderr = (completed.stderr or "").strip()
    if stdout:
        try:
            data = json.loads(stdout)
            if isinstance(data, dict):
                data.setdefault("ok", completed.returncode == 0)
                return data
        except Exception:
            pass
    return {
        "ok": completed.returncode == 0,
        "stdout": stdout,
        "error": stderr or stdout or f"command exited with code {completed.returncode}",
    }


def invoke_helper_json(script_name: str, *args: str) -> dict[str, Any]:
    completed = run_command(["python3", str(python_script(script_name)), *args])
    return _json_or_error(completed)


def doctor_snapshot() -> dict[str, Any]:
    return invoke_helper_json("doctor_snapshot.py", "--workspace", str(workspace_root()))


def list_runs() -> list[dict[str, Any]]:
    base = workspace_root() / ".copilot-mission-control" / "runs"
    items: list[dict[str, Any]] = []
    if not base.exists():
        return items
    for run_dir in sorted([path for path in base.iterdir() if path.is_dir()], reverse=True):
        status = longrun_lib.read_json(run_dir / "status.json", {})
        status = longrun_lib.ensure_status_defaults(status)
        items.append(
            {
                "runId": run_dir.name,
                "state": status.get("state"),
                "phase": status.get("phase"),
                "summary": status.get("summary"),
                "updatedAt": status.get("updatedAt"),
                "operatorPendingCount": status.get("operatorInbox", {}).get("pendingCount", 0),
                "selectedModel": status.get("selectedModel"),
            }
        )
    return items


def _latest_launcher_meta() -> dict[str, Any] | None:
    meta_dir = launcher_dir()
    if not meta_dir.exists():
        return None
    metas = sorted(meta_dir.glob("*.json"), reverse=True)
    for meta_file in metas:
        try:
            return json.loads(meta_file.read_text(encoding="utf-8"))
        except Exception:
            continue
    return None


def _tail(path_text: str | None, lines: int = 120) -> list[str]:
    if not path_text:
        return []
    path = Path(path_text)
    if not path.exists():
        return []
    data = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    return data[-lines:]


def run_detail(run_id: str) -> dict[str, Any]:
    snapshot = invoke_helper_json("run_snapshot.py", "--workspace", str(workspace_root()), "--run-id", run_id)
    if not snapshot.get("ok", False):
        raise FileNotFoundError(snapshot.get("error") or f"Run not found: {run_id}")
    meta = _latest_launcher_meta()
    snapshot.setdefault("launcherMeta", meta)
    if meta and not snapshot.get("logTail"):
        snapshot["logTail"] = _tail(meta.get("logFile"))
    return snapshot


def write_operator_request(run_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    target = longrun_lib.resolve_run_target(workspace_root(), run_id)
    request_id = payload.get("id") or f"req-{uuid.uuid4().hex[:12]}"

    def list_lines(items: list[str] | None) -> list[str]:
        clean = [str(item).strip() for item in (items or []) if str(item).strip()]
        return [f"- {item}" for item in clean] if clean else []

    block = [
        f"<!-- LONGRUN:INBOX id={request_id} ts={longrun_lib.now_iso()} type={payload.get('type', 'append_task')} status=submitted priority={payload.get('priority', 'normal')} -->",
        f"## Operator Request: {payload.get('title') or '追加任务'}",
        "",
        "### Raw Request",
        payload.get("rawText") or payload.get("normalizedText") or "",
        "",
        "### Normalized Request",
        payload.get("normalizedText") or payload.get("rawText") or "",
    ]
    deliverable_lines = list_lines(payload.get("linkedDeliverables"))
    if deliverable_lines:
        block.extend(["", "### Linked Deliverables", *deliverable_lines])
    artifact_lines = list_lines(payload.get("linkedArtifacts"))
    if artifact_lines:
        block.extend(["", "### Linked Artifacts", *artifact_lines])
    if payload.get("linkedWorkstream"):
        block.extend(["", "### Linked Workstream", f"- {payload['linkedWorkstream']}"])
    block.extend(["", "<!-- /LONGRUN:INBOX -->", ""])

    longrun_lib.ensure_dir(target.run_dir)
    with longrun_lib.operator_inbox_path(target).open("a", encoding="utf-8") as handle:
        handle.write("\n".join(block) + "\n")

    status = longrun_lib.ensure_status_defaults(longrun_lib.read_json(longrun_lib.status_path(target), {}))
    status = longrun_lib.sync_operator_tasks(target, status, checkpoint="web-inbox")
    status["updatedAt"] = longrun_lib.now_iso()
    longrun_lib.write_json_atomic(longrun_lib.status_path(target), status)
    longrun_lib.sync_plan_markdown(target, status)
    return {"ok": True, "requestId": request_id, "runId": target.run_id, "operatorTasks": status.get("operatorTasks", [])}


def launch_run(prompt: str, *, model: str | None = None) -> dict[str, Any]:
    cmd = [str(copilot_longrun_path()), "run", "--detach", "--json"]
    if model:
        cmd.extend(["--model", model])
    cmd.append(prompt)
    return _json_or_error(run_command(cmd))


def resume_run(run_id: str, *, model: str | None = None) -> dict[str, Any]:
    cmd = [str(copilot_longrun_path()), "resume", "--detach", "--json"]
    if model:
        cmd.extend(["--model", model])
    cmd.append(run_id)
    return _json_or_error(run_command(cmd))


def verify_run(run_id: str) -> dict[str, Any]:
    return invoke_helper_json("verify_run.py", "--workspace", str(workspace_root()), "--run-id", run_id, "--json")


def reconcile_run(run_id: str) -> dict[str, Any]:
    return invoke_helper_json("reconcile_run.py", "--workspace", str(workspace_root()), "--run-id", run_id, "--print")


def finalize_run(run_id: str, *, status_name: str, headline: str) -> dict[str, Any]:
    return invoke_helper_json(
        "finalize_run.py",
        "--workspace",
        str(workspace_root()),
        "--run-id",
        run_id,
        "--status",
        status_name,
        "--headline",
        headline,
        "--local-verify",
        "--print",
    )


def stream_snapshots(run_id: str) -> Iterator[str]:
    last = None
    while True:
        snapshot = run_detail(run_id)
        blob = json.dumps(snapshot, ensure_ascii=False, sort_keys=True)
        if blob != last:
            yield f"data: {blob}\n\n"
            last = blob
        time.sleep(1)
