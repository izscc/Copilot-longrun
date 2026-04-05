from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from .bridge import LONGRUN_HOME

WEB_HOME = LONGRUN_HOME / 'web'
AI_PROFILE_PATH = WEB_HOME / 'ai-profiles.json'
DEFAULT_BASE_URL = 'https://api.zscc.in/v1'


def _load() -> dict[str, Any]:
    if not AI_PROFILE_PATH.exists():
        return {'defaultProfile': None, 'profiles': []}
    try:
        return json.loads(AI_PROFILE_PATH.read_text(encoding='utf-8'))
    except Exception:
        return {'defaultProfile': None, 'profiles': []}


def _save(payload: dict[str, Any]) -> None:
    WEB_HOME.mkdir(parents=True, exist_ok=True)
    AI_PROFILE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def _mask(profile: dict[str, Any]) -> dict[str, Any]:
    clone = dict(profile)
    key = clone.pop('apiKey', '')
    clone['hasKey'] = bool(key)
    if key:
        clone['keyPreview'] = f"{key[:4]}***{key[-4:]}" if len(key) > 8 else '***'
    return clone


def list_profiles(masked: bool = True) -> dict[str, Any]:
    payload = _load()
    profiles = payload.get('profiles', [])
    if masked:
        profiles = [_mask(item) for item in profiles]
    return {'defaultProfile': payload.get('defaultProfile'), 'profiles': profiles}


def get_profile(name: str | None = None) -> dict[str, Any] | None:
    payload = _load()
    selected = name or payload.get('defaultProfile')
    for item in payload.get('profiles', []):
        if item.get('name') == selected:
            return item
    profiles = payload.get('profiles') or []
    return profiles[0] if profiles else None


def save_profile(profile: dict[str, Any]) -> dict[str, Any]:
    payload = _load()
    items = [item for item in payload.get('profiles', []) if item.get('name') != profile.get('name')]
    normalized = {
        'name': profile.get('name') or 'default',
        'baseUrl': (profile.get('baseUrl') or DEFAULT_BASE_URL).rstrip('/'),
        'apiKey': profile.get('apiKey') or '',
        'model': profile.get('model') or '',
        'provider': profile.get('provider') or 'openai-compatible',
    }
    items.append(normalized)
    payload['profiles'] = sorted(items, key=lambda item: item.get('name') or '')
    payload['defaultProfile'] = profile.get('defaultProfile') or payload.get('defaultProfile') or normalized['name']
    if profile.get('setDefault'):
        payload['defaultProfile'] = normalized['name']
    _save(payload)
    return _mask(normalized)


def _request_json(url: str, *, api_key: str = '', method: str = 'GET', body: dict[str, Any] | None = None) -> dict[str, Any]:
    headers = {'Content-Type': 'application/json'}
    if api_key:
        headers['Authorization'] = f'Bearer {api_key}'
    data = json.dumps(body).encode('utf-8') if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=20) as resp:
        raw = resp.read().decode('utf-8')
    return json.loads(raw) if raw else {}


def fetch_models(profile_name: str | None = None) -> dict[str, Any]:
    profile = get_profile(profile_name)
    if not profile:
        return {'ok': False, 'error': 'No AI profile configured', 'models': []}
    url = profile['baseUrl'].rstrip('/') + '/models'
    try:
        payload = _request_json(url, api_key=profile.get('apiKey', ''))
        models = payload.get('data') if isinstance(payload, dict) else []
        names = []
        for item in models or []:
            if isinstance(item, dict) and item.get('id'):
                names.append(item['id'])
        return {'ok': True, 'models': sorted(names), 'profile': profile.get('name')}
    except urllib.error.HTTPError as exc:
        return {'ok': False, 'error': f'HTTP {exc.code}', 'models': [], 'profile': profile.get('name')}
    except Exception as exc:
        return {'ok': False, 'error': str(exc), 'models': [], 'profile': profile.get('name')}


def test_profile_connection(profile: dict[str, Any]) -> dict[str, Any]:
    saved = save_profile(profile)
    models = fetch_models(profile.get('name') or saved.get('name'))
    return {'ok': models.get('ok', False), 'profile': saved, 'models': models.get('models', []), 'error': models.get('error')}
