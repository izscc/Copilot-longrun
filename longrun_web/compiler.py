from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any

from .ai_config import get_profile
from .prompt_packs import compose_system_prompt
from .shared_policy import local_mission_draft, local_operator_request, render_compiled_prompt


def _extract_json(text: str) -> dict[str, Any] | None:
    text = (text or '').strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        pass
    match = re.search(r'\{.*\}', text, flags=re.S)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except Exception:
        return None


def _chat_completion(base_url: str, api_key: str, model: str, system_prompt: str, user_prompt: str) -> str:
    url = base_url.rstrip('/') + '/chat/completions'
    payload = {
        'model': model,
        'temperature': 0.2,
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_prompt},
        ],
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}',
        },
        method='POST',
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = json.loads(resp.read().decode('utf-8') or '{}')
    choices = raw.get('choices') or []
    message = choices[0].get('message', {}) if choices else {}
    return str(message.get('content') or '').strip()


def _ai_compile(raw_text: str, *, draft: dict[str, Any], interaction: str, profile_name: str | None, pack_version: str) -> dict[str, Any] | None:
    profile = get_profile(profile_name)
    if not profile or not profile.get('apiKey') or not profile.get('model'):
        return None
    pack = compose_system_prompt(pack_version, profile=draft['profile'], complexity=draft['complexity'], interaction=interaction)
    user_prompt = (
        '请基于下面输入返回 JSON，且只输出 JSON。\n\n'
        'JSON schema:\n'
        '{\n'
        '  "missionDraft": {...},\n'
        '  "compiledPrompt": "...",\n'
        '  "operatorRequest": {\n'
        '    "type": "adjust_plan|append_task|clarify",\n'
        '    "priority": "low|normal|high",\n'
        '    "title": "...",\n'
        '    "rawText": "...",\n'
        '    "normalizedText": "...",\n'
        '    "linkedDeliverables": ["..."],\n'
        '    "linkedArtifacts": ["..."],\n'
        '    "linkedWorkstream": "..."\n'
        '  }\n'
        '}\n\n'
        f'当前草案:\n{json.dumps(draft, ensure_ascii=False, indent=2)}\n\n'
        f'新增用户输入:\n{raw_text}\n'
    )
    try:
        content = _chat_completion(profile['baseUrl'], profile['apiKey'], profile['model'], pack['systemPrompt'], user_prompt)
        parsed = _extract_json(content)
        if isinstance(parsed, dict):
            parsed['packVersion'] = pack['version']
            parsed['systemPrompt'] = pack['systemPrompt']
            return parsed
    except urllib.error.HTTPError as exc:
        return {'error': f'HTTP {exc.code}', 'compiledPrompt': '', 'missionDraft': draft, 'operatorRequest': local_operator_request(raw_text, draft), 'packVersion': pack['version'], 'systemPrompt': pack['systemPrompt']}
    except Exception as exc:
        return {'error': str(exc), 'compiledPrompt': '', 'missionDraft': draft, 'operatorRequest': local_operator_request(raw_text, draft), 'packVersion': pack['version'], 'systemPrompt': pack['systemPrompt']}
    return None


def compile_prompt(raw_text: str, *, previous_draft: dict[str, Any] | None = None, interaction: str = 'initial_compile', profile_name: str | None = None, pack_version: str = 'v1') -> dict[str, Any]:
    draft = local_mission_draft(raw_text, previous_draft, interaction=interaction)
    local_operator = local_operator_request(raw_text, draft)
    local_result = {
        'missionDraft': draft,
        'compiledPrompt': render_compiled_prompt(draft),
        'operatorRequest': local_operator,
        'packVersion': pack_version,
        'systemPrompt': compose_system_prompt(pack_version, profile=draft['profile'], complexity=draft['complexity'], interaction=interaction)['systemPrompt'],
        'source': 'local',
    }
    ai_result = _ai_compile(raw_text, draft=draft, interaction=interaction, profile_name=profile_name, pack_version=pack_version)
    if not ai_result:
        return local_result
    merged_draft = dict(draft)
    merged_draft.update(ai_result.get('missionDraft') or {})
    compiled = ai_result.get('compiledPrompt') or render_compiled_prompt(merged_draft)
    operator_request = dict(local_operator)
    operator_request.update(ai_result.get('operatorRequest') or {})
    return {
        'missionDraft': merged_draft,
        'compiledPrompt': compiled,
        'operatorRequest': operator_request,
        'packVersion': ai_result.get('packVersion', pack_version),
        'systemPrompt': ai_result.get('systemPrompt', local_result['systemPrompt']),
        'source': 'ai' if not ai_result.get('error') else 'local-with-ai-error',
        'error': ai_result.get('error'),
    }


def finalize_prompt(draft: dict[str, Any], *, pack_version: str = 'v1') -> dict[str, Any]:
    return {
        'missionDraft': draft,
        'compiledPrompt': render_compiled_prompt(draft),
        'packVersion': pack_version,
        'source': 'local',
    }
