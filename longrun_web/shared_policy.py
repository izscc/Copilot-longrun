from __future__ import annotations

import re
from pathlib import Path
from typing import Any

TASK_TYPES = ('adjust_plan', 'append_task', 'clarify')
TASK_STATUSES = ('pending', 'accepted', 'applied', 'scheduled', 'in_progress', 'done', 'blocked', 'rejected', 'superseded')


def infer_language(text: str) -> str:
    return 'zh-CN' if re.search(r'[\u4e00-\u9fff]', text or '') else 'en-US'


def infer_profile(text: str) -> str:
    lowered = (text or '').lower()
    coding = ['代码', 'bug', '测试', '构建', '重构', '脚本', 'ci', 'repo', 'implement', 'refactor', 'debug', 'build']
    research = ['调研', 'research', '分析', 'benchmark', 'market', '趋势', '政策', '法规']
    office = ['文档', '报告', '总结', '材料', '表格', 'ppt', 'slides', 'doc', 'sheet']
    if any(token in lowered for token in coding):
        return 'coding'
    if any(token in lowered for token in research):
        return 'research'
    if any(token in lowered for token in office):
        return 'office'
    return 'office'


def infer_complexity(text: str) -> str:
    lowered = (text or '').lower()
    fleet = ['并行', 'parallel', 'fleet', 'phase', '多阶段', '多工作流', '长期', 'resume']
    parallel = ['多步', '研究', '分析', 'report', '验证', '多个']
    if sum(token in lowered for token in fleet) >= 2:
        return 'fleet'
    if any(token in lowered for token in parallel):
        return 'parallel'
    return 'single-lane'


def evidence_mode(profile: str) -> str:
    return 'balanced' if profile in {'research', 'office'} else 'local-first'


def default_visible_names(profile: str) -> list[str]:
    if profile == 'coding':
        return ['变更摘要.md', '验证记录.md']
    if profile == 'research':
        return ['任务总览.md', '来源附录.md', '最终总结.md']
    return ['任务总览.md', '最终总结.md']


def extract_file_like_deliverables(text: str) -> list[str]:
    pattern = re.compile(r'([A-Za-z0-9_./\-]+\.(?:md|txt|json|csv|py|sh|ts|tsx|js|jsx))')
    found: list[str] = []
    for item in pattern.findall(text or ''):
        normalized = item.strip().strip('`')
        if normalized not in found:
            found.append(normalized)
    return found


def derive_deliverables(text: str, profile: str) -> list[str]:
    explicit = extract_file_like_deliverables(text)
    if explicit:
        return explicit
    defaults = default_visible_names(profile)
    return [f'artifacts/{name}' for name in defaults]


def extract_constraints(text: str) -> list[str]:
    constraints: list[str] = []
    for raw in (text or '').splitlines():
        line = raw.strip('-* ').strip()
        lowered = line.lower()
        if not line:
            continue
        if any(token in lowered for token in ['必须', '不要', '仅', '只能', '默认', '禁止', 'must', 'should', 'only', 'do not', 'dont', "don't"]):
            constraints.append(line)
    return constraints[:8]


def summarize_goal(text: str) -> str:
    clean = ' '.join((text or '').split())
    if not clean:
        return '完成用户交代的 LongRun 任务'
    for token in ['。', '.', '\n']:
        if token in clean:
            head = clean.split(token, 1)[0].strip()
            if head:
                return head
    return clean[:120]


def merge_list(base: list[str], extra: list[str]) -> list[str]:
    seen: list[str] = []
    for item in [*(base or []), *(extra or [])]:
        if item and item not in seen:
            seen.append(item)
    return seen


def local_mission_draft(raw_text: str, previous: dict[str, Any] | None = None, *, interaction: str = 'initial_compile') -> dict[str, Any]:
    previous = previous or {}
    profile = previous.get('profile') or infer_profile(raw_text)
    complexity = previous.get('complexity') or infer_complexity(raw_text)
    language = previous.get('language') or infer_language(raw_text)
    deliverables = merge_list(previous.get('deliverables', []), derive_deliverables(raw_text, profile))
    constraints = merge_list(previous.get('constraints', []), extract_constraints(raw_text))
    goal = previous.get('goal') or summarize_goal(raw_text)
    missing_info: list[str] = []
    if profile == 'coding' and not any(item.endswith(('.py', '.ts', '.tsx', '.js', '.jsx', '.md')) for item in deliverables):
        missing_info.append('建议明确代码或验证交付物路径')
    return {
        'goal': goal,
        'profile': profile,
        'complexity': complexity,
        'language': language,
        'deliverables': deliverables,
        'constraints': constraints,
        'evidenceMode': previous.get('evidenceMode') or evidence_mode(profile),
        'recommendedLaunchMode': 'detached',
        'summary': goal,
        'rawTask': raw_text,
        'missingInfo': merge_list(previous.get('missingInfo', []), missing_info),
        'risks': previous.get('risks', []),
        'interaction': interaction,
    }


def local_operator_request(raw_text: str, draft: dict[str, Any] | None = None) -> dict[str, Any]:
    draft = draft or local_mission_draft(raw_text, interaction='append_task')
    lowered = raw_text.lower()
    task_type = 'append_task'
    if any(token in lowered for token in ['调整计划', '改计划', 'replan', 'adjust plan']):
        task_type = 'adjust_plan'
    elif any(token in lowered for token in ['说明一下', 'clarify', '澄清', '解释']):
        task_type = 'clarify'
    deliverables = draft.get('deliverables') or []
    linked_workstream = 'deliverables' if deliverables else None
    title_source = summarize_goal(raw_text)
    title = title_source[:48]
    return {
        'type': task_type,
        'priority': 'high' if any(token in lowered for token in ['紧急', 'urgent', '尽快']) else 'normal',
        'title': title,
        'rawText': raw_text.strip(),
        'normalizedText': raw_text.strip(),
        'linkedDeliverables': deliverables[:4],
        'linkedArtifacts': [item for item in deliverables if item.startswith('artifacts/')][:4],
        'linkedWorkstream': linked_workstream,
    }


def render_compiled_prompt(draft: dict[str, Any]) -> str:
    deliverables = '\n'.join(f'- {item}' for item in draft.get('deliverables') or []) or '- 无'
    constraints = '\n'.join(f'- {item}' for item in draft.get('constraints') or []) or '- 采用 LongRun 默认安全约束'
    return (
        '请按 LongRun 长跑模式执行以下任务。\n\n'
        f'## Goal\n- {draft.get("goal") or "完成任务"}\n\n'
        f'## Profile\n- {draft.get("profile")}\n- {draft.get("complexity")}\n- language: {draft.get("language")}\n- evidence mode: {draft.get("evidenceMode")}\n\n'
        f'## Deliverables\n{deliverables}\n\n'
        f'## Constraints\n{constraints}\n\n'
        '## Operating Rules\n'
        '- 先任务画像，再规划，再执行。\n'
        '- 默认 helper-first、shell-safe。\n'
        '- 每个关键阶段都要记账到 status/journal。\n'
        '- finalize 前先 reconcile、verify。\n'
        '- 若已完成 deliverable，优先收敛而不是继续高成本折腾。\n'
    )
