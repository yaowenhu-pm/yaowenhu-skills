#!/usr/bin/env python3
"""
feishu skill · 首次授权引导（每位成员在自己机器上跑一次）

用你本人的飞书账号授权 → 拿到 user token，存本地（600，不进 git）。
之后这台机器上的 Codex / Claude 就能以你的身份读写飞书文档。

用法：
  python3 setup.py                       # 交互式（人在终端跑）
  python3 setup.py --url                 # 只打印授权链接（无 TTY 的 agent 第 1 步）
  python3 setup.py --code '<跳转URL或code>'  # 换 token 并保存（agent 第 2 步）
  FEISHU_TOKEN_FILE=.feishu-token-other.json python3 setup.py
  FEISHU_PROFILE=mail python3 setup.py
依赖：requests（pip install requests，或用项目 venv）

agent（Claude/Codex）注意：交互式模式需要 TTY 输入，在工具 shell 里跑会 EOF 退出。
请改用两步：先 `--url` 把链接发给用户，用户授权后把跳转的完整 URL 粘回来，再 `--code`。
"""
import getpass, os, sys, json, time, urllib.parse
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
PROFILE = os.environ.get("FEISHU_PROFILE", "default")
MAIL_PROFILE = PROFILE == "mail"
ENV = os.path.join(HERE, ".feishu-mail.env" if MAIL_PROFILE else ".infidive-docs.env")
DEFAULT_TOKEN = os.path.join(HERE, ".feishu-mail-token.json" if MAIL_PROFILE else ".infidive-docs-token.json")
ACC = "https://accounts.feishu.cn/open-apis"
BASE = "https://open.feishu.cn/open-apis"
SCOPE = "docx:document drive:drive drive:file drive:file:upload wiki:wiki docs:document.content:read bitable:app bitable:app:readonly base:record:retrieve im:message im:message:readonly im:message.group_at_msg:readonly im:message.p2p_msg:readonly im:resource im:chat calendar:calendar contact:contact.base:readonly offline_access"
MAIL_SCOPE = "mail:user_mailbox.message:readonly mail:user_mailbox.message.subject:read mail:user_mailbox.message.address:read mail:user_mailbox.message.body:read mail:user_mailbox.message:modify mail:user_mailbox.folder:write mail:user_mailbox.rule:write offline_access"
REDIRECT = "https://example.com"
STATE = "infidive2026"

# infiDive 全能助手 · 公司共享 App 凭证（已内置，无需手动输入）
DEFAULT_APP_ID     = "cli_aab5c810a4f89bd9"
DEFAULT_APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "")
EXPORT_SCOPE = "docx:document drive:drive drive:file wiki:wiki docs:document.content:read bitable:app:readonly offline_access"


def _write600(path, content):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, content.encode())
    finally:
        os.close(fd)
    os.chmod(path, 0o600)


def _token_path():
    path = os.environ.get("FEISHU_TOKEN_FILE", DEFAULT_TOKEN)
    return path if os.path.isabs(path) else os.path.join(HERE, path)


def _scope():
    if os.environ.get("FEISHU_SCOPE"):
        return os.environ["FEISHU_SCOPE"]
    if MAIL_PROFILE:
        return MAIL_SCOPE
    if os.environ.get("FEISHU_SCOPE_PROFILE") == "export":
        return EXPORT_SCOPE
    return SCOPE


def _creds(interactive):
    """加载/初始化 App 凭证。普通功能沿用公司共享 App；个人邮件使用独立 App。"""
    if os.path.exists(ENV):
        env = {}
        for line in open(ENV):
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
        aid, asec = env["FEISHU_APP_ID"], env["FEISHU_APP_SECRET"]
        print(f"✓ 已有 app 凭证（App ID: {aid}）\n")
    elif MAIL_PROFILE:
        if not interactive:
            sys.exit("✗ 个人邮件 App 凭证尚未配置，需要人在终端交互式运行一次：\n"
                     "  FEISHU_PROFILE=mail python3 setup.py\n"
                     "（App Secret 不要粘贴到聊天里）")
        print("个人邮件 App 凭证只保存在本机，不要粘贴到聊天或提交到 git。")
        aid = input("App ID: ").strip()
        asec = getpass.getpass("App Secret: ").strip()
        if not aid or not asec:
            sys.exit("✗ App ID / App Secret 不能为空")
        _write600(ENV, f"FEISHU_APP_ID={aid}\nFEISHU_APP_SECRET={asec}\n")
        print(f"✓ 已存个人邮件 App 凭证（App ID: {aid}，权限 600）\n")
    else:
        aid, asec = DEFAULT_APP_ID, DEFAULT_APP_SECRET
        _write600(ENV, f"FEISHU_APP_ID={aid}\nFEISHU_APP_SECRET={asec}\n")
        print(f"✓ 已自动写入公司 App 凭证（App ID: {aid}）\n")
    return aid, asec


def _authorize_url(aid, scope):
    q = urllib.parse.urlencode({
        "client_id": aid, "redirect_uri": REDIRECT, "response_type": "code",
        "scope": scope, "state": STATE,
    })
    return f"{ACC}/authen/v1/authorize?{q}"


def _exchange(aid, asec, raw, token_path):
    """用授权 code（或跳转后的完整 URL）换 token 并落盘。"""
    code = raw.strip().strip('"').strip("'")
    if "code=" in code:
        code = urllib.parse.parse_qs(urllib.parse.urlparse(code).query).get("code", [""])[0]
    if not code:
        sys.exit("✗ 没解析到 code，重跑一次")
    d = requests.post(f"{BASE}/authen/v2/oauth/token", json={
        "grant_type": "authorization_code", "client_id": aid, "client_secret": asec,
        "code": code, "redirect_uri": REDIRECT,
    }, timeout=20).json()
    if not d.get("access_token"):
        sys.exit(f"✗ 换 token 失败：{d}\n（code 是一次性的且几分钟就过期，重新走一遍授权链接；或确认 App Secret 正确）")
    st = {
        "access_token": d["access_token"],
        "exp": time.time() + d.get("expires_in", 7200),
        "refresh_token": d.get("refresh_token"),
    }
    _write600(token_path, json.dumps(st))
    print(f"✓ 已存 {os.path.basename(token_path)}（权限 600）")


def main():
    argv = sys.argv[1:]
    token_path = _token_path()
    scope = _scope()

    if argv and argv[0] == "--url":
        # agent 第 1 步：只打印授权链接（把链接原样发给用户，让用户在浏览器点「授权」）
        aid, _ = _creds(interactive=False)
        print("请用户在浏览器打开下面链接并点「授权」，然后把跳转后的完整 URL 粘回来：\n")
        print(_authorize_url(aid, scope))
        print("\n（授权后会跳到 https://example.com/?code=XXX...，页面打不开是正常的）")
        return

    if argv and argv[0] == "--code":
        # agent 第 2 步：拿用户粘回的 URL/code 换 token
        if len(argv) < 2:
            sys.exit("✗ 用法：python3 setup.py --code '<跳转后的完整URL或code>'")
        aid, asec = _creds(interactive=False)
        _exchange(aid, asec, argv[1], token_path)
        print("\n=== 授权完成！飞书 skill 已可用 ===")
        return

    if argv:
        sys.exit(f"✗ 未知参数 {argv[0]}；支持 --url / --code，或不带参数交互式运行")

    if not sys.stdin.isatty():
        sys.exit("✗ 当前没有 TTY，交互式模式无法输入。agent 请分两步：\n"
                 f"  1. python3 {os.path.abspath(__file__)} --url   # 把打印的链接发给用户\n"
                 f"  2. python3 {os.path.abspath(__file__)} --code '<用户粘回的完整URL>'")

    print(f"=== feishu {'个人邮件' if MAIL_PROFILE else '首次'}授权 ===\n")
    print(f"Token 文件：{token_path}\n")
    aid, asec = _creds(interactive=True)

    print("第 2 步 · 浏览器打开下面链接，用你的飞书账号点「授权」：\n")
    print(f"  {_authorize_url(aid, scope)}\n")
    print("  授权后页面会跳到 https://example.com/?code=XXX...（页面打不开是正常的）\n")

    raw = input("第 3 步 · 把跳转后地址栏的【完整 URL】或其中的 code 粘这里：\n  ").strip()
    _exchange(aid, asec, raw, token_path)
    print("\n=== 授权完成！===")
    print("\n现在请在 Codex 或 Claude 中发送：")
    print("\n  帮我测试飞书 skill 的所有功能是否正常\n")
    print("AI 助手会逐项检查并告诉你哪些功能可用、哪些需要开权限。")


if __name__ == "__main__":
    main()
