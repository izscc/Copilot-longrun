#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from _longrun_lib import (  # noqa: E402
    account_fingerprint,
    availability_cache_path,
    current_copilot_identity,
    display_model_name,
    extract_rate_limit,
    load_model_config,
    now_iso,
    parse_iso,
    read_model_availability,
    validate_model_config,
    write_model_availability,
)

UNAVAILABLE_SNIPPETS = [
    'unknown model',
    'invalid model',
    'from --model flag is not available',
    'not available to your account',
    'you do not have access',
    'cannot use model',
    'model is not supported',
    'not found',
]


def probe_one(copilot_bin: str, model: str, timeout: int) -> tuple[str, str]:
    cmd = [
        copilot_bin,
        '--model', model,
        '--no-custom-instructions',
        '--no-ask-user',
        '--yolo',
        '--stream', 'off',
        '--silent',
        '--prompt', 'Reply with exactly OK.',
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return 'unknown', 'probe-timeout'
    output = '\n'.join(part for part in [proc.stdout, proc.stderr] if part).strip().lower()
    if proc.returncode == 0:
        return 'available', 'probe-success'
    if extract_rate_limit(output):
        return 'available', 'rate-limited-during-probe'
    for snippet in UNAVAILABLE_SNIPPETS:
        if snippet in output:
            return 'unavailable', snippet
    return 'unknown', f'probe-exit-{proc.returncode}'


def main() -> int:
    parser = argparse.ArgumentParser(description='Probe Copilot model availability and cache the result')
    parser.add_argument('--copilot-bin', default='copilot')
    parser.add_argument('--config')
    parser.add_argument('--cache')
    parser.add_argument('--scope', choices=['preferred', 'all'], default='preferred')
    parser.add_argument('--refresh', action='store_true')
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--timeout-seconds', type=int, default=45)
    args = parser.parse_args()

    config = load_model_config(args.config)
    errors = validate_model_config(config)
    if errors:
        if args.json:
            print(json.dumps({'ok': False, 'errors': errors}, ensure_ascii=False, indent=2))
        else:
            print('\n'.join(errors), file=sys.stderr)
        return 2

    models = list(dict.fromkeys(config.get('preferred', []) + (config.get('fallback', []) if args.scope == 'all' else [])))
    identity = current_copilot_identity()
    fingerprint = account_fingerprint(identity)
    cache_path = availability_cache_path(args.cache)
    cache = read_model_availability(cache_path)
    accounts = cache.setdefault('accounts', {})
    account = accounts.setdefault(fingerprint, {'identity': identity, 'models': {}})
    account['identity'] = identity
    account.setdefault('models', {})
    ttl_hours = int(config.get('availabilityTtlHours', 24) or 24)
    now_dt = datetime.now(timezone.utc)

    for model in models:
        entry = account['models'].get(model) or {}
        checked_at = parse_iso(entry.get('checkedAt'))
        fresh = checked_at is not None and (now_dt - checked_at).total_seconds() <= ttl_hours * 3600
        if entry.get('status') in {'available', 'unavailable'} and fresh and not args.refresh:
            continue
        status, reason = probe_one(args.copilot_bin, model, args.timeout_seconds)
        account['models'][model] = {
            'status': status,
            'reason': reason,
            'checkedAt': now_iso(),
            'displayName': display_model_name(model, config),
        }

    cache['version'] = 1
    write_model_availability(cache_path, cache)

    latest_available_opus = None
    for model in config.get('preferred', []):
        if (account['models'].get(model) or {}).get('status') == 'available':
            latest_available_opus = model
            break

    payload = {
        'ok': True,
        'identity': identity,
        'accountFingerprint': fingerprint,
        'cache': str(cache_path),
        'scope': args.scope,
        'latestAvailableOpus': latest_available_opus,
        'models': {model: account['models'].get(model, {'status': 'unknown', 'reason': 'not-probed'}) for model in models},
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"账号: {identity}")
        print(f"缓存: {cache_path}")
        print(f"当前账号可用的最新 Opus: {display_model_name(latest_available_opus, config) if latest_available_opus else 'None detected'}")
        for model in models:
            item = account['models'].get(model, {'status': 'unknown', 'reason': 'not-probed'})
            print(f"- {display_model_name(model, config)}: {item.get('status')} ({item.get('reason')})")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
