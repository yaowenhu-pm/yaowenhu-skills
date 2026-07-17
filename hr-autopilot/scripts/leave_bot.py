#!/usr/bin/env python3
"""独立请假监听器（无小潜 twin_bot 时用）。

长连接监听私聊消息 + 卡片按钮回调，全部路由到 leave_flow。
⚠️ 同一个飞书 App 的事件只会随机推给一条长连接——如果团队里已有人
常驻 twin_bot（它已内置请假分支），就不要再跑这个，否则消息会被分流。

前台调试: python3 scripts/leave_bot.py
常驻:     install.sh 会生成 LaunchAgent com.infidive.hr-autopilot.leavebot
"""
import json
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fs  # noqa: E402
import leave_flow  # noqa: E402


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


_seen = {}


def on_message(data):
    ev = data.get("event") or {}
    msg = ev.get("message") or {}
    sender = ((ev.get("sender") or {}).get("sender_id") or {}).get("open_id")
    mid = msg.get("message_id")
    if not mid or mid in _seen:
        return
    _seen[mid] = time.time()
    for k in [k for k, v in _seen.items() if time.time() - v > 3600]:
        del _seen[k]
    if msg.get("chat_type") != "p2p" or msg.get("message_type") != "text":
        return
    try:
        text = json.loads(msg.get("content") or "{}").get("text", "").strip()
    except json.JSONDecodeError:
        return
    if text:
        leave_flow.try_handle_leave(text, sender, msg.get("chat_id"))


def _plain(obj):
    try:
        import lark_oapi as lark
        raw = lark.JSON.marshal(obj)
        return json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        return obj if isinstance(obj, dict) else getattr(obj, "__dict__", {}) or {}


def main():
    import lark_oapi as lark
    from lark_oapi.event.callback.model.p2_card_action_trigger import (
        P2CardActionTriggerResponse,
    )

    def on_card(event):
        try:
            resp = leave_flow.handle_card_action(_plain(event))
        except Exception as e:
            log("card action error:", e)
            resp = {"toast": {"type": "error", "content": f"处理失败: {e}"[:60]}}
        return P2CardActionTriggerResponse(resp or {})

    handler = (
        lark.EventDispatcherHandler.builder("", "")
        .register_p2_im_message_receive_v1(
            lambda ev: threading.Thread(target=on_message, args=(_plain(ev),), daemon=True).start())
        .register_p2_card_action_trigger(on_card)
        .build()
    )
    log("leave_bot 启动，监听请假消息与审批卡片…")
    lark.ws.Client(fs.APP_ID, fs.APP_SECRET, event_handler=handler).start()


if __name__ == "__main__":
    main()
