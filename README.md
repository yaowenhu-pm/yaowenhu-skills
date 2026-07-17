# infiDive-skills

infiDive 公司 AI 协作工具库。团队成员的 Codex 和 Claude 共享同一套协作工具,新人开箱即用,逐步累加 —— 每解决一个协作痛点就沉淀成一个 skill,而不是每人重复搭建。

## 设计原则

- **共享**:工具代码 + 用法文档(本仓库,可 git)
- **隔离**:每人用自己的凭证(本地 `.env` / `token.json`,`.gitignore` 排除,绝不进 git)
- **谁改可追溯**:各人各自飞书身份,权限在飞书侧统一管
- 完整方案 / 治理见内部协作工具规划文档

## 安装（新成员,一次性）

```bash
git clone https://git.infidive.com/infidive-ai/skills.git ~/infiDive-skills
cd ~/infiDive-skills
bash install.sh          # 同时软链所有 skill 到 Codex / Claude
```

> 2026-07-17 起本仓库以自建 Gitea（git.infidive.com）为唯一主仓,GitHub 上的旧仓不再更新。已按旧地址克隆过的成员执行一次:
> `git remote set-url origin https://git.infidive.com/infidive-ai/skills.git && git pull --rebase`

然后给需要授权的 skill 跑一次首次授权(见各 skill 的 `SKILL.md`)。之后在 Codex 或 Claude 中自然语言触发即可,例如「把这个飞书文档的标题改成 X」。

## 现有 skill

| skill | 作用 | 首次授权 |
|---|---|---|
| `feishu` | 读写飞书文档 / 推送 markdown 到知识库 / 监控 AI 服务状态 | 需(自己的飞书账号,`python3 setup.py`) |
| `feishu-console` | 飞书开发者后台加权限/事件订阅/发版本(浏览器自动化) | 不需(用本人已登录飞书的浏览器) |
| `elegant-docs` | 文档撰写/润色/评估,严格篇幅约束 | 不需 |
| `wechat-article-extractor` | 解析微信公众号文章链接,提取标题/作者/正文/发布时间等结构化数据 | 不需(需先 `npm install`) |
| `hr-autopilot` | 请假审批→考勤→工资单全自动(对话式请假+审批中心双通道),`./install.sh` 一键部署 | 不需(App 身份运行,表格需授权「小潜」可编辑) |
| `creator-stats` | 抖音/小红书创作者大盘数据批量录入 CSV(提供主页链接,驱动本机登录态 Chrome 采集,断点续跑) | 不需(需本人 Chrome 已登录抖音/小红书 + Claude in Chrome 扩展) |

## 更新

```bash
cd ~/infiDive-skills && git pull
```

软链自动指向新版,本地凭证不受影响。

## 加新 skill(维护者 = A4)

1. 建 `<name>/SKILL.md`,frontmatter 必填 `name` + `description`(description 决定 Codex / Claude 何时加载,要写清触发场景)
2. 配套脚本放 `<name>/scripts/`;若需凭证,写 `setup.py` 引导个人授权
3. 凭证文件名加进 `.gitignore`
4. `git push` + 通知成员 `git pull`

## 红线

- 任何**个人凭证**(user token / 密码)绝不进本仓库,只在成员本地(`.gitignore` 已排除)
- 唯一例外:公司共享 App 凭证(App ID/Secret)为让新人零配置授权而内置于 `feishu/setup.py`——因此**本仓库必须保持 private**,泄露时第一时间在飞书开发者后台重置 App Secret
- 本仓库只放**通用工具代码 + 文档**,不放商业敏感内容(与 infiDive 保密目录分离)
