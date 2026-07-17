#!/usr/bin/env python3
"""
status_monitor.py — 分别监控 Claude / Codex(OpenAI) 官方 Status Page，各自独立判断变化、独立推送一张简洁飞书卡片
2026-07-01

数据源：Atlassian Statuspage v2 summary API（官方源，无需 API Key）
  Claude: https://status.claude.com/api/v2/summary.json
  Codex/OpenAI: https://status.openai.com/api/v2/summary.json

用法：
  python3 status_monitor.py check <chat_id>                     检查全部服务，只在“出问题”时推送
  python3 status_monitor.py check <chat_id> --services claude   只检查指定服务（逗号分隔）
  python3 status_monitor.py check <chat_id> --force             无视状态和健康度，强制推送当前状态（测试用）
  python3 status_monitor.py check <chat_id> --as-user           改用你本人身份发（默认是 App/bot 身份）
  python3 status_monitor.py check <chat_id> --dry-run           只打印卡片 JSON，不真的发送、不写状态文件

只在 indicator != none（有活跃事件）且和上次记录不同时才推送；服务健康、或从异常恢复到
健康时都不推送，保持安静。状态记录在同目录 .status_state.json，不要手动编辑。

默认用 App（bot）身份发卡，不占用个人账号，适合无人值守。前提：「infidive-全功能助手」
这个 App 必须先被加为目标群成员，否则会报 230002 Bot/User can NOT be out of the chat。
加 --as-user 可以退回用你本人身份发（跟其他 feishu.py 命令一致，无需拉 App 进群）。
"""
import os, sys, json
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(HERE, "..", ".status_state.json")

sys.path.insert(0, HERE)
from feishu import send_card, send_card_bot

SERVICES = {
    "claude": {
        "label": "Claude",
        "summary_url": "https://status.claude.com/api/v2/summary.json",
        "page_url": "https://status.claude.com",
    },
    "codex": {
        "label": "Codex / OpenAI",
        "summary_url": "https://status.openai.com/api/v2/summary.json",
        "page_url": "https://status.openai.com",
    },
}

INDICATOR_TEMPLATE = {"none": "green", "minor": "yellow", "major": "orange", "critical": "red"}


def fetch(service):
    cfg = SERVICES[service]
    r = requests.get(cfg["summary_url"], timeout=15)
    r.raise_for_status()
    d = r.json()
    status = d.get("status", {})
    incidents = [i for i in d.get("incidents", []) if i.get("status") != "resolved"]
    return {
        "indicator": status.get("indicator", "none"),
        "description": status.get("description", "Operational"),
        "incidents": [
            {"name": i.get("name"), "impact": i.get("impact"), "shortlink": i.get("shortlink")}
            for i in incidents
        ],
    }


def load_state():
    if os.path.exists(STATE_FILE):
        return json.load(open(STATE_FILE))
    return {}


def save_state(state):
    tmp = STATE_FILE + ".tmp"
    json.dump(state, open(tmp, "w"), ensure_ascii=False, indent=2)
    os.replace(tmp, STATE_FILE)


def has_changed(prev, cur):
    if prev is None:
        return True
    if prev.get("indicator") != cur["indicator"]:
        return True
    prev_links = sorted(i.get("shortlink") or i.get("name", "") for i in prev.get("incidents", []))
    cur_links = sorted(i.get("shortlink") or i.get("name", "") for i in cur["incidents"])
    return prev_links != cur_links


def build_card(svc, cur):
    cfg = SERVICES[svc]
    names = [i["name"] for i in cur["incidents"] if i.get("name")]
    body = "\n".join(names) if names else cur.get("description", "Operational")
    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": f"{cfg['label']} System Status"},
            "template": INDICATOR_TEMPLATE.get(cur["indicator"], "blue"),
        },
        "elements": [{
            "tag": "div",
            "text": {"tag": "plain_text", "content": body},
        }],
    }


def check(chat_id, services=None, force=False, as_user=False, dry_run=False):
    services = services or list(SERVICES)
    state = load_state()
    changed = []
    for svc in services:
        cur = fetch(svc)
        prev = state.get(svc)
        if force or (has_changed(prev, cur) and cur["indicator"] != "none"):
            changed.append((svc, cur))
        if not dry_run:
            state[svc] = cur
    if not dry_run:
        save_state(state)
    if not changed:
        print("无变化")
        return
    send = send_card if as_user else send_card_bot
    for svc, cur in changed:
        card = build_card(svc, cur)
        if dry_run:
            print(f"{svc}: " + json.dumps(card, ensure_ascii=False))
        else:
            print(f"{svc}: " + send(chat_id, json.dumps(card, ensure_ascii=False)))


def main():
    a = sys.argv[1:]
    if not a or a[0] != "check":
        print(__doc__)
        return
    args = a[1:]
    force = "--force" in args
    as_user = "--as-user" in args
    dry_run = "--dry-run" in args
    args = [x for x in args if x not in ("--force", "--as-user", "--dry-run")]
    services = None
    i = 0
    while i < len(args):
        x = args[i]
        if x.startswith("--services="):
            services = x.split("=", 1)[1].split(",")
            del args[i]
        elif x == "--services":
            if i + 1 >= len(args):
                sys.exit("[FATAL] --services 需要跟一个逗号分隔的服务列表，例如 --services claude,codex")
            services = args[i + 1].split(",")
            del args[i:i + 2]
        else:
            i += 1
    if not args:
        sys.exit("[FATAL] 需要传 chat_id，例如 python3 status_monitor.py check oc_xxx")
    check(args[0], services, force, as_user, dry_run)


if __name__ == "__main__":
    main()
