#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

LONGRUN_HOME = Path(os.environ.get("LONGRUN_HOME", str(Path.home() / ".copilot-mission-control")))
DEFAULT_MODEL_CONFIG = LONGRUN_HOME / "config" / "model-policy.json"
DEFAULT_MODEL_AVAILABILITY = LONGRUN_HOME / "config" / "model-availability.json"
COPILOT_CONFIG_DIR = Path(os.environ.get("COPILOT_CONFIG_DIR", str(Path.home() / ".copilot")))
MANAGED_PLAN_START = "<!-- LONGRUN:STATUS:START -->"
MANAGED_PLAN_END = "<!-- LONGRUN:STATUS:END -->"
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


def completion_path(target: RunTarget) -> Path:
    return target.run_dir / "COMPLETION.md"


def legacy_completion_path(target: RunTarget) -> Path:
    return target.run_dir / "final-summary.md"


def final_summary_path(target: RunTarget) -> Path:
    # Backward-compatible alias. Prefer legacy path if it already exists.
    legacy = legacy_completion_path(target)
    return legacy if legacy.exists() else completion_path(target)


def active_run_file(base: Path) -> Path:
    return base / "state" / "active-run-id"


def default_model_config() -> dict[str, Any]:
    return {
        "defaultPolicy": "latest-available-opus-first",
        "preferred": ["claude-opus-4.6", "claude-opus-4.5"],
        "fallback": ["claude-sonnet-4.6", "claude-sonnet-4.5", "gpt-5.4", "gemini-3.1-pro"],
        "backoffMinutes": [2, 5, 10],
        "availabilityTtlHours": 24,
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


def availability_cache_path(path: str | Path | None = None) -> Path:
    return Path(path).expanduser() if path else DEFAULT_MODEL_AVAILABILITY


def parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def current_copilot_identity(config_dir: str | Path | None = None) -> str:
    for name in ("COPILOT_GITHUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN"):
        if os.environ.get(name):
            return f"env:{name}"
    cfg_dir = Path(config_dir).expanduser() if config_dir else COPILOT_CONFIG_DIR
    cfg_json = cfg_dir / "config.json"
    obj = read_json(cfg_json, {})
    last = obj.get("last_logged_in_user") or {}
    login = last.get("login")
    host = last.get("host") or "https://github.com"
    if login:
        return f"{login}@{host}"
    return "unknown-account"


def account_fingerprint(identity: str) -> str:
    return hashlib.sha1(identity.encode("utf-8")).hexdigest()[:12]


def read_model_availability(path: str | Path | None = None) -> dict[str, Any]:
    cache_path = availability_cache_path(path)
    default = {"version": 1, "accounts": {}}
    raw = read_json(cache_path, default)
    if not isinstance(raw, dict):
        return copy.deepcopy(default)
    raw.setdefault("version", 1)
    raw.setdefault("accounts", {})
    return raw


def write_model_availability(path: str | Path | None, payload: dict[str, Any]) -> Path:
    cache_path = availability_cache_path(path)
    return write_json_atomic(cache_path, payload)


def model_availability_snapshot(
    config: dict[str, Any],
    *,
    cache: dict[str, Any] | None = None,
    path: str | Path | None = None,
    identity: str | None = None,
) -> dict[str, dict[str, Any]]:
    cache_obj = cache or read_model_availability(path)
    ident = identity or current_copilot_identity()
    fingerprint = account_fingerprint(ident)
    ttl_hours = int(config.get("availabilityTtlHours", 24) or 24)
    models = (((cache_obj.get("accounts") or {}).get(fingerprint) or {}).get("models") or {})
    snapshot: dict[str, dict[str, Any]] = {}
    for slug in dict.fromkeys([*config.get("preferred", []), *config.get("fallback", [])]):
        entry = copy.deepcopy(models.get(slug) or {})
        checked = parse_iso(entry.get("checkedAt"))
        if checked is None or (datetime.now(timezone.utc) - checked).total_seconds() > ttl_hours * 3600:
            snapshot[slug] = {
                "status": "unknown",
                "reason": "cache-miss" if not entry else "stale-cache",
                "checkedAt": entry.get("checkedAt"),
            }
            continue
        snapshot[slug] = {
            "status": entry.get("status", "unknown"),
            "reason": entry.get("reason", "cached"),
            "checkedAt": entry.get("checkedAt"),
        }
    return snapshot


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


def model_chain(
    config: dict[str, Any],
    explicit_model: str | None = None,
    prompt_text: str | None = None,
    *,
    availability: dict[str, dict[str, Any]] | None = None,
) -> list[str]:
    detected = normalize_model_name(explicit_model, config)
    if not detected:
        detected = detect_model_from_text(prompt_text, config)
    base_preferred = list(dict.fromkeys(config.get("preferred", [])))
    base_fallback = list(dict.fromkeys(config.get("fallback", [])))
    base_chain = [*base_preferred, *base_fallback]

    def status_of(slug: str) -> str:
        if not availability:
            return "unknown"
        return (availability.get(slug) or {}).get("status", "unknown")

    def ordered(seq: list[str]) -> tuple[list[str], list[str], list[str]]:
        return (
            [item for item in seq if status_of(item) == "available"],
            [item for item in seq if status_of(item) == "unknown"],
            [item for item in seq if status_of(item) == "unavailable"],
        )

    if detected:
        remainder = [item for item in base_chain if item != detected and status_of(item) != "unavailable"]
        unavailable = [item for item in base_chain if item != detected and status_of(item) == "unavailable"]
        return [detected, *remainder, *unavailable]

    preferred_available, preferred_unknown, _preferred_unavailable = ordered(base_preferred)
    fallback_available, fallback_unknown, fallback_unavailable = ordered(base_fallback)
    chain = [
        *preferred_available,
        *preferred_unknown,
        *fallback_available,
        *fallback_unknown,
    ]
    return chain or [*base_chain, *fallback_unavailable]


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
    ttl = config.get("availabilityTtlHours", 24)
    if not isinstance(ttl, int) or ttl <= 0:
        errors.append("availabilityTtlHours must be a positive integer")
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


def default_visible_name_style(language: str | None) -> str:
    return "简体中文" if (language or "zh-CN") == "zh-CN" else "native"


def resolve_artifact_path(target: RunTarget, item: str | Path) -> Path:
    raw = Path(str(item))
    if raw.is_absolute():
        return raw
    run_candidate = (target.run_dir / raw).resolve()
    if run_candidate.exists():
        return run_candidate
    workspace_candidate = (target.workspace / raw).resolve()
    if workspace_candidate.exists():
        return workspace_candidate
    if str(raw).startswith("artifacts/"):
        return run_candidate
    return workspace_candidate


def display_artifact_path(target: RunTarget, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(target.run_dir.resolve())).replace("\\", "/")
    except ValueError:
        pass
    try:
        return str(path.resolve().relative_to(target.workspace.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


def artifact_id_for_path(path_text: str) -> str:
    digest = hashlib.sha1(path_text.encode("utf-8")).hexdigest()[:12]
    stem = Path(path_text).stem
    if re.search(r"[\u4e00-\u9fff]", stem):
        prefix = "artifact"
    else:
        prefix = slugify(stem, max_len=24)
    return f"{prefix}-{digest}" if prefix else f"artifact-{digest}"


def ensure_status_defaults(status: dict[str, Any] | None) -> dict[str, Any]:
    payload = copy.deepcopy(status or {})
    payload.setdefault("deliverables", [])
    payload.setdefault("completedWorkstreams", [])
    payload.setdefault("activeWorkstreams", [])
    payload.setdefault("fallbackChain", [])
    payload.setdefault("lastError", None)
    payload.setdefault("artifacts", [])
    payload.setdefault("verification", {})
    verification = payload.get("verification") or {}
    verification.setdefault("state", "pending")
    verification.setdefault("hardFailures", [])
    verification.setdefault("softWarnings", [])
    verification.setdefault("driftFindings", [])
    verification.setdefault("recommendedAction", "continue")
    verification.setdefault("failureClass", None)
    verification.setdefault("lastVerifiedAt", None)
    payload["verification"] = verification
    recovery = payload.get("recoveryState") or {}
    recovery.setdefault("phaseAttempts", {})
    recovery.setdefault("backoffHistoryMinutes", [])
    recovery.setdefault("failureClass", None)
    recovery.setdefault("retryCount", 0)
    recovery.setdefault("lastRecommendedAction", None)
    payload["recoveryState"] = recovery
    language = payload.get("language") or "zh-CN"
    naming = payload.get("naming") or {}
    naming.setdefault("defaultLocale", language)
    naming.setdefault("defaultVisibleNameStyle", default_visible_name_style(language))
    payload["naming"] = naming
    return payload


def refresh_artifact_inventory(target: RunTarget, status: dict[str, Any] | None) -> dict[str, Any]:
    payload = ensure_status_defaults(status)
    existing_by_key: dict[str, dict[str, Any]] = {}
    for item in payload.get("artifacts") or []:
        if not isinstance(item, dict):
            continue
        key = item.get("path") or item.get("id")
        if key:
            existing_by_key[str(key)] = copy.deepcopy(item)

    deliverables = [str(item) for item in payload.get("deliverables") or [] if item]
    discovered_paths: dict[str, Path] = {}

    artifacts_dir = target.run_dir / "artifacts"
    if artifacts_dir.exists():
        for path in sorted(p for p in artifacts_dir.rglob("*") if p.is_file()):
            rel = display_artifact_path(target, path)
            discovered_paths[rel] = path

    for item in deliverables:
        path = resolve_artifact_path(target, item)
        discovered_paths.setdefault(item, path)

    profile = payload.get("profile")
    records: list[dict[str, Any]] = []
    for rel in sorted(discovered_paths):
        path = discovered_paths[rel]
        prior = existing_by_key.get(rel, {})
        state = "present" if path.exists() and path.is_file() and path.stat().st_size > 0 else "missing"
        required = bool(prior.get("required")) or rel in deliverables
        source_requirement = prior.get("sourceRequirement")
        if not source_requirement:
            if profile in {"research", "office"} and rel.startswith("artifacts/"):
                source_requirement = "recommended"
            else:
                source_requirement = "none"
        records.append({
            "id": prior.get("id") or artifact_id_for_path(rel),
            "path": rel,
            "displayName": prior.get("displayName") or Path(rel).stem,
            "role": prior.get("role") or ("deliverable" if rel in deliverables else "artifact"),
            "required": required,
            "sourceRequirement": source_requirement,
            "state": state,
        })

    payload["artifacts"] = records
    return payload


def infer_completed_workstreams(target: RunTarget, status: dict[str, Any]) -> list[str]:
    existing = [str(item) for item in status.get("completedWorkstreams") or [] if item]
    if existing:
        return existing
    discovered: list[str] = []
    for item in status.get("artifacts") or []:
        if not isinstance(item, dict) or item.get("state") != "present":
            continue
        path_text = str(item.get("path") or "")
        if path_text.startswith("artifacts/"):
            remainder = path_text[len("artifacts/") :]
            token = remainder.split("/", 1)[0] if remainder else ""
            label = "artifacts-top-level" if not token or token.endswith(".md") else token
        else:
            label = "deliverables"
        if label not in discovered:
            discovered.append(label)
    if status.get("state") in {"complete", "blocked"} and "finalize" not in discovered:
        discovered.append("finalize")
    return discovered


def remove_duplicate_status_sections(plan_text: str) -> str:
    if "## LongRun Status Board" not in plan_text:
        return plan_text
    managed_removed = re.sub(
        re.escape(MANAGED_PLAN_START) + r".*?" + re.escape(MANAGED_PLAN_END),
        "",
        plan_text,
        count=1,
        flags=re.S,
    )
    if "## LongRun Status Board" not in managed_removed:
        return plan_text
    cleaned_unmanaged = re.sub(
        r"\n## LongRun Status Board\n.*?(?=\n## [^\n]+|\Z)",
        "\n",
        managed_removed,
        flags=re.S,
    )
    board_match = re.search(
        re.escape(MANAGED_PLAN_START) + r".*?" + re.escape(MANAGED_PLAN_END),
        plan_text,
        flags=re.S,
    )
    if board_match:
        prefix = plan_text[: board_match.start()]
        board = board_match.group(0)
        suffix = cleaned_unmanaged
        return (prefix + board + suffix).strip() + "\n"
    return cleaned_unmanaged.strip() + "\n"


def classify_failure(
    hard_failures: Iterable[str] | None = None,
    drift_findings: Iterable[str] | None = None,
    *,
    last_error: str | None = None,
) -> tuple[str | None, str]:
    issues = " ".join([*(hard_failures or []), *(drift_findings or []), last_error or ""]).lower()
    if "dangerous shell expansion" in issues:
        return "shell_block", "rewrite shell checks to helper-first or python heredoc, then retry verify"
    if "plan.md" in issues or "active-run-id" in issues or "drift" in issues or "duplicate unmanaged status" in issues:
        return "state_drift", "run reconcile_run.py before the next verify/finalize"
    if "sources.jsonl" in issues or "source" in issues:
        return "source_gap", "run harvest_sources.py, then re-run reconcile_run.py and verify_run.py"
    if "missing deliverable" in issues or "deliverable" in issues:
        return "verification_gap", "fix deliverable paths or produce the missing deliverable before finalize"
    if extract_rate_limit(issues):
        return "rate_limited", "wait for backoff or fallback model recovery, then retry"
    if issues.strip():
        return "tool_failure", "inspect the last failed step and retry with a smaller change"
    return None, "continue"


def canonical_phase_name(value: str | None) -> str:
    token = (value or "").strip().lower()
    mapping = {
        "init": "plan",
        "explore": "explore",
        "research": "execute",
        "plan": "plan",
        "execute": "execute",
        "synthesis": "execute",
        "verify": "verify",
        "verification": "verify",
        "recover": "recover",
        "recovery": "recover",
        "finalize": "finalize",
    }
    return mapping.get(token, "execute")


def _status_board_lines(target: RunTarget, status: dict[str, Any]) -> list[str]:
    canonical_phase = canonical_phase_name(status.get("phase"))
    phase_order = ["explore", "plan", "execute", "verify", "recover", "finalize"]
    labels = {
        "explore": "Explore",
        "plan": "Plan",
        "execute": "Execute",
        "verify": "Verify",
        "recover": "Recover",
        "finalize": "Finalize",
    }
    current_index = phase_order.index(canonical_phase) if canonical_phase in phase_order else 2
    run_state = status.get("state", "running")
    lines = [
        MANAGED_PLAN_START,
        "## LongRun Status Board",
        "",
        f"- State: `{run_state}`",
        f"- Phase: `{status.get('phase', 'unknown')}`",
        f"- Model: `{status.get('selectedModel', 'unknown')}`",
        f"- Model control: `{status.get('modelControlMode', 'unknown')}`",
        "",
        "### Phase Progress",
    ]
    for idx, phase in enumerate(phase_order):
        checked = idx < current_index or (idx == current_index and run_state in {"complete", "blocked"}) or (run_state in {"complete", "blocked"} and phase == "finalize")
        box = "x" if checked else " "
        lines.append(f"- [{box}] {labels[phase]}")

    completed = list(status.get("completedWorkstreams") or infer_completed_workstreams(target, status))
    active = list(status.get("activeWorkstreams") or [])
    if completed or active:
        lines.extend(["", "### Workstream Progress"])
        seen: list[str] = []
        for item in [*completed, *active]:
            if item and item not in seen:
                seen.append(item)
        for item in seen:
            box = "x" if item in completed else " "
            lines.append(f"- [{box}] {item}")

    delivered = list(status.get("deliverables") or [])
    lines.extend(["", "### Deliverables"])
    if delivered:
        lines.extend(f"- [x] `{item}`" for item in delivered)
    else:
        lines.append("- [ ] None recorded")

    lines.append(MANAGED_PLAN_END)
    return lines


def sync_plan_markdown(target: RunTarget, status: dict[str, Any] | None = None) -> Path:
    status_obj = refresh_artifact_inventory(target, status or read_json(status_path(target), {}))
    plan_file = target.run_dir / "plan.md"
    original = remove_duplicate_status_sections(read_text(plan_file, "")).strip()
    board = "\n".join(_status_board_lines(target, status_obj)).strip()
    if MANAGED_PLAN_START in original and MANAGED_PLAN_END in original:
        updated = re.sub(
            re.escape(MANAGED_PLAN_START) + r".*?" + re.escape(MANAGED_PLAN_END),
            board,
            original,
            count=1,
            flags=re.S,
        )
    elif original:
        if original.startswith("# "):
            first_newline = original.find("\n")
            if first_newline != -1:
                updated = original[: first_newline + 1] + "\n" + board + "\n\n" + original[first_newline + 1 :].lstrip()
            else:
                updated = original + "\n\n" + board
        else:
            updated = board + "\n\n" + original
    else:
        updated = "# Mission Plan\n\n" + board + "\n"
    return write_text_atomic(plan_file, updated.strip() + "\n")


def plan_sync_findings(target: RunTarget, status: dict[str, Any] | None = None) -> list[str]:
    status_obj = refresh_artifact_inventory(target, status or read_json(status_path(target), {}))
    findings: list[str] = []
    plan_text = read_text(target.run_dir / "plan.md", "")
    if MANAGED_PLAN_START not in plan_text or MANAGED_PLAN_END not in plan_text:
        findings.append("plan.md is missing the managed LongRun status board")
    unmanaged = re.sub(
        re.escape(MANAGED_PLAN_START) + r".*?" + re.escape(MANAGED_PLAN_END),
        "",
        plan_text,
        count=1,
        flags=re.S,
    )
    if "## LongRun Status Board" in unmanaged:
        findings.append("plan.md contains duplicate unmanaged status sections")
    if re.search(r"^\| State \| running \|", unmanaged, flags=re.M):
        findings.append("plan.md contains stale running state outside the managed board")
    if re.search(r"^- \[ \] (Explore|Plan|Execute|Verify|Recover|Finalize)", unmanaged, flags=re.M):
        findings.append("plan.md contains unchecked stale phase items outside the managed board")
    if status_obj.get("state") in {"complete", "blocked"}:
        if list(status_obj.get("activeWorkstreams") or []):
            findings.append("status is finalized but activeWorkstreams is not empty")
        if not list(status_obj.get("deliverables") or []):
            findings.append("status is finalized but deliverables is empty")
        active = active_run_file(target.base)
        if active.exists() and read_text(active, "").strip() == target.run_id:
            findings.append("state/active-run-id still points to finalized run")
    return findings


def local_verify(target: RunTarget, status_override: dict[str, Any] | None = None) -> dict[str, Any]:
    status = refresh_artifact_inventory(target, status_override or read_json(status_path(target), {}))
    deliverables = status.get("deliverables") or []
    deliverables = [deliverables] if isinstance(deliverables, str) else deliverables
    hard_failures: list[str] = []
    soft_warnings: list[str] = []
    drift_findings: list[str] = []
    existing: list[str] = []
    for item in deliverables:
        path = resolve_artifact_path(target, item)
        if path.exists() and path.is_file() and path.stat().st_size > 0:
            existing.append(str(path))
        else:
            hard_failures.append(f"missing deliverable: {item}")
    profile = status.get("profile")
    if profile in {"research", "office"}:
        src = sources_path(target)
        artifacts_dir = target.run_dir / "artifacts"
        src_count = 0
        if src.exists():
            src_count = len([line for line in src.read_text(encoding="utf-8").splitlines() if line.strip()])
        artifact_count = len(list(p for p in artifacts_dir.rglob("*.md"))) if artifacts_dir.exists() else 0
        source_modes = {str((item or {}).get("sourceRequirement") or "none") for item in status.get("artifacts") or [] if isinstance(item, dict)}
        source_required = profile == "research" or "required" in source_modes
        source_recommended = source_required or profile == "office" or "recommended" in source_modes
        if src_count < 1 and source_required:
            hard_failures.append("sources.jsonl has no recorded entries")
        elif src_count < 1 and source_recommended:
            soft_warnings.append("sources.jsonl has no recorded entries")
        if artifact_count < 1:
            hard_failures.append("artifacts directory has no markdown workstream outputs")
    drift_findings.extend(plan_sync_findings(target, status))
    completion = completion_path(target)
    legacy_completion = legacy_completion_path(target)
    if status.get("state") in {"complete", "blocked"} and not completion.exists() and not legacy_completion.exists():
        hard_failures.append("COMPLETION.md is missing for finalized run")
    elif status.get("state") in {"complete", "blocked"} and legacy_completion.exists() and not completion.exists():
        soft_warnings.append("legacy final-summary.md exists without COMPLETION.md")
    failure_class, recommended_action = classify_failure(
        hard_failures,
        drift_findings,
        last_error=((status.get("lastError") or {}).get("message") if isinstance(status.get("lastError"), dict) else str(status.get("lastError") or "")),
    )
    ok = not hard_failures and not drift_findings
    return {
        "ok": ok,
        "deliverables": existing,
        "findings": [*hard_failures, *soft_warnings, *drift_findings],
        "hardFailures": hard_failures,
        "softWarnings": soft_warnings,
        "driftFindings": drift_findings,
        "recommendedAction": recommended_action,
        "failureClass": failure_class,
        "completionExists": completion.exists() or legacy_completion.exists(),
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


def summarize_model_strategy(config: dict[str, Any], availability: dict[str, dict[str, Any]] | None = None) -> str:
    availability = availability or model_availability_snapshot(config)
    available_preferred = [item for item in config.get("preferred", []) if availability.get(item, {}).get("status") == "available"]
    latest_opus = display_model_name(available_preferred[0], config) if available_preferred else "None detected"
    preferred = " -> ".join(display_model_name(item, config) for item in config.get("preferred", []))
    fallback = " -> ".join(display_model_name(item, config) for item in config.get("fallback", []))
    backoff = " -> ".join(f"{m}m" for m in config.get("backoffMinutes", []))
    return (
        f"默认策略: {config.get('defaultPolicy', 'latest-available-opus-first')}\n"
        f"当前账号可用的最新 Opus: {latest_opus}\n"
        f"优先模型: {preferred}\n"
        f"回退链: {fallback}\n"
        f"限流退避: {backoff}"
    )


def init_status_payload(
    run_id: str,
    prompt: str,
    explicit_model: str | None = None,
    *,
    session_model: str | None = None,
    model_control_mode: str | None = None,
    config: dict[str, Any] | None = None,
    availability: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    cfg = config or default_model_config()
    profile = infer_profile(prompt)
    complexity = infer_complexity(prompt)
    language = infer_language(prompt)
    preferred_model = normalize_model_name(explicit_model, cfg) or detect_model_from_text(prompt, cfg)
    normalized_session_model = normalize_model_name(session_model, cfg) or session_model
    if normalized_session_model:
        chain = model_chain(cfg, explicit_model=normalized_session_model, availability=availability)
        selected = normalized_session_model
        control_mode = model_control_mode or "launcher-enforced"
        fallback = [item for item in chain if item != selected]
        reason = "launcher-selected" if control_mode == "launcher-enforced" else "explicit-session-model"
    else:
        selected = "session-inherited"
        control_mode = model_control_mode or "session-inherited"
        fallback = []
        reason = "session-inherited"
    return ensure_status_defaults({
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
        "modelPolicy": cfg.get("defaultPolicy", "latest-available-opus-first"),
        "modelPreference": preferred_model,
        "selectedModel": selected,
        "modelControlMode": control_mode,
        "modelAttemptHistory": [
            {
                "ts": now_iso(),
                "model": selected,
                "reason": reason,
            }
        ],
        "fallbackChain": fallback,
        "fallbackReason": None,
        "deliverables": [],
        "completedWorkstreams": [],
        "activeWorkstreams": [],
        "artifacts": [],
        "lastError": None,
        "verification": {
            "state": "pending",
            "hardFailures": [],
            "softWarnings": [],
            "driftFindings": [],
            "recommendedAction": "continue",
            "failureClass": None,
            "lastVerifiedAt": None,
        },
        "recoveryState": {
            "phaseAttempts": {},
            "backoffHistoryMinutes": [],
            "failureClass": None,
            "retryCount": 0,
            "lastRecommendedAction": None,
        },
        "naming": {
            "defaultLocale": language,
            "defaultVisibleNameStyle": default_visible_name_style(language),
        },
        "allowedCapabilities": allowed_default_capabilities(profile),
        "createdAt": now_iso(),
        "updatedAt": now_iso(),
    })


def cli_workspace_and_run(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--workspace", default=os.getcwd())
    parser.add_argument("--run-id", default="active")
