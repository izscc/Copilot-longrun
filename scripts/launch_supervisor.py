#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from _longrun_lib import (  # noqa: E402
    LongRunError,
    classify_failure,
    display_model_name,
    ensure_status_defaults,
    extract_rate_limit,
    load_model_config,
    local_verify,
    model_availability_snapshot,
    now_iso,
    read_json,
    read_model_availability,
    resolve_run_target,
    status_path,
    validate_model_config,
    write_json_atomic,
)

MODEL_FALLBACK_PATTERNS = [
    ("model-unavailable", "unknown model"),
    ("model-unavailable", "invalid model"),
    ("model-unavailable", "from --model flag is not available"),
    ("model-unavailable", "not available to your account"),
    ("model-unavailable", "you do not have access"),
    ("model-unavailable", "cannot use model"),
    ("model-unavailable", "model is not supported"),
    ("rate-limited", "user_model_rate_limited"),
]


def build_command(args, skill_ref: str, payload: str, model: str) -> list[str]:
    cmd = [args.copilot_bin]
    for item in args.plugin_arg:
        cmd.extend(["--plugin-dir", item])
    if args.mode in {"run", "resume"}:
        cmd.extend(["--autopilot", "--yolo", "--no-ask-user", "--max-autopilot-continues", str(args.max_continues)])
    else:
        cmd.extend(["--yolo", "--no-ask-user"])
    cmd.extend(["--model", model, "-p", f"{skill_ref} {payload}".strip()])
    return cmd


def run_and_stream(cmd: list[str], cwd: Path, env_patch: dict[str, str] | None = None) -> tuple[int, str]:
    env = os.environ.copy()
    if env_patch:
        env.update(env_patch)
    process = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    chunks: list[str] = []
    assert process.stdout is not None
    for line in process.stdout:
        sys.stdout.write(line)
        sys.stdout.flush()
        chunks.append(line)
    rc = process.wait()
    return rc, "".join(chunks)


def detect_fallback_reason(output: str) -> str | None:
    lowered = output.lower()
    if extract_rate_limit(output):
        return "rate-limited"
    for reason, snippet in MODEL_FALLBACK_PATTERNS:
        if snippet in lowered:
            return reason
    return None


def patch_latest_run(workspace: Path, *, selected_model: str, fallback_reason: str | None = None, note: str | None = None) -> None:
    try:
        target = resolve_run_target(workspace, "latest")
    except LongRunError:
        return
    status_file = status_path(target)
    status = ensure_status_defaults(read_json(status_file, {}))
    if not status:
        return
    status["selectedModel"] = selected_model
    status["modelControlMode"] = "launcher-enforced"
    history = list(status.get("modelAttemptHistory") or [])
    history.append({
        "ts": now_iso(),
        "model": selected_model,
        "reason": fallback_reason or note or "launcher-attempt",
    })
    status["modelAttemptHistory"] = history[-12:]
    if fallback_reason:
        status["fallbackReason"] = fallback_reason
    status["updatedAt"] = now_iso()
    write_json_atomic(status_file, status)


def patch_recovery_hint(workspace: Path, *, message: str, failure_class: str | None = None, recommended_action: str | None = None) -> None:
    try:
        target = resolve_run_target(workspace, "latest")
    except LongRunError:
        return
    status_file = status_path(target)
    status = ensure_status_defaults(read_json(status_file, {}))
    if not status:
        return
    status["lastError"] = {"message": message, "ts": now_iso()}
    recovery = status.get("recoveryState") or {}
    recovery["failureClass"] = failure_class
    recovery["lastRecommendedAction"] = recommended_action
    recovery["retryCount"] = int(recovery.get("retryCount") or 0) + 1
    status["recoveryState"] = recovery
    status["updatedAt"] = now_iso()
    write_json_atomic(status_file, status)


def auto_finalize_if_possible(workspace: Path, note: str) -> bool:
    try:
        target = resolve_run_target(workspace, "latest")
    except LongRunError:
        return False
    subprocess.run([
        sys.executable,
        str(SCRIPT_DIR / "harvest_sources.py"),
        "--workspace", str(workspace),
        "--run-id", target.run_id,
    ], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run([
        sys.executable,
        str(SCRIPT_DIR / "reconcile_run.py"),
        "--workspace", str(workspace),
        "--run-id", target.run_id,
    ], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    status = read_json(status_path(target), {})
    if status.get("state") == "complete":
        return True
    verification = local_verify(target)
    if not verification.get("ok") or not verification.get("deliverables"):
        patch_recovery_hint(
            workspace,
            message="auto-finalize precheck did not pass local verification",
            failure_class=verification.get("failureClass"),
            recommended_action=verification.get("recommendedAction"),
        )
        return False
    finalize = SCRIPT_DIR / "finalize_run.py"
    subprocess.run([
        sys.executable,
        str(finalize),
        "--workspace", str(workspace),
        "--run-id", target.run_id,
        "--status", "complete",
        "--headline", "LongRun auto-finalized after local deliverable verification",
        "--local-verify",
        "--recovery-note", note,
    ], check=False)
    return True


def maybe_finalize_blocked(workspace: Path, note: str) -> None:
    try:
        target = resolve_run_target(workspace, "latest")
    except LongRunError:
        return
    status = read_json(status_path(target), {})
    if status.get("state") in {"complete", "blocked"}:
        return
    finalize = SCRIPT_DIR / "finalize_run.py"
    subprocess.run([
        sys.executable,
        str(finalize),
        "--workspace", str(workspace),
        "--run-id", target.run_id,
        "--status", "blocked",
        "--headline", "LongRun blocked after exhausting automatic recovery budget",
        "--recovery-note", note,
        "--blocker", note,
    ], check=False)


def main() -> int:
    parser = argparse.ArgumentParser(description="LongRun Copilot supervisor with model fallback")
    parser.add_argument("--workspace", default=os.getcwd())
    parser.add_argument("--copilot-bin", required=True)
    parser.add_argument("--mode", choices=["run", "resume", "prompt", "status"], required=True)
    parser.add_argument("--skill-ref", required=True)
    parser.add_argument("--resume-skill-ref", default="")
    parser.add_argument("--payload", required=True)
    parser.add_argument("--max-continues", default="100")
    parser.add_argument("--explicit-model")
    parser.add_argument("--model-config")
    parser.add_argument("--availability-cache")
    parser.add_argument("--refresh-model-cache", action="store_true")
    parser.add_argument("--plugin-arg", action="append", default=[])
    args = parser.parse_args()

    workspace = Path(args.workspace).resolve()
    config = load_model_config(args.model_config)
    errors = validate_model_config(config)
    if errors:
        for error in errors:
            print(f"[model-config-error] {error}", file=sys.stderr)
        return 2

    # Imported lazily to avoid circular import churn in summary contexts.
    from _longrun_lib import model_chain  # noqa: E402

    availability_cache = read_model_availability(args.availability_cache)
    availability = model_availability_snapshot(config, cache=availability_cache)
    chain = model_chain(config, explicit_model=args.explicit_model, prompt_text=args.payload, availability=availability)
    current_skill = args.skill_ref
    current_payload = args.payload

    for index, model in enumerate(chain):
        human = display_model_name(model, config)
        print(f"[LongRun] attempt {index + 1}/{len(chain)} with model: {human} ({model})")
        patch_latest_run(workspace, selected_model=model, note="launcher-attempt")
        cmd = build_command(args, current_skill, current_payload, model)
        rc, output = run_and_stream(cmd, workspace, {
            "LONGRUN_SELECTED_MODEL": model,
            "LONGRUN_MODEL_CONTROL_MODE": "launcher-enforced",
        })
        fallback_reason = detect_fallback_reason(output)
        if rc == 0 and not fallback_reason:
            return 0
        if auto_finalize_if_possible(workspace, f"launcher observed: {fallback_reason or 'non-zero exit after deliverable verification'}"):
            return 0
        if not fallback_reason:
            failure_class, recommended = classify_failure(last_error=output)
            patch_recovery_hint(workspace, message="launcher run failed without model fallback", failure_class=failure_class, recommended_action=recommended)
            return rc or 1
        _, recommended = classify_failure(last_error=fallback_reason)
        patch_recovery_hint(workspace, message=fallback_reason, failure_class=fallback_reason.replace("-", "_"), recommended_action=recommended)
        patch_latest_run(workspace, selected_model=model, fallback_reason=fallback_reason)
        if args.mode in {"run", "resume"} and args.resume_skill_ref:
            current_skill = args.resume_skill_ref
            current_payload = "latest"
        if index + 1 < len(chain):
            continue

        backoff_minutes = list(config.get("backoffMinutes", []))[:3]
        for backoff in backoff_minutes:
            note = f"{fallback_reason}; backoff {backoff}m before retry"
            print(f"[LongRun] {note}")
            time.sleep(backoff * 60)
            retry_cmd = build_command(args, current_skill, current_payload, model)
            rc, output = run_and_stream(retry_cmd, workspace, {
                "LONGRUN_SELECTED_MODEL": model,
                "LONGRUN_MODEL_CONTROL_MODE": "launcher-enforced",
            })
            retry_reason = detect_fallback_reason(output)
            if rc == 0 and not retry_reason:
                return 0
            if auto_finalize_if_possible(workspace, f"launcher recovered after {note}"):
                return 0
            _, recommended = classify_failure(last_error=retry_reason or fallback_reason)
            patch_recovery_hint(workspace, message=retry_reason or fallback_reason, failure_class=(retry_reason or fallback_reason or "").replace("-", "_") or None, recommended_action=recommended)
            patch_latest_run(workspace, selected_model=model, fallback_reason=retry_reason or fallback_reason)
            if not retry_reason:
                return rc or 1
        maybe_finalize_blocked(workspace, f"{fallback_reason}; exhausted fallback chain and backoff budget")
        return 1

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
