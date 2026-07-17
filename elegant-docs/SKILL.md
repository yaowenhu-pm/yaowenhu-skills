---
name: elegant-docs
description: >
  Document writing, polishing, and evaluation skill. MUST invoke (never answer directly) when ANY of these match:
  (A) Write task — user asks to write a doc, PRD, README, proposal, spec, report, or guide from scratch;
  (B) Evaluate task — user shares a document link (Feishu/Notion/GitHub etc.) + evaluation word like 看看/评估/怎么样/有问题吗;
  (C) Polish task — message contains a long text block (>5 sentences of methodology/blog/summary/plan/design/report)
      AND anywhere in the message appears a rewrite word: 优化/润色/改/整理/精简/重写/改一改 —
      regardless of word position (before, after, or inside the text) or additional constraints (不要提到XX/保留结构/去掉XX).
  NOT for: pure conversation, short messages (<5 sentences) with no rewrite word, translation, code review.
---
# elegant-docs · 优雅文档写作

## 核心原则

> 默认短，必要时长；结论前置，结构可扫；每个模块只承担一个任务。

## 工作流：选择模式

| 触发条件 | 使用模式 |
| --- | --- |
| 用户发来文本/方案/规范/文档链接（飞书、Notion、GitHub 等），后跟"评估"、"看看"、"怎么样"、"有问题吗"等评价词 | 模式 B |
| 用户要求写文档、方案、说明、规范、指南、README、PRD 等 | 模式 A |
| 用户粘贴文本（文章/博客/方法论/总结等），要求"润色"、"改一改"、"优化"、"整理"、"精简"、"重写" | 模式 C |

---

**模式 A：从零写作**

默认直接生成。仅当以下信息缺失且会影响结构时才提问：读者是谁、文档的核心目的。

按下方「文档类型默认结构」起草。固定输出顺序：

1. **正文**：按对应类型结构展开
2. **自检说明**（1–2 行）：标注删掉了什么冗余、合并了哪些章节

---

**模式 B：评估文档**

固定输出：

1. **总评**：一句话结论（是否需要修改，程度如何）
2. **问题清单**：列出具体问题，每条注明位置和影响
3. **建议**：改或不改，优先级排序

不输出重写版本，除非用户追问。

---

**模式 C：润色草稿**

固定输出顺序：

1. **诊断**：字数 / 章节数 / 主要问题（2–3 条）
2. **重写版**
3. **改动说明**：删了什么、为什么（1–3 行）

## 字数策略

| 场景 | 目标字数 | 约束 |
| --- | --- | --- |
| 内容简单 / 信息密度低 / 用户要求简洁 | ≤ 400 字，≤ 3 章节 | 只保留可执行信息 |
| 默认 | 600–900 字 | — |
| 高信息密度说明 / 技术设计中等复杂 | 900–1500 字 | 必须有目录 |
| 天然复杂（PRD / 技术方案） | 允许更长 | 必须：分层 + 目录 + 每节可独立阅读 |

有疑问时选更短的那档。

## 格式选择

- **表格**：比较、参数列表、决策矩阵
- **列表**：步骤、枚举
- **段落**：有逻辑关系、需要上下文的解释性内容
- **目录**：全文超过 900 字时必须添加

## 信息优先级

每个段落的信息按此顺序排列，优先级递减：

1. **结论**：影响决策的核心信息
2. **示例**：帮助理解的具体案例
3. **解释**：必要的背景和原因

## 禁忌

- 套话开头："本文将介绍……"、"随着 XX 的快速发展……"
- 重复表意：同一件事只说一次
- 填充词："显而易见"、"众所周知"、"值得注意的是"
- 结尾复述：读者刚读完，不需要再总结一遍
- 修辞铺陈：不写

## 文档类型默认结构

| 类型 | 默认结构 |
| --- | --- |
| README | 是什么 → 快速开始 → 核心用法 → 参考 |
| PRD / 产品方案 | 背景与目标 → 用户与场景 → 功能范围 → 成功指标 |
| 技术方案 | 问题陈述 → 方案设计 → 取舍说明 → 实施计划 |
| 教程 / 操作手册 | 前置条件 → 步骤 → 常见问题 |
| 规范 / 指南 | 原则 → 规则 → 示例 → 反例 |
| 提案 / 汇报 | 结论先行 → 论据 → 行动项 |
| API 文档 | 概述 → 接口列表 → 参数说明 → 示例 → 错误码 |
| 数据分析报告 | 结论 → 指标 → 分析 → 洞察 → 建议 |
| 设计评审 | 目标 → 方案 → 风险 → 决策建议 |
