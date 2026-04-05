# Orchestration Complexity Guide

用它决定 `/longrun` 是否应该串行推进、有限并行，还是进入多阶段舰队模式。

## 画像优先级

先定 `profile`，再定 `complexity`。

### coding
- 改代码、补测试、修 CI、脚本化、构建/部署前的本地准备
- 默认优先本地验证，不强制研究型证据链

### research
- 市场/政策/行业/技术调研、趋势分析、结构化报告
- 必须有 artifact + sources

### office
- Markdown/CSV/文档/汇报材料/摘要/本地资料整理
- 若依赖公开网页，也必须保留来源
- 若依赖 Google Docs / Notion / 私有后台 等登录态系统，但当前宿主未提供访问能力，应直接 BLOCKED

## complexity 分类

### single-lane
- 单一主任务链路
- 基本不需要并行 workstreams
- 示例：修一个 bug、写一个脚本、补一个 focused 文档

### parallel
- 2-4 个相对独立的 workstreams
- 示例：研究四个主题、实现 + 测试 + 文档、整理数据 + 出报告

### fleet
- 多阶段、跨角色、带恢复预算的任务
- 示例：大规模重构、长时间研究 + 汇总 + 本地验证、复杂办公材料流水线

## 决策信号

提升 complexity：
- 用户明确要求多小时 / 多阶段 / 自主恢复
- 既要调研又要输出正式产物
- 失败恢复和状态可恢复性很重要
- workstreams 间存在可控并行

降低 complexity：
- 一个线性计划就足够
- 并行开销大于收益
- 任务主要集中在单个文件/单个命令

## 输出要求

一旦选定，必须写入：
- `mission.md`
- `status.json`
- `plan.md`

如果中途升级或降级 complexity，必须在 `journal.jsonl` 解释原因。
