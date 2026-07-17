#!/usr/bin/env python3
"""请假审批 → 考勤表 同步（幂等）。

遍历员工管理里绑定了「飞书账号」的员工，拉取其近期审批实例，
凡审批名称含「请假」等关键词且状态为 APPROVED、尚未处理过的：
解析请假类型与天数，累加到考勤管理该员工当月记录（无则新建），
并给通知人发飞书卡片。已处理实例记录在 state/processed.json。

用法: python3 scripts/sync_leave.py
"""
import datetime
import json
import os
import re

import fs

STATE = os.path.join(fs.ROOT, "state", "processed.json")


def load_state():
    if os.path.exists(STATE):
        with open(STATE, encoding="utf-8") as f:
            return json.load(f)
    return {"instances": {}}


def save_state(st):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=1)


def parse_ts(v):
    """把审批表单里的时间值转成 datetime（支持 ISO 字符串 / 毫秒 / 秒）。"""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return datetime.datetime.fromtimestamp(v / 1000 if v > 1e11 else v)
    s = str(v).strip().replace("T", " ").replace("+08:00", "")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(s[:len(fmt) + 2].strip(), fmt)
        except ValueError:
            continue
    return None


def parse_leave_form(form_json, hours_per_day):
    """从审批表单控件里解析 (请假类型, 天数, 开始时间)。兼容官方假勤控件与自建表单。"""
    try:
        widgets = json.loads(form_json) if isinstance(form_json, str) else (form_json or [])
    except json.JSONDecodeError:
        return None, None, None
    ltype = days = start = end = None
    for w in widgets:
        if not isinstance(w, dict):
            continue
        wtype = str(w.get("type") or "")
        name = str(w.get("name") or "")
        val = w.get("value")
        if "leaveGroup" in wtype and isinstance(val, dict):
            ltype = val.get("name") or ltype
            start = parse_ts(val.get("start")) or start
            end = parse_ts(val.get("end")) or end
            interval = val.get("interval")
            if isinstance(interval, (int, float)) and interval > 0:
                days = interval / 86400 if interval >= 86400 else interval / (hours_per_day * 3600)
        elif any(k in name for k in ("请假类型", "假期类型", "休假类型")):
            ltype = fs.cell_text(val) or ltype
        elif any(k in name for k in ("开始", "起始")):
            start = parse_ts(val) or start
        elif "结束" in name:
            end = parse_ts(val) or end
        elif any(k in name for k in ("时长", "天数")):
            m = re.search(r"[\d.]+", fs.cell_text(val))
            if m:
                days = float(m.group())
    if days is None and start and end:
        days = max(0.5, round((end - start).total_seconds() / 86400 * 2) / 2)
    return ltype, days, start


def month_range(dt):
    first = dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    nxt = (first + datetime.timedelta(days=32)).replace(day=1)
    return int(first.timestamp() * 1000), int(nxt.timestamp() * 1000)


def upsert_attendance(app, table, cfg, emp, month_dt, leave_field, days):
    """把 days 累加到员工当月考勤记录的 leave_field；没有当月记录则创建。"""
    lo, hi = month_range(month_dt)
    recs = fs.search_records(app, table, {"filter": {"conjunction": "and", "conditions": [
        {"field_name": "工号", "operator": "is", "value": [emp["工号"]]}]}})
    target = None
    for r in recs:
        ts = r["fields"].get("考勤时间")
        if isinstance(ts, (int, float)) and lo <= ts < hi:
            target = r
            break
    if target:
        cur = fs.cell_num(target["fields"].get(leave_field))
        fs.update_record(app, table, target["record_id"], {leave_field: cur + days})
    else:
        rules = cfg["rules"]
        expected = fs.month_workdays(cfg, month_dt.year, month_dt.month) or rules["default_workdays"]
        fs.create_record(app, table, {
            "姓名": emp["姓名"], "工号": emp["工号"], "考勤时间": lo,
            "应出勤": expected,
            "年假": rules["default_annual_leave_days"],
            "病假天数": 0, "事假天数": 0, "年假已用": 0,
            "迟到天数": 0, "早退天数": 0,
            leave_field: days,
        })


def main():
    cfg = fs.load_config()
    app = fs.app_token_from_url(cfg["base_url"])
    t_emp = fs.table_id_by_name(app, cfg["tables"]["employee"])
    t_att = fs.table_id_by_name(app, cfg["tables"]["attendance"])
    keywords = cfg["approval"]["name_keywords"]
    lookback = cfg["approval"].get("lookback_days", 92)
    hours_per_day = cfg["rules"]["hours_per_day"]
    ltype_map = cfg["leave_type_map"]
    st = load_state()
    since = datetime.datetime.now() - datetime.timedelta(days=lookback)
    handled = []

    employees = []
    for r in fs.list_records(app, t_emp):
        f = r["fields"]
        users = f.get("飞书账号")
        if isinstance(users, list) and users:
            employees.append({"姓名": fs.cell_text(f.get("姓名")),
                              "工号": fs.cell_text(f.get("工号")),
                              "open_id": users[0].get("id")})
    if not employees:
        print("员工管理表还没有任何人绑定「飞书账号」列，无法关联审批，跳过。")
        return

    for emp in employees:
        try:
            items = fs.query_instances_by_user(emp["open_id"], status="APPROVED")
        except RuntimeError as e:
            print(f"[warn] 查询 {emp['姓名']} 审批失败: {e}")
            continue
        for it in items:
            inst = it.get("instance") or {}
            appr = it.get("approval") or {}
            code = inst.get("code") or inst.get("instance_code")
            name = appr.get("approval_name") or inst.get("approval_name") or ""
            start_ms = inst.get("start_time")
            if not code or code in st["instances"]:
                continue
            if not any(k in name for k in keywords):
                continue
            if isinstance(start_ms, str) and start_ms.isdigit():
                start_ms = int(start_ms)
            if isinstance(start_ms, (int, float)) and \
                    datetime.datetime.fromtimestamp(start_ms / 1000) < since:
                continue
            detail = fs.get_instance(code)
            if detail.get("status") != "APPROVED":
                continue
            ltype, days, start = parse_leave_form(detail.get("form"), hours_per_day)
            if not days:
                print(f"[warn] 实例 {code}({name}) 无法解析请假时长，跳过（请人工处理）")
                fs.notify_all(cfg, f"⚠️ {emp['姓名']} 的审批「{name}」无法自动解析请假时长，"
                                   f"请人工核对考勤表。实例号 {code}", "请假同步告警")
                st["instances"][code] = {"emp": emp["工号"], "status": "unparsed"}
                continue
            month_dt = start or datetime.datetime.now()
            field = ltype_map.get(ltype or "", ltype_map["_default"])
            upsert_attendance(app, t_att, cfg, emp, month_dt, field, days)
            st["instances"][code] = {"emp": emp["工号"], "type": ltype, "days": days,
                                     "month": month_dt.strftime("%Y-%m")}
            handled.append(f"**{emp['姓名']}** {ltype or '请假'} {days}天"
                           f"（{month_dt.strftime('%Y-%m')}，已计入考勤）")
            print(f"✓ {emp['姓名']} {ltype} {days}天 -> 考勤[{field}]")

    save_state(st)
    if handled:
        md = "请假审批已自动同步到考勤表：\n" + "\n".join(f"- {h}" for h in handled) + \
             f"\n\n[打开考勤表]({cfg['base_url']})"
        fs.notify_all(cfg, md, "请假 → 考勤 自动同步")
    print(f"本次同步 {len(handled)} 条请假记录")


if __name__ == "__main__":
    main()
