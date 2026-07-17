#!/usr/bin/env python3
"""hr-autopilot 最小飞书客户端：纯应用身份(tenant_access_token)，无需 OAuth。"""
import json
import os
import time
import urllib.parse

import requests

BASE = "https://open.feishu.cn/open-apis"
APP_ID = os.environ.get("FEISHU_APP_ID", "cli_aab5c810a4f89bd9")
APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_tok_cache = {"token": None, "exp": 0}


def load_config():
    with open(os.path.join(ROOT, "config.json"), encoding="utf-8") as f:
        return json.load(f)


def tenant_token():
    if _tok_cache["token"] and time.time() < _tok_cache["exp"] - 60:
        return _tok_cache["token"]
    r = requests.post(f"{BASE}/auth/v3/tenant_access_token/internal",
                      json={"app_id": APP_ID, "app_secret": APP_SECRET}, timeout=20).json()
    if r.get("code") != 0:
        raise RuntimeError(f"获取 tenant_access_token 失败: {r}")
    _tok_cache["token"] = r["tenant_access_token"]
    _tok_cache["exp"] = time.time() + r.get("expire", 3600)
    return _tok_cache["token"]


def api(method, path, params=None, body=None, ok_codes=()):
    h = {"Authorization": f"Bearer {tenant_token()}", "Content-Type": "application/json"}
    r = requests.request(method, f"{BASE}{path}", headers=h, params=params, json=body, timeout=30)
    d = r.json()
    if d.get("code") not in (0,) + tuple(ok_codes):
        raise RuntimeError(f"{method} {path} -> {d.get('code')} {d.get('msg')}")
    return d.get("data") or {}


# ---------- 多维表格 ----------

def app_token_from_url(url):
    path = urllib.parse.urlparse(url).path
    for part in reversed(path.split("/")):
        if part:
            return part
    raise ValueError(f"无法从 URL 解析 app_token: {url}")


def list_tables(app):
    return api("GET", f"/bitable/v1/apps/{app}/tables", params={"page_size": 100}).get("items", [])


def table_id_by_name(app, name):
    for t in list_tables(app):
        if t["name"] == name:
            return t["table_id"]
    raise RuntimeError(f"找不到数据表「{name}」，请检查 config.json 的 tables 配置")


def list_fields(app, table):
    return api("GET", f"/bitable/v1/apps/{app}/tables/{table}/fields",
               params={"page_size": 100}).get("items", [])


def create_field(app, table, field_name, ftype, prop=None):
    body = {"field_name": field_name, "type": ftype}
    if prop:
        body["property"] = prop
    return api("POST", f"/bitable/v1/apps/{app}/tables/{table}/fields", body=body)


def update_field(app, table, field_id, field_name, ftype, prop):
    return api("PUT", f"/bitable/v1/apps/{app}/tables/{table}/fields/{field_id}",
               body={"field_name": field_name, "type": ftype, "property": prop})


def list_records(app, table):
    items, token = [], None
    while True:
        params = {"page_size": 500}
        if token:
            params["page_token"] = token
        d = api("GET", f"/bitable/v1/apps/{app}/tables/{table}/records", params=params)
        items += d.get("items") or []
        if not d.get("has_more"):
            return items
        token = d.get("page_token")


def search_records(app, table, filter_body):
    items, token = [], None
    while True:
        params = {"page_size": 500}
        if token:
            params["page_token"] = token
        d = api("POST", f"/bitable/v1/apps/{app}/tables/{table}/records/search",
                params=params, body=filter_body)
        items += d.get("items") or []
        if not d.get("has_more"):
            return items
        token = d.get("page_token")


def create_record(app, table, fields):
    return api("POST", f"/bitable/v1/apps/{app}/tables/{table}/records", body={"fields": fields})


def update_record(app, table, record_id, fields):
    return api("PUT", f"/bitable/v1/apps/{app}/tables/{table}/records/{record_id}",
               body={"fields": fields})


def cell_text(v):
    """把 bitable 单元格值统一转成字符串（文本字段返回 [{text,type}] 列表）。"""
    if v is None:
        return ""
    if isinstance(v, list):
        return "".join(x.get("text", "") if isinstance(x, dict) else str(x) for x in v)
    if isinstance(v, dict):
        return v.get("text", "") or str(v)
    return str(v)


def cell_num(v):
    try:
        return float(cell_text(v) or 0) if not isinstance(v, (int, float)) else float(v)
    except (TypeError, ValueError):
        return 0.0


# ---------- 审批 ----------

def query_instances_by_user(open_id, status=None):
    items, token = [], None
    while True:
        params = {"page_size": 100, "user_id_type": "open_id"}
        if token:
            params["page_token"] = token
        body = {"user_id": open_id}
        if status:
            body["instance_status"] = status
        d = api("POST", "/approval/v4/instances/query", params=params, body=body)
        items += d.get("instance_list") or []
        if not d.get("has_more"):
            return items
        token = d.get("page_token")


def get_instance(instance_code):
    return api("GET", f"/approval/v4/instances/{instance_code}",
               params={"user_id_type": "open_id"})


# ---------- 消息通知 ----------

def send_md(receive_id, id_type, md, title="通知"):
    card = {"config": {"wide_screen_mode": True},
            "header": {"title": {"tag": "plain_text", "content": title}, "template": "blue"},
            "elements": [{"tag": "markdown", "content": md}]}
    try:
        api("POST", "/im/v1/messages", params={"receive_id_type": id_type},
            body={"receive_id": receive_id, "msg_type": "interactive",
                  "content": json.dumps(card, ensure_ascii=False)})
    except RuntimeError as e:
        print(f"[warn] 通知发送失败({receive_id}): {e}")


def notify_all(cfg, md, title):
    n = cfg.get("notify", {})
    for oid in n.get("open_ids", []):
        send_md(oid, "open_id", md, title)
    for email in n.get("emails", []):
        send_md(email, "email", md, title)


# ---------- 大小周日历 ----------

def _bsw(cfg):
    return (cfg.get("rules") or {}).get("big_small_week") or {}


def is_working_saturday(cfg, d):
    """d(date) 是否为大周要上班的周六：与锚点周六相隔偶数周。"""
    import datetime as _dt
    b = _bsw(cfg)
    if not b.get("enabled") or d.weekday() != 5:
        return False
    anchor = _dt.date.fromisoformat(b["working_saturday_anchor"])
    return (d - anchor).days % 14 == 0


def is_workday(cfg, d):
    return d.weekday() < 5 or is_working_saturday(cfg, d)


def month_workdays(cfg, year, month):
    """当月应出勤天数 = 周一到周五 + 大周班六。未启用大小周时返回 None。"""
    import calendar
    import datetime as _dt
    if not _bsw(cfg).get("enabled"):
        return None
    n = calendar.monthrange(year, month)[1]
    return sum(1 for day in range(1, n + 1) if is_workday(cfg, _dt.date(year, month, day)))


def upcoming_working_saturdays(cfg, days=70):
    """未来 N 天内的班六日期列表（ISO 串），供请假解析提示词使用。"""
    import datetime as _dt
    today = _dt.date.today()
    return [(today + _dt.timedelta(days=i)).isoformat() for i in range(days)
            if is_working_saturday(cfg, today + _dt.timedelta(days=i))]
