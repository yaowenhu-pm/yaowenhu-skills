# yaowenhu-skills

个人 Agent Skills 合集，遵循 [Agent Skills](https://agentskills.io) 开放标准（`SKILL.md` 格式），可被 Claude Code、Codex 等兼容 Agent 自动加载。

A personal collection of Agent Skills following the [Agent Skills](https://agentskills.io) open standard (`SKILL.md` format), auto-loaded by Claude Code, Codex, and other compatible agents.

---

## Skills

| Skill | 说明 | Description |
|-------|------|-------------|
| [`creator-stats`](creator-stats/) | 抖音/小红书创作者主页大盘数据批量录入 CSV。驱动本机已登录的真实 Chrome 逐页访问主页，纯文本解析昵称、粉丝数、获赞数等公开数据，增量落盘、支持断点续跑。不写爬虫、不破解签名、不绕验证码。 | Batch-collect public profile stats (followers, likes, etc.) of Douyin / Xiaohongshu creators into a CSV. Drives your own logged-in Chrome page by page — no scraper, no signature cracking, no CAPTCHA bypassing. Incremental writes with resume support. |
| [`elegant-docs`](elegant-docs/) | 优雅文档写作：让 Agent 写文档、评估文档、润色草稿时默认短、结论前置、结构可扫。纯提示词 Skill，零依赖。 | Elegant document writing: makes the agent default to concise, conclusion-first, scannable structure when writing, evaluating, or polishing documents. Pure-prompt skill, zero dependencies. |

---

## 安装 / Installation

Skill 本质是一个包含 `SKILL.md` 的目录，放进 Agent 的 skills 路径即可，无需安装命令。

A skill is just a directory containing a `SKILL.md`. Drop it into your agent's skills path — no installer needed.

```bash
git clone https://github.com/yaowenhu-pm/yaowenhu-skills.git ~/yaowenhu-skills

# Claude Code
mkdir -p ~/.claude/skills
ln -s ~/yaowenhu-skills/creator-stats ~/.claude/skills/creator-stats
ln -s ~/yaowenhu-skills/elegant-docs  ~/.claude/skills/elegant-docs

# Codex
mkdir -p ~/.codex/skills
ln -s ~/yaowenhu-skills/creator-stats ~/.codex/skills/creator-stats
ln -s ~/yaowenhu-skills/elegant-docs  ~/.codex/skills/elegant-docs
```

软链方式安装后，仓库 `git pull` 即完成升级。也可以直接 `cp -r` 复制目录。

With symlinks, a `git pull` in the repo is all it takes to upgrade. Plain `cp -r` works too.

装完新开会话即生效。Restart your agent session after installing.

### 前置要求 / Prerequisites

- `elegant-docs`：无 / none。
- `creator-stats`：本机 Chrome 需安装 **Claude in Chrome** 扩展，且抖音、小红书为登录态。Requires the **Claude in Chrome** extension and logged-in Douyin / Xiaohongshu sessions in your local Chrome.

---

## 使用 / Usage

安装后用自然语言触发即可（`description` 字段驱动自动匹配）：

Trigger with natural language after installing (auto-matched via each skill's `description`):

- 「帮我把这批抖音/小红书主页的粉丝数整理成表格」 → `creator-stats`
- "Collect follower stats for these creator profile links into a CSV" → `creator-stats`
- 「帮我润色一下这篇文档」「写一份 PRD」 → `elegant-docs`
- "Polish this draft" / "Write a README for this project" → `elegant-docs`

---

## License

MIT
