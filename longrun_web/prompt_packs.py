from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .bridge import LONGRUN_HOME, REPO_ROOT

PACK_ROOT = REPO_ROOT / 'prompt_packs' / 'longrun-compiler'
OVERRIDE_PATH = LONGRUN_HOME / 'web' / 'prompt-pack-overrides.json'


def list_pack_versions() -> list[str]:
    if not PACK_ROOT.exists():
        return []
    return sorted(path.name for path in PACK_ROOT.iterdir() if path.is_dir())


def _read(path: Path) -> str:
    return path.read_text(encoding='utf-8').strip() if path.exists() else ''


def load_overrides() -> dict[str, Any]:
    if not OVERRIDE_PATH.exists():
        return {}
    try:
        return json.loads(OVERRIDE_PATH.read_text(encoding='utf-8'))
    except Exception:
        return {}


def save_overrides(payload: dict[str, Any]) -> None:
    OVERRIDE_PATH.parent.mkdir(parents=True, exist_ok=True)
    OVERRIDE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def compose_system_prompt(version: str, *, profile: str, complexity: str, interaction: str) -> dict[str, Any]:
    version = version or 'v1'
    root = PACK_ROOT / version
    pieces = {
        'base': _read(root / 'base.md'),
        'profile': _read(root / f'profile-{profile}.md'),
        'complexity': _read(root / f'complexity-{complexity}.md'),
        'interaction': _read(root / f'interaction-{interaction}.md'),
    }
    overrides = load_overrides().get(version, {}) if root.exists() else {}
    replace = overrides.get('replace', {}) if isinstance(overrides, dict) else {}
    append = overrides.get('append', {}) if isinstance(overrides, dict) else {}
    for key, value in replace.items():
        if key in pieces and value:
            pieces[key] = str(value).strip()
    for key, value in append.items():
        if key in pieces and value:
            pieces[key] = (pieces[key] + '\n\n' + str(value).strip()).strip()
    system_prompt = '\n\n'.join(part for part in pieces.values() if part).strip()
    return {
        'version': version,
        'pieces': pieces,
        'systemPrompt': system_prompt,
    }
