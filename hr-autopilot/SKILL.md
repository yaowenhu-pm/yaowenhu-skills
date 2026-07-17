---
name: hr-autopilot
description: 考勤请假自动化：对话式请假（私聊小潜一句话）+ 审批中心双通道，审批通过自动写考勤表。当用户要求安装/部署 hr-autopilot、打通请假审批和考勤、同步请假到考勤表、配置对话式请假、修改考勤规则（大小周/年假额度）、或排查"请假没同步/审批卡片没反应/小潜不回复请假"时使用。不含薪资计算（该模块已按数据安全要求下线）。
---

# hr-autopilot · 请假审批 → 考勤 全自动

员工请假（私聊小潜一句话，或走审批中心）→ 审批通过自动写考勤表 + 请假记录表留痕，双向通知。

> ⚠️ **薪资模块已于 2026-07-06 按数据安全要求整体下线**：App 凭证为全公司共享，凡 App 可读的表都不得存放真实薪资。薪资管理表及员工表薪资列已从多维表格移除，`calc_payroll.py` 已删除。考勤数据可导出供 HR 在小潜无权限的私有表格中另行算薪。**绝不在本 Base 的任何字段填真实薪资数字。**

## 一键安装

```bash
cd ~/infidive-claude-skills/hr-autopilot && ./install.sh
```

装完的手工项只有两个：
1. 多维表格右上角 `···` → 更多 → 添加文档应用 → 「小潜」→ **可编辑**（换新表格时必做，否则写入报 91403）
2. 员工管理表：绑定「飞书账号」列（审批↔员工关联的唯一依据）

## 命令速查

| 场景 | 命令 |
|---|---|
| 补表结构（幂等） | `python3 scripts/ensure_schema.py` |
| 手动同步审批中心请假 | `python3 scripts/sync_leave.py` |
| 独立常驻对话请假监听 | `python3 scripts/leave_bot.py` |
| 卸载定时任务 | `crontab -l \| grep -v hr-autopilot \| crontab -` |

## 架构（多入口，同一账本，单长连接）

- **对话入口**：私聊小潜"我明天请一天事假" → haiku 解析 → 审批卡片按员工表「上级」列路由（未填则发给 config `approval.default_approver`，现为毅哥）→ 点【同意】秒级写考勤 + 请假记录表留痕，双向通知。
- **单连接原则**：同一 App 只能有一条事件长连接。现由 wiki-mirror 的 `feishu_events.py` 独占（含 card.action.trigger 卡片回调），消息经 events.jsonl 由 `link_reply_bot.py` 消费并调用本 skill 的 `leave_flow.py`。**绝不另起监听进程**（事件会随机分流丢消息）；无该基建的环境才用 `leave_bot.py`。
- **审批中心入口**：cron 每小时轮询审批实例（按审批名含"请假"匹配，无需审批码），幂等去重（state/processed.json）。官方假勤审批不支持 API 代提单。
- **卡片回调**：飞书要求 3 秒内响应——实现是"秒回 toast + 后台线程处理"，新增卡片交互也必须遵守。

## 考勤规则

`config.json` 的 `rules`：**大小周**（`big_small_week.working_saturday_anchor` 填任一班六日期，两周一循环；班六计入应出勤和请假天数）、年假默认额度 5 天（累计到「年假已用」，年假剩余为表内公式）。

## 排查

- **请假没同步**：员工「飞书账号」列没绑 / 审批名不含关键词（config `name_keywords`）/ 看 `logs/sync.log`
- **写表报 91403**：表格没给「小潜」文档应用可编辑权限
- **审批卡片点了没反应/报错**：确认 feishu_events 监听进程在跑（`ensure_daemons.sh` 每 10 分钟拉起）；后台"回调订阅"需有 card.action.trigger 且=长连接
- **小潜回"解析服务不可用"**：claude CLI 登录态问题，长期 token 在 `~/.claude-oauth-token.env` 自动注入，检查该文件存在
- **通知没收到**：notify 用 `open_ids`，别用 email（跨租户 email 报 230001）
- **卡片里表格乱**：飞书卡片 markdown 不渲染管道表格，通知一律逐行文本
- **请假跨月**：全部天数计入开始日期所在月（简化约定）
- **手动改表会被感知吗**：会。脚本无缓存、每次运行实时读表
- **常驻失效场景**：宿主机睡眠/关机（对话请假离线且事件不补发，无回执=没处理到，重发即可；审批中心通道不受影响）

## 关键权限（已在 App「小潜」开通，全公司共享）

`approval:approval:readonly`、`approval:approval.list:readonly`、`approval:instance` + bitable 全套。审批 API 只认 tenant token。**共享凭证意味着 App 可读的数据=全员可读，敏感数据（薪资等）严禁进入 App 授权范围内的任何表格。**
