#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from _longrun_lib import append_jsonl, hook_events_path, now_iso, read_json, read_text, resolve_workspace, status_path, write_json_atomic  # noqa: E402


def load_payload() -> dict:
    try:
        return json.load(sys.stdin)
    except Exception:
        return {}


def main() -> int:
    event = os.environ.get("HOOK_EVENT", "unknown")
    data = load_payload()
    cwd = resolve_workspace(data.get("cwd") or os.getcwd())
    base = cwd / ".copilot-mission-control"
    global_path = base / "global" / "hook-events.jsonl"
    record = {"ts": data.get("timestamp") or now_iso(), "source": "hook", "event": event, "payload": data}
    append_jsonl(global_path, record)

    active_path = base / "state" / "active-run-id"
    run_id = read_text(active_path, "").strip() if active_path.exists() else ""
    if run_id:
        run_dir = base / "runs" / run_id
        append_jsonl(run_dir / "hook-events.jsonl", record)
        if event == "errorOccurred":
            status_file = run_dir / "status.json"
            status = read_json(status_file, {})
            status["lastError"] = {
                "ts": record["ts"],
                "event": event,
                "message": data.get("message") or data.get("error") or json.dumps(data, ensure_ascii=False),
            }
            recovery = dict(status.get("recoveryState") or {})
            recovery["lastErrorTs"] = record["ts"]
            status["recoveryState"] = recovery
            status["updatedAt"] = now_iso()
            write_json_atomic(status_file, status)

    if event != "preToolUse" or not run_id:
        return 0

    run_dir = base / "runs" / run_id
    policy = read_json(run_dir / "policy.json", {"allowCommit": False, "allowPush": False, "allowPR": False})
    args = data.get("toolArgs")
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except Exception:
            args = {"raw": args}
    cmd = ""
    if isinstance(args, dict):
        cmd = args.get("command") or args.get("script") or args.get("bash") or ""
    lowered = cmd.lower()
    tool = (data.get("toolName") or "").lower()
    deny = None
    dangerous_patterns = [r"(^|\s)sudo\b", r"rm\s+-rf\s+/", r"\bmkfs\b", r"\bdd\s+if=", r"diskutil\s+erase", r"\bshutdown\b", r"\breboot\b", r":\(\)\s*\{\s*:\|:&\s*\};:"]
    if tool in {"bash", "powershell"} and any(re.search(pattern, lowered) for pattern in dangerous_patterns):
        deny = "Blocked by copilot-mission-control: dangerous system command."
    elif tool in {"bash", "powershell"}:
        if not policy.get("allowCommit", False) and re.search(r"\bgit\s+commit\b", lowered):
            deny = "Blocked by copilot-mission-control: git commit is disabled for this run."
        elif not policy.get("allowPush", False) and (re.search(r"\bgit\s+push\b", lowered) or re.search(r"\bgit\s+tag\b", lowered)):
            deny = "Blocked by copilot-mission-control: git push/tag is disabled for this run."
        elif not policy.get("allowPR", False) and (re.search(r"\bgh\s+pr\s+(create|merge)\b", lowered) or re.search(r"\bhub\s+pull-request\b", lowered)):
            deny = "Blocked by copilot-mission-control: PR creation/merge is disabled for this run."
    if deny:
        print(json.dumps({"permissionDecision": "deny", "permissionDecisionReason": deny}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
