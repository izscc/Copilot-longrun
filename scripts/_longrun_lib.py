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


def final_summary_path(target: RunTarget) -> Path:
    return target.run_dir / "final-summary.md"


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

    completed = list(status.get("completedWorkstreams") or [])
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
    status_obj = status or read_json(status_path(target), {})
    plan_file = target.run_dir / "plan.md"
    original = read_text(plan_file, "").strip()
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
    status_obj = status or read_json(status_path(target), {})
    findings: list[str] = []
    plan_text = read_text(target.run_dir / "plan.md", "")
    if MANAGED_PLAN_START not in plan_text or MANAGED_PLAN_END not in plan_text:
        findings.append("plan.md is missing the managed LongRun status board")
    if status_obj.get("state") in {"complete", "blocked"}:
        if list(status_obj.get("activeWorkstreams") or []):
            findings.append("status is finalized but activeWorkstreams is not empty")
        if not list(status_obj.get("deliverables") or []):
            findings.append("status is finalized but deliverables is empty")
        active = active_run_file(target.base)
        if active.exists() and read_text(active, "").strip() == target.run_id:
            findings.append("state/active-run-id still points to finalized run")
    return findings


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
        for artifact in sorted(artifacts_dir.glob("*.md")) if artifacts_dir.exists() else []:
            text = read_text(artifact, "")
            if "## Sources" not in text and "## 来源" not in text and "### 核心来源" not in text:
                ok = False
                findings.append(f"{artifact.name} is missing a Sources section")
            if not re.search(r"^##?\s*(Findings|结论|研究摘要|关键洞察|研究背景)\b", text, flags=re.M):
                ok = False
                findings.append(f"{artifact.name} is missing a Findings/summary section")
            has_evidence = bool(re.search(r"^##?\s*(Evidence|证据)\b", text, flags=re.M))
            has_open_questions = bool(re.search(r"^##?\s*(Open Questions|待确认问题)\b", text, flags=re.M))
            if not (has_evidence or has_open_questions or len(re.findall(r"https?://\S+", text)) >= 2):
                ok = False
                findings.append(f"{artifact.name} is missing evidence/open-questions structure")
    for finding in plan_sync_findings(target, status):
        ok = False
        findings.append(finding)
    final_summary = final_summary_path(target)
    if status.get("state") in {"complete", "blocked"} and not final_summary.exists():
        ok = False
        findings.append("final-summary.md is missing for finalized run")
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
        "lastError": None,
        "recoveryState": {"phaseAttempts": {}, "backoffHistoryMinutes": []},
        "allowedCapabilities": allowed_default_capabilities(profile),
        "createdAt": now_iso(),
        "updatedAt": now_iso(),
    }


def cli_workspace_and_run(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--workspace", default=os.getcwd())
    parser.add_argument("--run-id", default="active")
