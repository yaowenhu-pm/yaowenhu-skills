#!/usr/bin/env python3
"""小潜对话式请假：一句话请假 → 上级卡片审批 → 秒级写考勤。

被 twin_bot.py 调用：
  try_handle_leave(text, sender_open_id, chat_id) -> bool   # 消息分支
  handle_card_action(event_dict) -> dict                    # 卡片按钮回调

数据落两处：请假记录表（审计）+ 考勤管理表，
与 sync_leave.py（审批中心轮询通道）共用同一账本。
"""
import datetime
import json
import os
import re
import subprocess
import threading

import fs
from sync_leave import upsert_attendance

CLAUDE = os.path.expanduser("~/.local/bin/claude")
OAUTH_ENV = os.path.expanduser("~/.claude-oauth-token.env")


def _claude_env():
    """CLI 登录态会过期；有长期 OAuth token 文件就注入，免疫过期。"""
    env = dict(os.environ)
    if os.path.exists(OAUTH_ENV):
        for line in open(OAUTH_ENV):
            line = line.strip().removeprefix("export ").strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k] = v.strip().strip('"')
    return env
INTENT_RE = re.compile(r"请假|休假|病假|事假|年假|想休|请[一两半0-9.]+天|请半天")
LEAVE_TABLE = "请假记录"


_tid_cache = {}


def table_id(app, name):
    """table_id 不会变，缓存省一次 API 往返（卡片回调对时延敏感）。"""
    key = (app, name)
    if key not in _tid_cache:
        _tid_cache[key] = fs.table_id_by_name(app, name)
    return _tid_cache[key]


def approver_name(cfg, open_id):
    alias = (cfg.get("approval") or {}).get("approver_alias") or {}
    if open_id in alias:
        return alias[open_id]
    app = fs.app_token_from_url(cfg["base_url"])
    for r in fs.list_records(app, table_id(app, cfg["tables"]["employee"])):
        users = r["fields"].get("飞书账号")
        if isinstance(users, list) and users and users[0].get("id") == open_id:
            return fs.cell_text(r["fields"].get("姓名"))
    return "上级"


def default_approver(cfg):
    """员工表没填「上级」时的兜底审批人，配置在 config.json approval.default_approver。"""
    return cfg.get("approval", {}).get("default_approver") or \
        (cfg.get("notify", {}).get("open_ids") or [""])[0]


def log(*a):
    import time
    print(time.strftime("%H:%M:%S"), "[leave]", *a, flush=True)


def parse_leave(text):
    """LLM 把自然语言请假请求解析成结构化 JSON；非请假意图返回 None。"""
    today = datetime.date.today()
    sats = fs.upcoming_working_saturdays(fs.load_config())
    bsw_note = (f"公司实行大小周，以下周六是工作日：{'、'.join(sats[:6])}；"
                f"其余周六及所有周日休息。\n") if sats else ""
    prompt = f"""今天是 {today.isoformat()}（星期{"一二三四五六日"[today.weekday()]}）。
{bsw_note}
下面是一条发给公司机器人的消息。如果它是在申请请假，输出严格 JSON（不要任何其他文字）：
{{"leave": true, "type": "事假|病假|年假 之一", "start": "YYYY-MM-DD", "end": "YYYY-MM-DD", "days": 数字, "reason": "一句话事由，没有则空串"}}
天数规则：半天=0.5；"明天请一天"即 start=end=明天、days=1；跨休息日的按自然日写 start/end，days 只数工作日（大周班六算工作日）。
如果不是请假申请（例如询问请假政策、闲聊），输出 {{"leave": false}}。
消息：{text}"""
    r = subprocess.run([CLAUDE, "-p", prompt, "--model", "haiku"],
                       capture_output=True, text=True, timeout=90, env=_claude_env())
    m = re.search(r"\{.*\}", r.stdout, re.S)
    if not m:
        if r.returncode != 0 or "log" in (r.stdout + r.stderr).lower():
            raise RuntimeError(f"claude CLI 不可用: {(r.stdout or r.stderr).strip()[:120]}")
        return None
    try:
        d = json.loads(m.group())
    except json.JSONDecodeError:
        return None
    if not d.get("leave"):
        return None
    if d.get("type") not in ("事假", "病假", "年假"):
        d["type"] = "事假"
    try:
        datetime.date.fromisoformat(d["start"])
        datetime.date.fromisoformat(d["end"])
        d["days"] = float(d["days"])
    except (KeyError, ValueError, TypeError):
        return None
    return d


def find_employee(open_id):
    cfg = fs.load_config()
    app = fs.app_token_from_url(cfg["base_url"])
    te = fs.table_id_by_name(app, cfg["tables"]["employee"])
    for r in fs.list_records(app, te):
        f = r["fields"]
        users = f.get("飞书账号")
        if isinstance(users, list) and users and users[0].get("id") == open_id:
            sup = f.get("上级")
            approver = sup[0]["id"] if isinstance(sup, list) and sup else default_approver(cfg)
            return {"姓名": fs.cell_text(f.get("姓名")), "工号": fs.cell_text(f.get("工号")),
                    "open_id": open_id, "approver": approver}
    return None


def _ts(date_str):
    return int(datetime.datetime.fromisoformat(date_str).timestamp() * 1000)


def _approval_card(emp, req, record_id, decided=None):
    md = (f"**{emp['姓名']}**（{emp['工号']}）申请 **{req['type']} {req['days']}天**\n"
          f"{req['start']} ~ {req['end']}"
          + (f"\n事由:{req['reason']}" if req.get("reason") else ""))
    elements = [{"tag": "markdown", "content": md}]
    if decided:
        elements.append({"tag": "markdown", "content": f"**{decided}**"})
        template = "green" if decided == "已同意" else "red"
    else:
        template = "orange"
        elements.append({"tag": "action", "actions": [
            {"tag": "button", "text": {"tag": "plain_text", "content": "同意"}, "type": "primary",
             "value": {"la": "approve", "rid": record_id}},
            {"tag": "button", "text": {"tag": "plain_text", "content": "驳回"}, "type": "danger",
             "value": {"la": "reject", "rid": record_id}},
        ]})
    return {"config": {"wide_screen_mode": True, "update_multi": True},
            "header": {"title": {"tag": "plain_text", "content": "请假审批"}, "template": template},
            "elements": elements}


def try_handle_leave(text, sender_open_id, chat_id):
    """请假意图则完整处理并返回 True；否则 False 交回原有问答分支。"""
    if not INTENT_RE.search(text):
        return False
    try:  # 即时回执，解析要几秒
        fs.send_md(chat_id, "chat_id", "收到，正在为你解析请假信息…", "请假")
    except Exception:
        pass
    try:
        req = parse_leave(text)
    except Exception as e:
        log("parse error:", e)
        fs.send_md(chat_id, "chat_id",
                   "请假解析服务暂时不可用，请稍后重发一句，或走审批中心提请假。"
                   "（管理员请检查 claude CLI 登录态）", "请假")
        return True
    if not req:
        return False

    emp = find_employee(sender_open_id)
    if not emp:
        fs.send_md(chat_id, "chat_id",
                   "你的飞书账号还没绑定到员工管理表，请联系管理员绑定后再请假。", "请假")
        return True

    cfg = fs.load_config()
    app = fs.app_token_from_url(cfg["base_url"])
    tl = table_id(app, LEAVE_TABLE)
    now = int(datetime.datetime.now().timestamp() * 1000)
    rec = fs.create_record(app, tl, {
        "摘要": f"{emp['姓名']} {req['type']} {req['days']}天 {req['start']}",
        "姓名": emp["姓名"], "工号": emp["工号"], "请假类型": req["type"],
        "开始日期": _ts(req["start"]), "结束日期": _ts(req["end"]),
        "天数": req["days"], "事由": req.get("reason", ""),
        "状态": "待审批", "提交时间": now,
    })
    rid = rec["record"]["record_id"]
    card = _approval_card(emp, req, rid)
    fs.api("POST", "/im/v1/messages", params={"receive_id_type": "open_id"},
           body={"receive_id": emp["approver"], "msg_type": "interactive",
                 "content": json.dumps(card, ensure_ascii=False)})
    aname = approver_name(cfg, emp["approver"])
    fs.send_md(chat_id, "chat_id",
               f"✅ 已提交给 **{aname}** 审批：**{req['type']} {req['days']}天**"
               f"（{req['start']} ~ {req['end']}）。审批结果会第一时间通知你。", "请假")
    log(f"request {rid}: {emp['姓名']} {req['type']} {req['days']}天")
    return True


_processing = set()
_plock = threading.Lock()


def handle_card_action(event):
    """卡片按钮回调。飞书要求 3 秒内响应：立即回 toast，重活丢后台线程。"""
    action = (event.get("event") or {}).get("action") or {}
    value = action.get("value") or {}
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            value = {}
    rid, la = value.get("rid"), value.get("la")
    if not rid or la not in ("approve", "reject"):
        return {}
    operator = (((event.get("event") or {}).get("operator")) or {}).get("open_id", "")
    msg_id = ((event.get("event") or {}).get("context") or {}).get("open_message_id")
    with _plock:
        if rid in _processing:
            return {"toast": {"type": "info", "content": "正在处理中…"}}
        _processing.add(rid)
    threading.Thread(target=_process_decision, args=(rid, la, operator, msg_id),
                     daemon=True).start()
    return {"toast": {"type": "success",
                      "content": "已同意，处理中…" if la == "approve" else "已驳回，处理中…"}}


def _process_decision(rid, la, operator, msg_id):
    try:
        _do_decision(rid, la, operator, msg_id)
    except Exception as e:
        log(f"decision error {rid}: {e}")
    finally:
        with _plock:
            _processing.discard(rid)


def _do_decision(rid, la, operator, msg_id):
    cfg = fs.load_config()
    app = fs.app_token_from_url(cfg["base_url"])
    tl = table_id(app, LEAVE_TABLE)
    rec = fs.api("GET", f"/bitable/v1/apps/{app}/tables/{tl}/records/{rid}")
    f = (rec.get("record") or {}).get("fields") or {}
    if fs.cell_text(f.get("状态")) != "待审批":
        log(f"{rid} 已处理过，忽略重复点击")
        return

    req = {"type": fs.cell_text(f.get("请假类型")), "days": fs.cell_num(f.get("天数")),
           "start": datetime.datetime.fromtimestamp(f["开始日期"] / 1000).strftime("%Y-%m-%d"),
           "end": datetime.datetime.fromtimestamp(f["结束日期"] / 1000).strftime("%Y-%m-%d"),
           "reason": fs.cell_text(f.get("事由"))}
    emp_name, emp_no = fs.cell_text(f.get("姓名")), fs.cell_text(f.get("工号"))
    approved = la == "approve"
    status = "已同意" if approved else "已驳回"
    now = int(datetime.datetime.now().timestamp() * 1000)
    fs.update_record(app, tl, rid, {"状态": status, "审批人": operator, "审批时间": now})

    if approved:  # 秒级入账：考勤表按月累加，年假走年假已用
        ta = table_id(app, cfg["tables"]["attendance"])
        field = cfg["leave_type_map"].get(req["type"], cfg["leave_type_map"]["_default"])
        month_dt = datetime.datetime.fromisoformat(req["start"])
        upsert_attendance(app, ta, cfg, {"姓名": emp_name, "工号": emp_no}, month_dt,
                          field, req["days"])
        log(f"{rid} approved -> 考勤[{field}] +{req['days']}")
    else:
        log(f"{rid} rejected by {operator}")

    # 通知申请人
    emp = None
    te = table_id(app, cfg["tables"]["employee"])
    for r in fs.list_records(app, te):
        if fs.cell_text(r["fields"].get("工号")) == emp_no:
            users = r["fields"].get("飞书账号")
            if isinstance(users, list) and users:
                emp = users[0]["id"]
    if emp:
        icon = "✅" if approved else "❌"
        extra = "考勤表已自动更新。" if approved else "如有疑问请联系审批人。"
        fs.send_md(emp, "open_id",
                   f"{icon} 你的 **{req['type']} {req['days']}天**（{req['start']} ~ {req['end']}）"
                   f"{status}。{extra}", "请假结果")

    # 原卡片替换成结果态（按钮消失，防止重复点击）
    emp_info = {"姓名": emp_name, "工号": emp_no}
    new_card = _approval_card(emp_info, req, rid, decided=status)
    if msg_id:
        try:
            fs.api("PATCH", f"/im/v1/messages/{msg_id}",
                   body={"content": json.dumps(new_card, ensure_ascii=False)})
        except RuntimeError as e:
            log("card patch failed:", e)
