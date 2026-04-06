#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from _longrun_lib import (  # noqa: E402
    append_jsonl,
    ensure_run_layout,
    ensure_status_defaults,
    init_status_payload,
    journal_path,
    load_model_config,
    mint_run_id,
    model_availability_snapshot,
    now_iso,
    prompt_stem,
    read_json,
    read_model_availability,
    refresh_artifact_inventory,
    resolve_run_target,
    set_active_run,
    set_latest_run,
    status_path,
    sync_plan_markdown,
    write_json_atomic,
    write_text_atomic,
)


def build_mission_markdown(run_id: str, prompt: str, status: dict[str, object], launcher_mode: str) -> str:
    lines = [
        "# Mission Contract",
        "",
        "## Run Metadata",
        f"- Run ID: `{run_id}`",
        f"- Prepared at: `{status.get('createdAt')}`",
        f"- Launcher mode: `{launcher_mode}`",
        f"- Model control: `{status.get('modelControlMode')}`",
        f"- Selected model: `{status.get('selectedModel')}`",
    ]
    termination_mode = status.get("terminationMode")
    if termination_mode:
        lines.append(f"- Termination mode: `{termination_mode}`")
    lines.extend([
        "",
        "## Profile",
        f"- Profile: `{status.get('profile')}`",
        f"- Complexity: `{status.get('complexity')}`",
        f"- Delegation mode: `{status.get('delegationMode')}`",
        f"- Language: `{status.get('language')}`",
        f"- Evidence mode: `{status.get('evidenceMode')}`",
        f"- Model policy: `{status.get('modelPolicy')}`",
        "",
        "## Original user prompt",
        "```text",
        (prompt or "").rstrip(),
        "```",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare a fresh LongRun run directory and state pointers")
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--task", required=True)
    parser.add_argument("--run-id")
    parser.add_argument("--allow-existing", action="store_true")
    parser.add_argument("--explicit-model")
    parser.add_argument("--session-model")
    parser.add_argument("--model-control-mode")
    parser.add_argument("--model-config")
    parser.add_argument("--availability-cache")
    parser.add_argument("--termination-mode")
    parser.add_argument("--launcher-mode", default="launcher-preallocated")
    parser.add_argument("--print-json", action="store_true", dest="do_print")
    args = parser.parse_args()

    run_id = args.run_id or mint_run_id(args.workspace, args.task)
    target = resolve_run_target(args.workspace, run_id)
    status_file = status_path(target)
    status_exists = status_file.exists()
    run_exists = target.run_dir.exists() and any(target.run_dir.iterdir()) if target.run_dir.exists() else False
    if run_exists and not args.allow_existing:
        raise SystemExit(f"prepare_run: run already exists: {target.run_id}")

    ensure_run_layout(target)
    set_active_run(target.base, target.run_id)
    set_latest_run(target.base, target.run_id)

    if status_exists and args.allow_existing:
        status = ensure_status_defaults(read_json(status_file, {}))
    else:
        config = load_model_config(args.model_config)
        availability = model_availability_snapshot(
            config,
            cache=read_model_availability(args.availability_cache),
            path=args.availability_cache,
        )
        status = init_status_payload(
            target.run_id,
            args.task,
            explicit_model=args.explicit_model,
            session_model=args.session_model,
            model_control_mode=args.model_control_mode,
            config=config,
            availability=availability,
        )

    status["runId"] = target.run_id
    status.setdefault("createdAt", now_iso())
    status["updatedAt"] = now_iso()
    status["launcherMode"] = args.launcher_mode
    status["runIdSource"] = "explicit" if args.run_id else "generated"
    if args.termination_mode:
        status["terminationMode"] = args.termination_mode
    if not status_exists or not args.allow_existing:
        status["summary"] = "Mission prepared by launcher"
        status["phase"] = "init"
        status["state"] = "running"
    status = refresh_artifact_inventory(target, status)
    write_json_atomic(status_file, status)
    sync_plan_markdown(target, status)

    mission_file = target.run_dir / "mission.md"
    if not mission_file.exists() or not mission_file.read_text(encoding="utf-8").strip():
        write_text_atomic(mission_file, build_mission_markdown(target.run_id, args.task, status, args.launcher_mode))

    if not status_exists:
        append_jsonl(journal_path(target), {
            "ts": now_iso(),
            "source": "helper",
            "event": "run-prepared",
            "payload": {
                "runId": target.run_id,
                "launcherMode": args.launcher_mode,
                "taskStem": prompt_stem(args.task),
            },
        })

    result = {
        "workspace": str(target.workspace),
        "runId": target.run_id,
        "runDir": str(target.run_dir),
        "launcherMode": args.launcher_mode,
        "statusPath": str(status_file),
        "existing": run_exists,
    }
    if args.do_print:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(target.run_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
