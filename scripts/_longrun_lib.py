#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

LONGRUN_HOME = Path(os.environ.get("LONGRUN_HOME", str(Path.home() / ".copilot-mission-control")))
DEFAULT_MODEL_CONFIG = LONGRUN_HOME / "config" / "model-policy.json"
KNOWN_MODEL_DISPLAY = {
    "claude-opus-4.6": "Claude Opus 4.6",
    "claude-opus-4.5": "Claude Opus 4.5",
    "claude-sonnet-4.6": "Claude Sonnet 4.6",
    "claude-sonnet-4.5": "Claude Sonnet 4.5",
    "gpt-5.4": "GPT-5.4",
    "gemini-3.1-pro": "Gemini 3.1 Pro",
}
MODEL_ALIASES = {
    "claude opus 4.6": "claude-opus-4.6",
    "claude-opus-4.6": "claude-opus-4.6",
    "opus 4.6": "claude-opus-4.6",
    "opus4.6": "claude-opus-4.6",
    "opus": "claude-opus-4.6",
    "claude opus 4.5": "claude-opus-4.5",
    "claude-opus-4.5": "claude-opus-4.5",
    "opus 4.5": "claude-opus-4.5",
    "claude sonnet 4.6": "claude-sonnet-4.6",
    "claude-sonnet-4.6": "claude-sonnet-4.6",
    "sonnet 4.6": "claude-sonnet-4.6",
    "claude sonnet 4.5": "claude-sonnet-4.5",
    "claude-sonnet-4.5": "claude-sonnet-4.5",
    "sonnet 4.5": "claude-sonnet-4.5",
    "sonnet": "claude-sonnet-4.6",
    "gpt-5.4": "gpt-5.4",
    "gpt 5.4": "gpt-5.4",
    "gpt5.4": "gpt-5.4",
    "gemini 3.1 pro": "gemini-3.1-pro",
    "gemini-3.1-pro": "gemini-3.1-pro",
    "gemini 3.1": "gemini-3.1-pro",
}
RATE_LIMIT_PATTERNS = [
    r"user_model_rate_limited",
    r"hit a rate limit",
    r"please try again in",
    r"rate limit that restricts",
]


class LongRunError(RuntimeError):
    pass


@dataclass
class RunTarget:
    workspace: Path
    base: Path
    run_id: str
    run_dir: Path


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_text(path: Path, default: str = "") -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return default


def read_json(path: Path, default: Any = None) -> Any:
    if default is None:
        default = {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return copy.deepcopy(default)
    except json.JSONDecodeError:
        return copy.deepcopy(default)


def write_json_atomic(path: Path, obj: Any) -> Path:
    ensure_dir(path.parent)
    with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False, encoding="utf-8") as tmp:
        json.dump(obj, tmp, ensure_ascii=False, indent=2)
        tmp.write("\n")
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)
    return path


def write_text_atomic(path: Path, text: str) -> Path:
    ensure_dir(path.parent)
    with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False, encoding="utf-8") as tmp:
        tmp.write(text)
        if not text.endswith("\n"):
            tmp.write("\n")
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)
    return path


def append_jsonl(path: Path, obj: Any) -> Path:
    ensure_dir(path.parent)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(obj, ensure_ascii=False) + "\n")
    return path


def shallow_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = shallow_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def resolve_workspace(path: str | None = None) -> Path:
    return Path(path or os.getcwd()).expanduser().resolve()


def sanitize_run_id(value: str) -> str:
    return value.strip()


def resolve_run_target(workspace: str | Path | None = None, run_id: str | None = None) -> RunTarget:
    ws = resolve_workspace(str(workspace) if workspace else None)
    base = ws / ".copilot-mission-control"
    state_dir = base / "state"
    if not run_id or run_id in {"latest", "active"}:
        state_name = "latest-run-id" if run_id in {None, "latest"} else "active-run-id"
        state_file = state_dir / state_name
        run_id = sanitize_run_id(read_text(state_file, ""))
    if not run_id:
        raise LongRunError(f"No run id found in workspace: {ws}")
    run_dir = base / "runs" / run_id
    return RunTarget(workspace=ws, base=base, run_id=run_id, run_dir=run_dir)


def status_path(target: RunTarget) -> Path:
    return target.run_dir / "status.json"


def journal_path(target: RunTarget) -> Path:
    return target.run_dir / "journal.jsonl"


def hook_events_path(target: RunTarget) -> Path:
    return target.run_dir / "hook-events.jsonl"


def sources_path(target: RunTarget) -> Path:
    return target.run_dir / "sources.jsonl"


def final_summary_path(target: RunTarget) -> Path:
    return target.run_dir / "final-summary.md"


def active_run_file(base: Path) -> Path:
    return base / "state" / "active-run-id"


def default_model_config() -> dict[str, Any]:
    return {
        "defaultPolicy": "opus-first",
        "preferred": ["claude-opus-4.6", "claude-opus-4.5"],
        "fallback": ["claude-sonnet-4.6", "claude-sonnet-4.5", "gpt-5.4", "gemini-3.1-pro"],
        "backoffMinutes": [2, 5, 10],
        "displayNames": KNOWN_MODEL_DISPLAY,
        "aliases": MODEL_ALIASES,
    }


def load_model_config(path: str | Path | None = None) -> dict[str, Any]:
    config_path = Path(path).expanduser() if path else DEFAULT_MODEL_CONFIG
    config = read_json(config_path, default_model_config())
    merged = default_model_config()
    merged.update({k: v for k, v in config.items() if k not in {"displayNames", "aliases"}})
    merged["displayNames"] = shallow_merge(default_model_config()["displayNames"], config.get("displayNames", {}))
    merged["aliases"] = shallow_merge(default_model_config()["aliases"], config.get("aliases", {}))
    return merged


def normalize_model_name(value: str | None, config: dict[str, Any] | None = None) -> str | None:
    if not value:
        return None
    cfg = config or default_model_config()
    token = value.strip().lower()
    aliases = {k.lower(): v for k, v in cfg.get("aliases", {}).items()}
    if token in aliases:
        return aliases[token]
    if token in cfg.get("displayNames", {}):
        return token
    simplified = re.sub(r"\s+", " ", token)
    return aliases.get(simplified)


def detect_model_from_text(text: str | None, config: dict[str, Any] | None = None) -> str | None:
    if not text:
        return None
    cfg = config or default_model_config()
    lowered = text.lower()
    aliases = sorted(cfg.get("aliases", {}).items(), key=lambda item: len(item[0]), reverse=True)
    for alias, slug in aliases:
        pattern = re.escape(alias.lower())
        if re.search(pattern, lowered):
            return slug
    return None


def display_model_name(slug: str, config: dict[str, Any] | None = None) -> str:
    cfg = config or default_model_config()
    return cfg.get("displayNames", {}).get(slug, slug)


def model_chain(config: dict[str, Any], explicit_model: str | None = None, prompt_text: str | None = None) -> list[str]:
    detected = normalize_model_name(explicit_model, config)
    if not detected:
        detected = detect_model_from_text(prompt_text, config)
    base_chain = list(dict.fromkeys([*config.get("preferred", []), *config.get("fallback", [])]))
    if detected:
        return [detected] + [item for item in base_chain if item != detected]
    return base_chain


def validate_model_config(config: dict[str, Any]) -> list[str]:
    known = set(KNOWN_MODEL_DISPLAY)
    errors: list[str] = []
    for field in ("preferred", "fallback"):
        for value in config.get(field, []):
            if value not in known:
                errors.append(f"{field} contains unknown model slug: {value}")
    for alias, slug in config.get("aliases", {}).items():
        if slug not in known:
            errors.append(f"alias '{alias}' points to unknown model slug: {slug}")
    backoff = config.get("backoffMinutes", [])
    if not isinstance(backoff, list) or not backoff or not all(isinstance(x, int) and x > 0 for x in backoff):
        errors.append("backoffMinutes must be a non-empty list of positive integers")
    return errors


def slugify(text: str, max_len: int = 48) -> str:
    lowered = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    lowered = re.sub(r"-+", "-", lowered)
    return (lowered[:max_len] or "mission").strip("-")


def infer_profile(prompt: str) -> str:
    lowered = prompt.lower()
    coding_signals = ["代码", "bug", "测试", "构建", "重构", "脚本", "repo", "ci", "fix", "implement", "refactor", "test", "debug", "build"]
    office_signals = ["表格", "文档", "汇报", "ppt", "幻灯片", "excel", "csv", "markdown", "报告", "总结", "材料", "slide", "sheet", "doc"]
    research_signals = ["调研", "research", "趋势", "分析", "市场", "政策", "法规", "competitive", "benchmark", "industry"]
    if any(signal in lowered for signal in coding_signals):
        return "coding"
    if any(signal in lowered for signal in research_signals):
        return "research"
    if any(signal in lowered for signal in office_signals):
        return "office"
    return "office"


def infer_complexity(prompt: str) -> str:
    lowered = prompt.lower()
    heavy_signals = ["multi", "多", "并行", "parallel", "phase", "fleet", "research", "report", "验证", "resume", "长期"]
    medium_signals = ["report", "分析", "docs", "tests", "文档", "研究", "多步"]
    if sum(signal in lowered for signal in heavy_signals) >= 2:
        return "fleet"
    if any(signal in lowered for signal in medium_signals):
        return "parallel"
    return "single-lane"


def infer_language(prompt: str) -> str:
    if re.search(r"[\u4e00-\u9fff]", prompt or ""):
        return "zh-CN"
    return "en-US"


def allowed_default_capabilities(profile: str) -> list[str]:
    if profile in {"research", "office"}:
        return ["local-files", "shell", "public-web"]
    return ["local-files", "shell"]


def local_verify(target: RunTarget) -> dict[str, Any]:
    status = read_json(status_path(target), {})
    deliverables = status.get("deliverables") or []
    deliverables = [deliverables] if isinstance(deliverables, str) else deliverables
    findings: list[str] = []
    ok = True
    existing: list[str] = []
    for item in deliverables:
        path = (target.workspace / item).resolve() if not str(item).startswith("/") else Path(item)
        if path.exists() and path.is_file() and path.stat().st_size > 0:
            existing.append(str(path))
        else:
            ok = False
            findings.append(f"missing deliverable: {item}")
    profile = status.get("profile")
    if profile in {"research", "office"}:
        src = sources_path(target)
        artifacts_dir = target.run_dir / "artifacts"
        src_count = 0
        if src.exists():
            src_count = len([line for line in src.read_text(encoding="utf-8").splitlines() if line.strip()])
        artifact_count = len(list(artifacts_dir.glob("*.md"))) if artifacts_dir.exists() else 0
        if src_count < 2:
            ok = False
            findings.append("sources.jsonl has fewer than 2 entries")
        if artifact_count < 1:
            ok = False
            findings.append("artifacts directory has no markdown workstream outputs")
    final_summary = final_summary_path(target)
    return {
        "ok": ok,
        "deliverables": existing,
        "findings": findings,
        "finalSummaryExists": final_summary.exists(),
    }


def clear_active_run_if_matches(target: RunTarget) -> None:
    active = active_run_file(target.base)
    if active.exists() and read_text(active, "").strip() == target.run_id:
        active.unlink()


def stable_source_id(url: str, title: str = "") -> str:
    seed = f"{url}|{title}".encode("utf-8")
    return hashlib.sha1(seed).hexdigest()[:12]


def extract_rate_limit(output: str) -> bool:
    lowered = output.lower()
    return any(re.search(pattern, lowered) for pattern in RATE_LIMIT_PATTERNS)


def parse_json_argument(raw: str | None, default: Any = None) -> Any:
    if raw is None:
        return copy.deepcopy(default)
    if raw.startswith("@"):
        return read_json(Path(raw[1:]).expanduser(), default)
    return json.loads(raw)


def summarize_model_strategy(config: dict[str, Any]) -> str:
    preferred = " -> ".join(display_model_name(item, config) for item in config.get("preferred", []))
    fallback = " -> ".join(display_model_name(item, config) for item in config.get("fallback", []))
    backoff = " -> ".join(f"{m}m" for m in config.get("backoffMinutes", []))
    return (
        f"默认策略: {config.get('defaultPolicy', 'opus-first')}\n"
        f"优先模型: {preferred}\n"
        f"回退链: {fallback}\n"
        f"限流退避: {backoff}"
    )


def init_status_payload(run_id: str, prompt: str, explicit_model: str | None = None, config: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = config or default_model_config()
    profile = infer_profile(prompt)
    complexity = infer_complexity(prompt)
    language = infer_language(prompt)
    chain = model_chain(cfg, explicit_model=explicit_model, prompt_text=prompt)
    selected = chain[0]
    return {
        "runId": run_id,
        "state": "running",
        "phase": "init",
        "summary": "Mission initialized",
        "profile": profile,
        "complexity": complexity,
        "delegationMode": {
            "single-lane": "direct",
            "parallel": "targeted-subagents",
            "fleet": "fleet",
        }[complexity],
        "language": language,
        "evidenceMode": "balanced",
        "modelPolicy": "opus-first",
        "modelPreference": normalize_model_name(explicit_model, cfg),
        "selectedModel": selected,
        "modelAttemptHistory": [
            {
                "ts": now_iso(),
                "model": selected,
                "reason": "user-requested" if normalize_model_name(explicit_model, cfg) else "default-opus-first",
            }
        ],
        "fallbackChain": chain[1:],
        "fallbackReason": None,
        "deliverables": [],
        "completedWorkstreams": [],
        "activeWorkstreams": [],
        "lastError": None,
        "recoveryState": {"phaseAttempts": {}, "backoffHistoryMinutes": []},
        "allowedCapabilities": allowed_default_capabilities(profile),
        "createdAt": now_iso(),
        "updatedAt": now_iso(),
    }


def cli_workspace_and_run(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--workspace", default=os.getcwd())
    parser.add_argument("--run-id", default="active")
