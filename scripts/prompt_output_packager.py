#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
from datetime import datetime
from pathlib import Path


NOISY_PREFIXES = (
    "[LongRun] attempt",
)

PROMPT_SECTION_TITLES = [
    "可直接执行 Prompt",
    "可复制 Prompt",
    "待执行 Prompt",
    "Prompt",
]

COMMAND_SECTION_TITLES = [
    "推荐启动命令",
    "推荐执行命令",
    "执行命令",
    "Launch Command",
    "Recommended Launch Command",
]

NON_PROMPT_FENCE_LANGS = {"bash", "sh", "shell", "zsh", "json", "yaml", "yml"}


def now_suffix() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def backup_if_exists(path: Path) -> None:
    if not path.exists():
        return
    backup = path.with_name(f"{path.stem}.bak.{now_suffix()}{path.suffix}")
    path.rename(backup)


def cleaned_output(text: str) -> str:
    lines = []
    for line in text.splitlines():
        if line.startswith(NOISY_PREFIXES):
            continue
        lines.append(line.rstrip())
    return "\n".join(lines).strip() + "\n"


def extract_first_fence(text: str) -> tuple[str | None, str | None]:
    match = re.search(r"(?ms)^```([^\n`]*)\n(.*?)\n```", text.strip())
    if not match:
        return None, None
    lang = (match.group(1) or "").strip().lower()
    body = (match.group(2) or "").strip()
    return lang, body


def extract_section_fence(text: str, titles: list[str]) -> str | None:
    for title in titles:
        pattern = re.compile(
            rf"(?ms)^[#]{{1,6}}\s*{re.escape(title)}\s*$.*?^```([^\n`]*)\n(.*?)\n```"
        )
        match = pattern.search(text)
        if match:
            block = (match.group(2) or "").strip()
            if block:
                return block
    return None


def fallback_prompt_fence(text: str) -> str | None:
    matches = re.findall(r"(?ms)^```([^\n`]*)\n(.*?)\n```", text.strip())
    candidates: list[str] = []
    for lang, body in matches:
        normalized = (lang or "").strip().lower()
        if normalized in NON_PROMPT_FENCE_LANGS:
            continue
        body = body.strip()
        if body:
            candidates.append(body)
    if not candidates:
        return None
    return max(candidates, key=len)


def quoted_cat_command(path: Path) -> str:
    path_text = shlex.quote(str(path.resolve()))
    return f'longrun "$(cat {path_text})"'


def copy_to_clipboard(text: str) -> bool:
    if shutil.which("pbcopy") is None:
        return False
    completed = subprocess.run(["pbcopy"], input=text, text=True, capture_output=True)
    return completed.returncode == 0


def auto_open(path: Path) -> bool:
    if sys_platform() == "darwin" and shutil.which("open"):
        return subprocess.run(["open", str(path)], capture_output=True).returncode == 0
    if sys_platform() == "linux" and shutil.which("xdg-open"):
        return subprocess.run(["xdg-open", str(path)], capture_output=True).returncode == 0
    return False


def sys_platform() -> str:
    return os.uname().sysname.lower()


def build_guide(task: str, model: str, prompt_file: Path, guide_file: Path, execute_cmd: str, original_command: str | None, extracted_mode: str) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "# 待执行 Prompt 使用说明",
        "",
        "> 这是一份由 LongRun 自动整理好的使用说明。主 Prompt 文件已经单独保存，并会自动打开，方便你立刻查看和修改。",
        "",
        "## 文件位置",
        f"- 主文件：`{prompt_file}`",
        f"- 当前说明：`{guide_file}`",
        f"- 生成时间：`{now}`",
        f"- 生成模型：`{model}`",
        f"- 提取方式：`{extracted_mode}`",
        "",
        "## 原始任务",
        f"- {task}",
        "",
        "## 推荐执行方式",
        "```bash",
        execute_cmd,
        "```",
        "",
        "这条命令会读取你刚刚修改后的最新版 Prompt 内容执行，所以你不需要重新生成 Prompt。",
    ]
    if original_command and original_command.strip() and original_command.strip() != execute_cmd.strip():
        lines.extend([
            "",
            "## LongRun 当时生成的原始推荐命令",
            "```bash",
            original_command.strip(),
            "```",
            "",
            "通常更推荐使用上面的“文件版执行命令”，因为它会读取你保存后的最新 Prompt。",
        ])
    lines.extend([
        "",
        "## 建议你先做什么",
        "- 先通读一遍主 Prompt，删除与你目标无关的部分。",
        "- 补充交付物、边界条件、限制项和必须保留的约束。",
        "- 如果你希望任务不要自动结束，可把相关要求补成 checkpoint 或 watch 类语义。",
        "- 保存后，直接复制上面的命令执行即可。",
        "",
        "## 如果执行结果不符合预期",
        "- 先检查目标是否写得足够明确。",
        "- 再检查交付物是否写清楚。",
        "- 如果 Prompt 太大或太杂，建议删掉次要背景，只保留关键约束。",
        "- 需要重新来一版时，可以再次运行 `longrun-prompt`。",
    ])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Package LongRun prompt output into local markdown artifacts")
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--captured-output", required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--auto-open", action="store_true")
    parser.add_argument("--copy-command", action="store_true")
    args = parser.parse_args()

    workspace = Path(args.workspace).resolve()
    captured_path = Path(args.captured_output).resolve()
    raw = captured_path.read_text(encoding="utf-8")
    cleaned = cleaned_output(raw)

    prompt_body = extract_section_fence(cleaned, PROMPT_SECTION_TITLES)
    extracted_mode = "section-fence"
    if not prompt_body:
        prompt_body = fallback_prompt_fence(cleaned)
        extracted_mode = "fallback-fence"
    if not prompt_body:
        prompt_body = cleaned.strip()
        extracted_mode = "full-output"

    original_command = extract_section_fence(cleaned, COMMAND_SECTION_TITLES)

    prompt_file = workspace / "待执行 Prompt.md"
    guide_file = workspace / "待执行 Prompt 使用说明.md"
    backup_if_exists(prompt_file)
    backup_if_exists(guide_file)

    write_text(prompt_file, prompt_body)
    execute_cmd = quoted_cat_command(prompt_file)
    guide_text = build_guide(args.task, args.model, prompt_file, guide_file, execute_cmd, original_command, extracted_mode)
    write_text(guide_file, guide_text)

    opened = auto_open(prompt_file) if args.auto_open else False
    copied = copy_to_clipboard(execute_cmd) if args.copy_command else False

    print(json.dumps({
        "promptFile": str(prompt_file),
        "guideFile": str(guide_file),
        "executeCommand": execute_cmd,
        "originalCommand": original_command or "",
        "opened": opened,
        "copiedToClipboard": copied,
        "extractMode": extracted_mode,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
