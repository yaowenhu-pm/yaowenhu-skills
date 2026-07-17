---
name: feishu
description: 飞书(Feishu/Lark)全功能操作工具。当用户给出飞书链接、要求读取/修改文档、推送知识库、发消息、读取或自动分类个人飞书邮箱、下载或归档发票附件及可信正文链接、查日历、查组织架构、监控 Claude/Codex 等 AI 服务状态并推送飞书时使用。
---

# feishu · 飞书操作工具

以**操作者本人的飞书身份**操作飞书全系 API —— 文档、知识库、消息、日历、用户组织。

> 脚本在 `scripts/`，首次授权运行根目录的 `setup.py`。依赖 Python3 + `requests`；事件监听额外依赖 `lark-oapi`。

## 首次使用 / Token 失效：授权与恢复

报 `缺凭证` / `缺 token` / `refresh 失败`（refresh_token 失效）时走同一恢复流程。**必须两步走，不要在无 TTY 的 shell 里直接跑交互式 `setup.py`（会 EOF 退出），也不要尝试用浏览器自动化打开 feishu.cn 页面**：

```
# 第 1 步：打印授权链接，把链接【原样】发给用户，请用户在浏览器打开并点「授权」
python3 setup.py --url

# 第 2 步：用户授权后页面跳到 https://example.com/?code=XXX...（打不开是正常的），
# 请用户把地址栏完整 URL 粘回来，然后：
python3 setup.py --code '<用户粘贴的完整URL>'
```

完成后重试原命令即可。人在终端时也可以直接交互式运行 `python3 setup.py`。

如果要使用另一个飞书账号，不要把 token 发到聊天里；在本机用该账号重新 OAuth，并用独立 token 文件避免覆盖当前账号：

```
FEISHU_TOKEN_FILE=.feishu-token-other.json python3 setup.py
FEISHU_TOKEN_FILE=.feishu-token-other.json python3 scripts/feishu.py me
```

### 个人邮箱授权

读取个人邮箱必须使用个人自建应用，不要给团队共享应用增加邮箱权限。先在飞书开放平台把应用可用范围限制为本人，配置重定向地址 `https://example.com`，开通并发布以下权限：

- `mail:user_mailbox.message:readonly`
- `mail:user_mailbox.message.subject:read`
- `mail:user_mailbox.message.address:read`
- `mail:user_mailbox.message.body:read`
- `mail:user_mailbox.message:modify`
- `mail:user_mailbox.folder:write`
- `mail:user_mailbox.rule:write`
- `offline_access`

完成后在本机运行：

```
FEISHU_PROFILE=mail python3 setup.py
```

首次配置时在终端输入现有 App ID 和 App Secret；已有 `.feishu-mail.env` 时直接复用，不重置 Secret，也不要把 Secret 粘贴到聊天。token 写入 `.feishu-mail-token.json`，两者权限均为 600 且不会进入 git。邮件相关命令会自动使用这个个人配置，其他命令继续使用原共享配置。

## 主脚本（全功能）

```
python3 scripts/feishu.py <命令>
```

### 个人邮箱与发票归档

| 命令 | 作用 |
|---|---|
| `mail-list [limit]` | 列出最近邮件的日期、发件人、主题和附件 |
| `mail-get <message_id>` | 获取指定邮件详情 |
| `mail-download <message_id> <保存目录>` | 下载邮件中的全部非内联附件 |
| `mail-folders` | 列出个人邮箱文件夹 |
| `mail-rules` | 列出个人邮箱收信规则 |
| `mail-classify-install [--apply]` | 预览或安装“自动分类”文件夹及未来邮件规则 |
| `mail-classify [--limit 100] [--apply]` | 预览或移动收件箱历史邮件；默认只预览 |
| `invoice-collect [--mailbox 邮箱地址] [--limit 100] [--root 目录] [--dry-run]` | 从指定的可访问邮箱收件箱筛选发票邮件，下载附件、去重并生成汇总 CSV；默认处理当前邮箱，目录为桌面“发票” |

`invoice-collect` 匹配邮件主题、正文摘要和附件名中的 `发票/电子票/数电票/行程单/电子客票/报销/invoice/receipt`，只保存 PDF，忽略其他格式和签名内联图片；对 `system@notice.aliyun.com` 只提取正文中的 PDF 下载按钮，并只允许阿里云可信域名。文件按邮件日期放入 `YYYY/MM`，用来源 ID 和 SHA-256 去重，不标记已读、不移动或删除邮件。首次运行先加 `--dry-run` 预览。

自动分类采用保守规则：发票、明确的 AI 订阅、GitHub PR/Issue 等常规开发通知才移入 `自动分类` 子目录；登录、密码、验证码、安全、风险、漏洞、公司邮件和未识别邮件保留在收件箱。`mail-classify-install` 与 `mail-classify` 默认都不写入，必须显式加 `--apply`。

### 消息
| 命令 | 作用 |
|---|---|
| `send-text <id> <id类型> <文本>` | 发文本消息（id类型: open_id/chat_id/email） |
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

### 群/会话
| 命令 | 作用 |
|---|---|
| `chat-list` | 列出我加入的群 |
| `chat-info <chat_id>` | 群详情 |
| `chat-members <chat_id>` | 群成员列表 |
| `chat-create <名称> [open_id,...]` | 建群 |
| `chat-search <关键词> [limit]` | 搜索可见群 |

### 用户/组织
| 命令 | 作用 |
|---|---|
| `me` | 我的用户信息 |
| `user-info <open_id>` | 查某用户 |
| `dept-list [dept_id]` | 列部门（默认根部门） |
| `dept-members <dept_id>` | 部门成员 |

### 日历
| 命令 | 作用 |
|---|---|
| `cal-list` | 我的日历列表 |
| `cal-events <calendar_id> [days]` | 未来N天事件 |
| `cal-create <calendar_id> <标题> <开始> <结束>` | 创建事件（时间格式：2026-06-27T10:00:00+08:00） |

### 知识库
| 命令 | 作用 |
|---|---|
| `wiki-spaces` | 列所有知识库 |
| `wiki-nodes <space_id> [parent_token]` | 列子节点 |
| `wiki-tree <space_id> [depth]` | 打印目录树 |
| `wiki-classify <md文件> <space_id> [depth]` | 打印目录树 + 文档摘要，供分类决策 |
| `wiki-node-info <节点URL或token>` | 查节点详情(space_id/obj_type/obj_token)，copy/move/rename 前先看这个 |
| `wiki-copy <节点URL或token> <目标space_id> [目标parent_token] [标题]` | 整节点复制(含图片富媒体，不丢图)；目标parent_token留空=复制到目标知识库顶层 |
| `wiki-move <节点URL或token> <目标space_id> [目标parent_token]` | 整节点移动(原节点消失)；对目标parent_token指向的节点无编辑权会报`no destination parent node permission` |
| `wiki-rename <节点URL或token> <新标题>` | 改节点标题(不改文档正文内的标题块，正文首行标题要用 `update` 单独改) |

**源文档本身是图片/富媒体为主、或源本身已经是 wiki 节点时，优先用 `wiki-copy`/`wiki-move` 而不是 `push-wiki`**——`push-wiki` 是先转 markdown 再导入，图片等块会丢；`wiki-copy`/`wiki-move` 是节点级搬运，图文完整保留。

**跨节点权限坑**：`wiki-copy`/`wiki-move` 指定 `target_parent_token` 时，需要对**那个具体目标节点**有编辑权，即便对整个知识库/顶层有权限也不够；报 `no destination parent node permission` 时不代表操作失败不可行，是目标节点权限不够。稳妥流程：
1. 先试指定 `target_parent_token` 直接搬到目标分类下；
2. 失败就退而求其次，`target_parent_token` 留空搬到目标知识库顶层（这一步通常必成），保证内容先落地；
3. 跟用户确认：找有该目标节点编辑权的人手动拖拽归位，或者给当前账号开通该节点编辑权；
4. 权限到位后，对已经落地的新节点再跑一次 `wiki-move` 归位到目标分类下。

### 多维表格 Base/Bitable
| 命令 | 作用 |
|---|---|
| `base-create-app <名称> [folder_token]` | 新建多维表格 App |
| `base-create-table <base> <表名> <fields_json或文件> [视图名]` | 新建数据表 |
| `base-tables <base_url_or_app_token>` | 列数据表 |
| `base-fields <base> <table_id>` | 列字段 |
| `base-records <base> <table_id> [limit]` | 列记录 |
| `base-search <base> <table_id> <body_json或文件> [limit]` | 查询记录 |
| `base-create <base> <table_id> <fields_json或文件>` | 新增记录 |
| `base-update <base> <table_id> <record_id> <fields_json或文件>` | 更新记录 |
| `base-delete <base> <table_id> <record_id>` | 删除记录 |

**写入约定（默认遵守）**：文本字段里的内容**一律用换行符 `\n` 分隔要素**，不要把多个要点挤成一行——多维表格行高不可通过 API 设置（`PATCH view` 静默忽略 `row_height`），换行是唯一保证单元格可读的方式。例：`"发生了什么": "定了三件事：\n1. 取消 Figma\n2. 登录改邮箱\n3. 采用 GitHub Mirror"`。单句短文本不必强加换行。

### 云空间文件
| 命令 | 作用 |
|---|---|
| `drive-root` | 获取云空间根目录 token |
| `drive-upload <folder_token> <文件路径> [文件名]` | 上传文件到云空间 |
| `drive-download <file_token> <保存路径>` | 下载云空间文件 |
| `media-download <file_token> <保存路径>` | 下载云文档素材 |

### 云文档
| 命令 | 作用 |
|---|---|
| `list` | 列云空间文档 |
| `read <URL>` | 读文档纯文本 |
| `blocks <URL>` | 列块（改前必先看） |
| `update <URL> <block_id> <文本>` | 改块文字 |
| `delete <URL> <block_id>` | 删顶层块 |
| `insert-after <URL> <block_id> <文本> [type]` | 在某块后插入 |
| `append <URL> <文本>` | 追加到文档末尾；Markdown表格会转原生表格并自动估算列宽；#标题转真实标题格式；不写空行/横线 |
| `create <标题> [正文]` | 新建文档；正文同append |
| `push-wiki <md> <节点URL或node_token> [标题]` | md推到节点下（支持裸token）；导入后自动估算表格列宽并清理空行/横线 |
| `push-wiki-top <md> <节点URL或node_token> [标题]` | md推到知识库顶层；导入后自动估算表格列宽并清理空行/横线 |

## AI 服务状态监控（推飞书群）

```
python3 scripts/status_monitor.py check <chat_id> [--services claude,codex] [--force] [--dry-run]
```

分别轮询 Claude（status.claude.com）和 Codex/OpenAI（status.openai.com）官方 Statuspage API，两个服务**各自独立**判断是否有变化，**各发各的卡片**（不合并成一条）。卡片极简，只有两行：标题是 `{服务} System Status`，正文是当前活跃事件名（没有活跃事件时才退回显示整体状态描述），不加图标、不加链接。只在该服务**出问题**（有活跃事件/指标非正常）且与上次记录不同时才推送到 `<chat_id>`；服务健康、或从异常恢复到健康时都不推送，保持安静。`--force` 忽略记录强制推送当前状态；`--dry-run` 只打印卡片 JSON 不真发、不写状态文件，改动前用它预览。

默认用 **App(bot)身份**发卡，不占用个人账号，适合无人值守。前提：「infidive-全功能助手」这个 App 必须先被加为目标群成员，否则会报 `230002 Bot/User can NOT be out of the chat`。加 `--as-user` 可以退回用你本人身份发（跟 `feishu.py` 其他命令一致，无需拉 App 进群）。要长期监控，给用户装一个定时任务，例如：

```
*/5 * * * * cd ~/infiDive-skills/feishu && python3 scripts/status_monitor.py check <chat_id> >> /tmp/status_monitor.log 2>&1
```

`chat_id` 用 `python3 scripts/feishu.py chat-list` 查。要监控别的服务（如 GitHub、Cursor），在 `status_monitor.py` 的 `SERVICES` 字典里加一条 `summary_url`（Statuspage 站点都是 `<domain>/api/v2/summary.json`）即可。

## 事件订阅 / WebSocket

```
python3 scripts/feishu_events.py listen [events_csv] [log_jsonl]
```

默认监听 `im.message.receive_v1`，收到事件后按 JSONL 输出到终端；传入 `log_jsonl` 时同时追加写入文件。示例：

```
python3 scripts/feishu_events.py listen im.message.receive_v1 events.jsonl
```

前提：飞书开发者后台已把事件订阅方式配置为「长连接」，并订阅对应事件。

## 文档命名与去重规范（新建/推送文档时必须遵守）

团队共用这个 skill，规则在这里生效一次，全员建的文档就都统一——不要跳过。适用于 `create`、`append`、`push-wiki`、`push-wiki-top` 四个建文档/推文档的命令。

**命名前缀**：标题必须是 `[类型]标题正文` 格式，类型固定在以下几种里选，不额外发明新类型：
- `会议纪要`、`决策`、`规范`、`产品`、`设计`、`技术`、`其他`

UI/交互/视觉稿等设计类内容用 `设计`，不要退而用 `产品` 顶替——两者在知识库里是并列的独立分类（如有「设计」目录节点，设计类文档应归到该目录下）。

用户没给标题、或标题没带前缀时，先判断内容属于哪类；拿不准就直接问用户，不要自己瞎猜硬套。

**去重检查**：新建或推送前，先确认知识库里没有同主题文档在重复造：
- 推知识库：`wiki-classify` 已经会输出目录树 + 目标文档摘要，扫一眼树里有没有标题相近/主题重合的节点
- 建云文档（`create`）或追加（`append`）：不确定是否已存在时，用 `list` 或 `chat-search` 之类命令先查一下同名/同主题文档

发现疑似重复后，**不要默认建新的**，向用户确认三选一：覆盖旧文档 / 在旧文档基础上追加 / 确认是新主题、允许新建。

## 智能推送工作流（必须遵守）

**当用户要求"推送文档到知识库"时，禁止直接推到任意位置，必须按以下步骤执行：**

### 步骤 1：获取知识库列表
```
python3 scripts/feishu.py wiki-spaces
```
确认目标知识库的 `space_id`。若用户未指定，询问推到哪个知识库。

### 步骤 2：读取目录结构 + 文档内容
```
python3 scripts/feishu.py wiki-classify <md文件路径> <space_id> 3
```
该命令同时输出：
- 知识库 3 层目录树（含 node_token）
- 文档前 800 字摘要

### 步骤 3：命名前缀 + 去重检查
按上方《文档命名与去重规范》检查/补全标题前缀；对照步骤 2 的目录树判断是否已有同主题文档，如有疑似重复先跟用户确认覆盖/追加/新建。

### 步骤 4：根据内容选择合适的父节点
根据目录树的分类和文档内容，判断文档归属哪个类目，选取最合适的 `node_token`。选择依据：
- 文档主题与目录节点标题的语义匹配
- 优先放在叶子节点（最细粒度的分类）下
- 若无明确匹配，说明原因并询问用户确认

### 步骤 5：推送到选定节点
```
python3 scripts/feishu.py push-wiki <md文件路径> <node_token> [标题]
```
`push-wiki` 支持直接传入裸 `node_token`，无需拼成完整 URL。

**若源文档是图片/富媒体为主、或源本身已经是一个 wiki 节点（而不是本地 md 文件）**，改用节点级搬运，见上方《知识库》命令表的 `wiki-copy`/`wiki-move` 及其权限坑处理流程，不要用 `push-wiki`（会丢图）。

### 步骤 6：确认结果
将推送结果（节点路径、文档标题）回报给用户。

### 步骤 7：零延迟触发知识库镜像同步
公司知识库有 GitHub 镜像（`infidive-ai/org-ai-pilot` 的 `knowledge-base/`），平时靠事件/轮询感知变更；但 `push-wiki` / `push-wiki-top` 是我们**自己发起的动作**，不必等感知——推送成功后立即跑一次同步器：

```
[ -x /Users/admin/.claude/automation/infidive-wiki-mirror/sync.sh ] && /bin/bash /Users/admin/.claude/automation/infidive-wiki-mirror/sync.sh
```

同步器目前只部署在耀文的机器上；其他成员机器上该文件不存在，`-x` 判断会自动跳过，不报错、不需要处理。

## 权限说明

新增能力需要在飞书开发者后台给 `infidive-全功能助手` App 开启对应权限，开启并发布新版本后重新 OAuth 授权：

| 能力 | 常用权限 |
|---|---|
| 消息/群 | `im:chat`、`im:message`、`im:message:readonly` |
| 消息媒体 | `im:resource`（覆盖上传图片/文件；`im:resource:upload` 在控制台不存在，勿用） |
| 个人邮箱 | `mail:user_mailbox.message:readonly`、`mail:user_mailbox.message.subject:read`、`mail:user_mailbox.message.address:read`、`mail:user_mailbox.message.body:read`、`mail:user_mailbox.message:modify`、`mail:user_mailbox.folder:write`、`mail:user_mailbox.rule:write` |
| 事件订阅 | 配置长连接，并订阅 `im.message.receive_v1` 等事件 |
| 多维表格 | `bitable:app`（含编辑和管理）、`bitable:app:readonly`、`base:record:retrieve` |
| 云空间文件 | `drive:file`、`drive:file:upload`、`drive:drive` |

## 凭证说明

- **App ID / App Secret**：公司共享凭证，已内置于 `setup.py`，首次运行自动写入本机，无需手动输入。
- **User Token**（`.infidive-docs-token.json`）：个人 OAuth token，只在本机（600），**绝不进 git**。
- **个人邮箱凭证**（`.feishu-mail.env` / `.feishu-mail-token.json`）：仅用于本人邮箱，只在本机（600），不要粘贴到聊天或提交到 git。
