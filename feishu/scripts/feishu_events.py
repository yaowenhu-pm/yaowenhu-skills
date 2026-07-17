#!/usr/bin/env python3
"""
feishu_events.py — 飞书长连接事件监听

用法：
  python3 scripts/feishu_events.py listen [events_csv] [log_jsonl]

示例：
  python3 scripts/feishu_events.py listen
  python3 scripts/feishu_events.py listen im.message.receive_v1,calendar.calendar.event.changed_v4 events.jsonl
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ENV = os.path.join(HERE, "..", ".infidive-docs.env")
DEFAULT_EVENTS = "im.message.receive_v1"


def _app():
    if not os.path.exists(ENV):
        sys.exit(f"[FATAL] 缺凭证 {ENV}（需先运行 setup.py）")
    env = {}
    for line in open(ENV):
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env["FEISHU_APP_ID"], env["FEISHU_APP_SECRET"]


def _plain(obj):
    try:
        import lark_oapi as lark
        raw = lark.JSON.marshal(obj)
        return json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        pass
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    if isinstance(obj, list):
        return [_plain(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _plain(v) for k, v in obj.items()}
    if hasattr(obj, "__dict__"):
        return {k: _plain(v) for k, v in obj.__dict__.items() if not k.startswith("_")}
    return str(obj)


def _event_summary(event_type, event):
    data = _plain(event)
    message = (data.get("event") or {}).get("message") or {}
    sender = (data.get("event") or {}).get("sender") or {}
    return {
        "ts": int(time.time()),
        "type": event_type,
        "message_id": message.get("message_id"),
        "chat_id": message.get("chat_id"),
        "message_type": message.get("message_type"),
        "sender": sender,
        "content": message.get("content"),
        "raw": data,
    }


def _emit(log_path, event_type, event):
    line = json.dumps(_event_summary(event_type, event), ensure_ascii=False)
    print(line, flush=True)
    if log_path:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")


HR_SCRIPTS = os.path.expanduser("~/infidive-claude-skills/hr-autopilot/scripts")
MEM_SCRIPTS = os.path.expanduser("~/.claude/automation/infidive-memory-pilot")
DIGEST_SCRIPTS = os.path.expanduser("~/xiaoqian-digest")


def _on_card_action(event, log_path=""):
    """卡片按钮回调必须由 ws 持有进程同步响应（3秒内）。
    多个卡片来源按 value.act 前缀分路：memory pilot 候选记忆（mem_*）优先，
    handle_card_action 返回 None 表示"不是我的卡"，再交给 hr-autopilot 请假审批。
    每路各自 try 兜底，一路抛错不拖累另一路，skill 不存在时回空响应。"""
    from lark_oapi.event.callback.model.p2_card_action_trigger import (
        P2CardActionTriggerResponse,
    )
    data = _plain(event)
    _emit(log_path, "card.action.trigger", event)
    resp = None
    # 每日摘要反馈卡（👍/👎）—— 前缀 digest_，不是它的卡返回 None 继续往下
    if resp is None:
        try:
            if os.path.isdir(DIGEST_SCRIPTS):
                if DIGEST_SCRIPTS not in sys.path:
                    sys.path.insert(0, DIGEST_SCRIPTS)
                import digest_actions
                resp = digest_actions.handle_card_action(data)
        except Exception as e:
            print(f"digest card action error: {e}", flush=True)
    # 候选记忆卡（采纳/丢弃）
    if resp is None:
        try:
            if os.path.isdir(MEM_SCRIPTS):
                if MEM_SCRIPTS not in sys.path:
                    sys.path.insert(0, MEM_SCRIPTS)
                import card_actions
                resp = card_actions.handle_card_action(data)
        except Exception as e:
            print(f"memory card action error: {e}", flush=True)
    # 请假审批卡（memory 卡明确不认领时才走）
    if resp is None:
        resp = {}
        try:
            if os.path.isdir(HR_SCRIPTS):
                if HR_SCRIPTS not in sys.path:
                    sys.path.insert(0, HR_SCRIPTS)
                import leave_flow
                resp = leave_flow.handle_card_action(data)
        except Exception as e:
            print(f"card action error: {e}", flush=True)
    return P2CardActionTriggerResponse(resp or {})


def listen(events_csv=DEFAULT_EVENTS, log_path=""):
    try:
        import lark_oapi as lark
    except Exception:
        sys.exit("[FATAL] 缺少 lark-oapi：请先运行 `python3 -m pip install lark-oapi`")

    aid, asec = _app()
    builder = lark.EventDispatcherHandler.builder("", "")
    events = [e.strip() for e in events_csv.split(",") if e.strip()]
    for event_type in events:
        callback = lambda event, et=event_type: _emit(log_path, et, event)
        method = "register_p2_" + event_type.replace(".", "_")
        if hasattr(builder, method):
            getattr(builder, method)(callback)
        else:
            builder.register_p2_customized_event(event_type, callback)
    builder.register_p2_card_action_trigger(
        lambda event: _on_card_action(event, log_path))

    print(f"listening events: {','.join(events)} (+card.action.trigger)", flush=True)
    lark.ws.Client(aid, asec, event_handler=builder.build()).start()


def main():
    args = sys.argv[1:]
    if not args or args[0] != "listen":
        print(__doc__)
        return
    listen(args[1] if len(args) > 1 else DEFAULT_EVENTS,
           args[2] if len(args) > 2 else "")


if __name__ == "__main__":
    main()
