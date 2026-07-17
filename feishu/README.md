# feishu · 飞书全功能操作 Skill

以**操作者本人的飞书身份**操作飞书全系 API —— 文档、知识库、消息、日历、用户组织。

> 依赖：Python 3 + `requests`；事件监听额外依赖 `lark-oapi`

---

## 快速开始

### 1. 安装

通过根目录 `install.sh` 软链整个 skills 仓库：

```bash
git clone https://github.com/infidive-ai/skills.git ~/infiDive-skills
cd ~/infiDive-skills
bash install.sh
```

### 2. 首次授权（每人在自己机器跑一次）

```bash
cd ~/infiDive-skills/feishu
python3 setup.py
```

引导步骤：
1. App ID / Secret 已内置，setup.py 自动写入本机，无需手动输入
2. 浏览器打开授权链接，用自己飞书账号点「授权」
3. 把跳转后的完整 URL 粘贴回终端

授权成功后本机凭证自动保存（权限 600，不进 git）。**只需一次**，token 自动续期。

授权完成后，在 Codex 或 Claude 中发送「帮我测试飞书 skill 的所有功能是否正常」，AI 助手会自动逐项检测并报告结果。

### 3. 后续更新

```bash
cd ~/infiDive-skills && git pull
```

skill 有新版本时也会在每次使用时自动提示。

---

## 使用方式

在 Codex 或 Claude 中自然语言触发，例如：
- 「把这个飞书文档的第二段改成 XXX」
- 「发消息给张三说今天下午会议取消」
- 「列出我明天的日历事件」
- 「把这份 markdown 推送到知识库节点 XXX 下面」

AI 助手会自动调用本 skill 中的脚本完成操作。

---

## 脚本说明

### `scripts/feishu.py` · 全功能主脚本

```bash
python3 scripts/feishu.py <命令> [参数...]
```

#### 消息

| 命令 | 说明 |
|------|------|
| `send-text <id> <id类型> <文本>` | 发文本消息（id类型：`open_id` / `chat_id` / `email`） |
| `send-card <chat_id> <card_json或文件>` | 发卡片消息到群 |
| `send-card-bot <chat_id> <card_json或文件>` | 用 App 身份发卡片，免用户 OAuth，适合 cron 无人值守 |
| `send-md <id> <id类型> <md文本或文件> [标题]` | 发**渲染后的 Markdown 卡片**（用户身份）；加粗/列表/链接/分隔线都会渲染 |
| `send-md-bot <id> <id类型> <md文本或文件> [标题]` | 发渲染后的 Markdown 卡片（App身份，可直接发 open_id，适合无人值守推送） |
| `update-md-bot <message_id> <md文本或文件> [标题]` | 更新 bot 已发的 Markdown 卡片（PATCH，流式输出/进度刷新用；message_id 从 send-md-bot 返回取，更新有频控建议≥1秒节流） |
> **流式卡片（真打字机动画）**：`feishu.stream_card_start / stream_card_update / stream_card_finish`（Python 函数，CardKit 卡片实体）——客户端逐字平滑渲染，适合 AI 生成类回复；`update-md-bot` 是整卡替换（视觉跳变），只适合低频进度刷新。sequence 严格递增，更新 ≥0.5s 节流。

| `reply <message_id> <文本>` | 回复某条消息 |
| `msg-list <chat_id> [limit]` | 拉取群消息列表（oldest-first） |
| `last-reply <chat_id> [open_id或-] [limit]` | 读最新一条回复（newest-first，默认跳过 bot 自己）——用于感知对方是否回复 |
| `msg-get <message_id>` | 获取指定消息 JSON |
| `msg-search <关键词> [limit]` | 搜索可见群近期消息 |
| `msg-resource <message_id> <file_key> <保存路径> [type]` | 下载消息中的图片/音视频/文件资源 |
| `send-image <id> <id类型> <图片路径>` | 上传并发送图片 |
| `send-file <id> <id类型> <文件路径> [file_type]` | 上传并发送文件 |

#### 群/会话

| 命令 | 说明 |
|------|------|
| `chat-list` | 列出我加入的群 |
| `chat-info <chat_id>` | 群详情 |
| `chat-members <chat_id>` | 群成员列表 |
| `chat-create <名称> [open_id,...]` | 建群 |
| `chat-search <关键词> [limit]` | 搜索可见群 |

#### 用户/组织

| 命令 | 说明 |
|------|------|
| `me` | 我的用户信息 |
| `user-info <open_id>` | 查某用户 |
| `dept-list [dept_id]` | 列部门（默认根部门） |
| `dept-members <dept_id>` | 部门成员 |

#### 日历

| 命令 | 说明 |
|------|------|
| `cal-list` | 我的日历列表 |
| `cal-events <calendar_id> [days]` | 未来 N 天事件 |
| `cal-create <calendar_id> <标题> <开始> <结束>` | 创建事件（格式：`2026-06-27T10:00:00+08:00`） |

#### 知识库

| 命令 | 说明 |
|------|------|
| `wiki-spaces` | 列所有知识库 |
| `wiki-nodes <space_id> [parent_token]` | 列子节点 |
| `wiki-tree <space_id> [depth]` | 打印目录树 |
| `wiki-classify <md文件> <space_id> [depth]` | 打印目录树 + 文档摘要，供智能分类决策 |

#### 多维表格 Base/Bitable

| 命令 | 说明 |
|------|------|
| `base-create-app <名称> [folder_token]` | 新建多维表格 App |
| `base-create-table <base> <表名> <fields_json或文件> [视图名]` | 新建数据表 |
| `base-tables <base_url_or_app_token>` | 列数据表 |
| `base-fields <base> <table_id>` | 列字段 |
| `base-records <base> <table_id> [limit]` | 列记录 |
| `base-search <base> <table_id> <body_json或文件> [limit]` | 查询记录 |
| `base-create <base> <table_id> <fields_json或文件>` | 新增记录 |
| `base-update <base> <table_id> <record_id> <fields_json或文件>` | 更新记录 |
| `base-delete <base> <table_id> <record_id>` | 删除记录 |

**写入约定（默认遵守）**：文本字段里的内容**一律用换行符 `\n` 分隔要素**，不要把多个要点挤成一行——多维表格行高不可通过 API 设置（`PATCH view` 静默忽略 `row_height`），换行是唯一保证单元格可读的方式。单句短文本不必强加换行。

#### 云空间文件

| 命令 | 说明 |
|------|------|
| `drive-root` | 获取云空间根目录 token |
| `drive-upload <folder_token> <文件路径> [文件名]` | 上传文件到云空间 |
| `drive-download <file_token> <保存路径>` | 下载云空间文件 |
| `media-download <file_token> <保存路径>` | 下载云文档素材 |

#### 云文档

| 命令 | 说明 |
|------|------|
| `list` | 列云空间文档 |
| `read <URL>` | 读文档纯文本 |
| `blocks <URL>` | 列块（改前必先看） |
| `update <URL> <block_id> <文本>` | 改块文字 |
| `delete <URL> <block_id>` | 删顶层块 |
| `insert-after <URL> <block_id> <文本> [type]` | 在某块后插入 |
| `append <URL> <文本>` | 追加到文档末尾；Markdown表格会转原生表格并自动估算列宽；#标题转真实标题格式；不写空行/横线 |
| `create <标题> [正文]` | 新建文档；正文同append |
| `insert-image <URL> <图片路径> [align] [width]` | 插入本地图片（align: 1=左 2=居中 3=右） |
| `update-image <URL> <block_id> [align] [width] [height]` | 调整图片块对齐/尺寸 |
| `push-wiki <md> <节点URL或node_token> [标题]` | md推到节点下（支持裸token）；导入后自动估算表格列宽并清理空行/横线 |
| `push-wiki-top <md> <节点URL或node_token> [标题]` | md推到知识库顶层；导入后自动估算表格列宽并清理空行/横线 |
| `fix-mentions <URL>` | 把文档内 @姓名 纯文本替换为真正的飞书提及 |
| `test` | 自动检测所有功能是否正常，逐项输出 ✅ / ❌ |

#### 智能推送工作流

推送文档到知识库时，不要直接 `push-wiki`，应按以下步骤执行：

1. `wiki-spaces` — 确认目标知识库 `space_id`
2. `wiki-classify <md文件> <space_id> 3` — 同时输出 3 层目录树 + 文档摘要
3. **命名前缀 + 去重检查** — 标题必须带类型前缀（`会议纪要` / `决策` / `规范` / `产品` / `技术` / `其他` 六选一）；对照目录树确认没有同主题文档在重复造，发现疑似重复先跟用户确认覆盖/追加/新建，不要默认建新的
4. 根据语义匹配选择合适的父节点 `node_token`
5. `push-wiki <md文件> <node_token> [标题]` — 推送到选定节点

命名与去重规范同样适用于 `create` / `append`：新建云文档前先用 `list` 或 `chat-search` 查一下有没有同名/同主题文档。

**多用户说明**：团队成员各自完成一次 `setup.py` 授权后，均可独立执行以上工作流。`wiki-classify` 每次实时拉取最新目录结构，多人同时推送互不干扰，各自以自己的飞书身份操作。

---

### `scripts/status_monitor.py` · AI 服务状态监控

分别轮询 Claude / Codex(OpenAI) 官方 Statuspage API，两个服务独立判断变化、独立推送（不合并成一条消息）。卡片极简，两行：标题 `{服务} System Status`，正文是当前活跃事件名（无活跃事件退回显示整体状态描述），不加图标、不加链接；无变化不推送。

```bash
python3 scripts/status_monitor.py check <chat_id> [--services claude,codex] [--force] [--dry-run]
```

- 数据源：`status.claude.com` / `status.openai.com` 的 `/api/v2/summary.json`（官方源，无需 key）
- 状态记录在 `.status_state.json`，和上次对比，只在**出问题**（有活跃事件）且与上次记录不同时才发卡；服务健康、或从异常恢复到健康时都不发，保持安静
- 默认用 App(bot) 身份发卡，不占用个人账号，适合 cron 无人值守；前提是先把 App 加为目标群成员，否则报 `230002`。加 `--as-user` 换成本人身份发（跟其他命令一致，靠 refresh_token 自动续期，无需拉 App 进群）
- `--dry-run` 只打印卡片 JSON，不真发送、不写状态文件，改动后先用它预览
- 加监控对象：在脚本的 `SERVICES` 字典里加一条 `summary_url`（Statuspage 站点都是 `<domain>/api/v2/summary.json`）

---

### `scripts/feishu_events.py` · 事件订阅 / WebSocket

使用飞书官方 Python SDK 的长连接模式接收事件。默认监听 `im.message.receive_v1`，收到事件后按 JSONL 输出；传入日志文件路径时会同步追加写入。

```bash
python3 scripts/feishu_events.py listen [events_csv] [log_jsonl]
python3 scripts/feishu_events.py listen im.message.receive_v1 events.jsonl
```

前提：飞书开发者后台已把事件订阅方式配置为「长连接」，并订阅对应事件。若缺少依赖，先安装：

```bash
python3 -m pip install lark-oapi
```

---

## 权限说明

新增能力需要在飞书开发者后台为 `infidive-全功能助手` 开启对应权限，开启并发布新版本后重新 OAuth 授权：

| 能力 | 常用权限 |
|------|----------|
| 消息/群 | `im:chat`、`im:message`、`im:message:readonly` |
| 消息媒体 | `im:resource`（覆盖上传图片/文件；`im:resource:upload` 在控制台不存在，勿用） |
| 事件订阅 | 配置长连接，并订阅 `im.message.receive_v1` 等事件 |
| 多维表格 | `bitable:app`、`bitable:app:readonly`、`bitable:app:write`、`base:record:retrieve` |
| 云空间文件 | `drive:file`、`drive:file:upload`、`drive:drive` |

---

## 文件结构

```
feishu/
├── SKILL.md              # Skill 描述（触发条件）
├── README.md             # 本文件
├── setup.py              # 首次授权引导脚本
└── scripts/
    ├── feishu.py          # 全功能主脚本
    ├── feishu_events.py   # 飞书长连接事件监听
    └── status_monitor.py  # AI 服务状态监控（Claude/Codex → 飞书卡片）
```

> **凭证红线**：`.infidive-docs.env` / `.infidive-docs-token.json` 只存在于成员本机（权限 600），已加入 `.gitignore`，**绝不进 git、不贴聊天、不写进任何文档**。
