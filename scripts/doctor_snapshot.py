#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from longrun_web.bridge import longrun_lib  # noqa: E402
from longrun_web.prompt_packs import list_pack_versions  # noqa: E402

REQUIRED_HELPERS = [
    "write_status.py",
    "write_journal.py",
    "record_source.py",
    "harvest_sources.py",
    "reconcile_run.py",
    "verify_run.py",
    "finalize_run.py",
]


def _bin(name: str) -> str | None:
    return shutil.which(name)


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, text=True, capture_output=True)


def _copilot_login(config_dir: Path) -> str | None:
    for name in ("COPILOT_GITHUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN"):
        if os.environ.get(name):
            return f"env:{name}"
    config_json = config_dir / "config.json"
    if not config_json.exists():
        return None
    try:
        obj = json.loads(config_json.read_text(encoding="utf-8"))
    except Exception:
        return None
    last = obj.get("last_logged_in_user") or {}
    login = last.get("login")
    host = last.get("host") or "https://github.com"
    return f"{login}@{host}" if login else None


def _gh_login(gh_bin: str | None) -> str | None:
    if not gh_bin:
        return None
    completed = _run(gh_bin, "auth", "status", "-h", "github.com")
    text = (completed.stdout or "") + "\n" + (completed.stderr or "")
    for line in text.splitlines():
        if "Logged in to github.com account" in line:
            parts = line.strip().split()
            if parts:
                return parts[-1]
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Emit a machine-readable LongRun doctor snapshot")
    parser.add_argument("--workspace", default=".")
    args = parser.parse_args()

    workspace = Path(args.workspace).expanduser().resolve()
    copilot_bin = _bin("copilot")
    gh_bin = _bin("gh")
    screen_bin = _bin("screen")
    launcher = ROOT / "scripts" / "copilot-longrun"
    helper_home = longrun_lib.LONGRUN_HOME / "bin"
    config_dir = Path(os.environ.get("COPILOT_CONFIG_DIR", str(Path.home() / ".copilot")))

    copilot_version = None
    if copilot_bin:
        completed = _run(copilot_bin, "--version")
        copilot_version = (completed.stdout or completed.stderr).splitlines()[0] if (completed.stdout or completed.stderr) else None

    helper_states = []
    missing_helpers = []
    for name in REQUIRED_HELPERS:
        path = helper_home / name
        exists = path.exists() or (ROOT / "scripts" / name).exists()
        helper_states.append({"name": name, "available": exists, "path": str(path if path.exists() else ROOT / "scripts" / name)})
        if not exists:
            missing_helpers.append(name)

    payload = {
        "ok": bool(copilot_bin and _copilot_login(config_dir) and not missing_helpers),
        "workspace": str(workspace),
        "repoRoot": str(ROOT),
        "copilot": {
            "installed": bool(copilot_bin),
            "path": copilot_bin,
            "version": copilot_version,
            "login": _copilot_login(config_dir),
        },
        "gh": {
            "installed": bool(gh_bin),
            "path": gh_bin,
            "login": _gh_login(gh_bin),
        },
        "screen": {
            "installed": bool(screen_bin),
            "path": screen_bin,
        },
        "launcher": {
            "installed": launcher.exists(),
            "path": str(launcher),
        },
        "helpers": {
            "home": str(helper_home),
            "required": helper_states,
            "missing": missing_helpers,
        },
        "modelPolicy": {
            "path": str(longrun_lib.DEFAULT_MODEL_CONFIG),
            "exists": longrun_lib.DEFAULT_MODEL_CONFIG.exists() or (ROOT / "config" / "model-policy.json").exists(),
        },
        "web": {
            "requirementsPath": str(ROOT / "requirements-web.txt"),
            "promptPackVersions": list_pack_versions(),
        },
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
