#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from _longrun_lib import append_jsonl, now_iso, read_text, resolve_run_target, sources_path, stable_source_id  # noqa: E402

URL_RE = re.compile(r'https?://[^\s)>\"]+')
BACKTICK_RE = re.compile(r"`([^`]+)`")
BARE_PATH_RE = re.compile(r"(?<![\w/.-])((?:src|scripts|config|docs|agents|skills|integrations|reports)/[^\s`'\")>]+)")
FILE_TOKEN_RE = re.compile(r"^(?:README\.md|package(?:-lock)?\.json|plugin\.json|hooks\.json|[^\s]+\.(?:md|json|ts|tsx|js|jsx|py|sh|toml|yaml|yml))$")


def looks_like_repo_path(text: str) -> bool:
    token = text.strip().strip('"\'')
    if not token or token.startswith(("http://", "https://", "/", "repo://", "file://")):
        return False
    if " " in token:
        return False
    if token.startswith(("src/", "scripts/", "config/", "docs/", "agents/", "skills/", "integrations/", "reports/")):
        return True
    return bool(FILE_TOKEN_RE.match(token))


def load_existing(path: Path) -> set[tuple[str, str, str]]:
    existing: set[tuple[str, str, str]] = set()
    for line in read_text(path, "").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        existing.add((str(obj.get("id") or ""), str(obj.get("url") or ""), str(obj.get("usedIn") or "")))
    return existing


def iter_candidate_sources(markdown_text: str) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for url in URL_RE.findall(markdown_text):
        found.append((url, "web"))
    for token in BACKTICK_RE.findall(markdown_text):
        if looks_like_repo_path(token):
            found.append((token, "repo"))
    for token in BARE_PATH_RE.findall(markdown_text):
        if looks_like_repo_path(token):
            found.append((token, "repo"))
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description="Harvest sources from existing LongRun artifacts")
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--run-id", default="active")
    parser.add_argument("--print", action="store_true", dest="do_print")
    args = parser.parse_args()

    target = resolve_run_target(args.workspace, args.run_id)
    src_path = sources_path(target)
    existing = load_existing(src_path)
    added: list[dict[str, str]] = []

    candidate_files = sorted(p for p in (target.run_dir / "artifacts").rglob("*.md") if p.is_file())
    for artifact in candidate_files:
        used_in = str(artifact.relative_to(target.run_dir)).replace("\\", "/")
        text = read_text(artifact, "")
        for raw, kind in iter_candidate_sources(text):
            if kind == "web":
                url = raw
                title = raw
            else:
                clean = raw.strip().strip('"\'')
                url = f"repo://{clean}"
                title = clean
            source_id = stable_source_id(url, title)
            key = (source_id, url, used_in)
            if key in existing:
                continue
            payload = {
                "id": source_id,
                "title": title,
                "url": url,
                "kind": kind,
                "capturedAt": now_iso(),
                "usedIn": used_in,
            }
            append_jsonl(src_path, payload)
            existing.add(key)
            added.append(payload)

    result = {"ok": True, "runId": target.run_id, "added": len(added), "sources": added}
    if args.do_print:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"ok": True, "runId": target.run_id, "added": len(added)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
