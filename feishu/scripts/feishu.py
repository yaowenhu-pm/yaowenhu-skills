#!/usr/bin/env python3
"""
feishu.py — 飞书全功能 CLI（基于 lark-oapi + user_access_token）
2026-06-27

凭证来源：.infidive-docs.env / .infidive-docs-token.json（setup.py 首次授权生成）。
如需切换账号，可用 FEISHU_TOKEN_FILE 指定另一个 token 文件。

用法：
  python3 feishu.py <命令> [参数...]

【个人邮箱】
  mail-list [limit=20]                       列出最近邮件及附件
  mail-get <message_id>                      获取邮件详情
  mail-download <message_id> <保存目录>       下载邮件中的非内联附件
  mail-folders                               列出个人邮箱文件夹
  mail-rules                                 列出个人邮箱收信规则
  mail-classify-install [--apply]            预览或安装自动分类文件夹与规则
  mail-classify [--limit 100] [--apply]      预览或移动历史邮件
  invoice-collect [--mailbox 邮箱地址] [--limit 100] [--root 目录] [--dry-run]
                                                收集发票附件和可信正文链接、去重并生成汇总 CSV

【消息】
  send-text  <chat_id|open_id|email> <id类型> <文本>
             id类型: open_id | user_id | email | chat_id
  send-card  <chat_id> <card_json_or_file>    发卡片消息到群
  send-card-bot <chat_id> <card_json_or_file> 用 App 身份发卡片（无需用户 OAuth，适合 cron 无人值守）
  send-md    <id> <id类型> <md文本或文件> [标题]  发渲染后的 Markdown 卡片（用户身份）
  send-md-bot <id> <id类型> <md文本或文件> [标题] 发渲染后的 Markdown 卡片（App身份，可发 open_id，适合无人值守）
  update-md-bot <message_id> <md文本或文件> [标题]  更新 bot 已发的 Markdown 卡片（流式/进度刷新）
  reply      <message_id> <文本>               回复某条消息
  msg-list   <chat_id> [limit=20]             拉取群消息列表（oldest-first）
  msg-recent <chat_id> [limit=20]             最近N条消息(正序返回, 读近期上下文用这个; msg-list 是 oldest-first)
  last-reply <chat_id> [open_id或-] [limit=20] 读最新一条回复（newest-first，默认跳过bot自己）——感知新人回复
  msg-get    <message_id>                     获取指定消息
  msg-search <关键词> [limit=20]               搜索可见群近期消息
  msg-resource <message_id> <file_key> <保存路径> [type=file] 下载消息资源
  send-image <id> <id类型> <图片路径>           上传并发送图片
  send-file  <id> <id类型> <文件路径> [file_type=stream] 上传并发送文件

【群/会话】
  chat-list                                   列出我加入的群
  chat-info  <chat_id>                        群详情
  chat-members <chat_id>                      群成员列表
  chat-create <name> [open_id1,open_id2,...]  建群
  chat-search <关键词> [limit=20]              搜索可见群

【用户/组织】
  me                                          我的用户信息
  user-info  <open_id>                        查某用户
  dept-list  [dept_id]                        列部门（默认根部门）
  dept-members <dept_id>                      部门成员

【日历】
  cal-list                                    我的日历列表
  cal-events <calendar_id> [days=7]           未来N天的事件
  cal-create <calendar_id> <标题> <开始> <结束> 创建事件
             时间格式: 2026-06-27T10:00:00+08:00

【知识库】
  wiki-spaces                                 列所有知识库
  wiki-nodes <space_id> [parent_token]        列知识库子节点
  wiki-tree  <space_id> [depth=2]             打印知识库目录树
  wiki-node-info <节点URL或token>             查节点详情（space_id/obj_type/obj_token），copy/move/rename 前先看这个
  wiki-copy  <节点URL或token> <目标space_id> [目标parent_token] [标题]
             整节点复制（含图片等富媒体，不走 markdown 不丢图）；目标parent_token留空=复制到目标知识库顶层
  wiki-move  <节点URL或token> <目标space_id> [目标parent_token]
             整节点移动（原节点消失）；对目标parent_token指向的节点没有编辑权会报 no destination parent node permission，
             留空移到顶层通常不受此限制，可先移顶层再等有权限的人/开权限后二次move到目标分类下
  wiki-rename <节点URL或token> <新标题>       改节点标题（只改节点标题，不改文档正文内的标题块，正文首行标题需用 update 单独改）

【多维表格 Base/Bitable】
  base-create-app <名称> [folder_token]       新建多维表格 App
  base-create-table <base> <表名> <fields_json或文件> [视图名] 新建数据表
  base-tables  <base_url_or_app_token>        列数据表
  base-fields  <base> <table_id>              列字段
  base-records <base> <table_id> [limit=20]   列记录
  base-search  <base> <table_id> <body_json或文件> [limit=20] 查询记录
  base-create  <base> <table_id> <fields_json或文件> 新增记录
  base-update  <base> <table_id> <record_id> <fields_json或文件> 更新记录
  base-delete  <base> <table_id> <record_id>  删除记录

【云空间文件】
  drive-root                                  获取云空间根目录 token
  drive-upload <folder_token> <文件路径> [文件名] 上传文件到云空间
  drive-download <file_token> <保存路径>      下载云空间文件
  media-download <file_token> <保存路径>      下载云文档素材

【云文档】
  list                                        云空间文档
  read   <URL>                               读文档
  blocks <URL>                               列块
  update <URL> <block_id> <文本>             改块
  append <URL> <文本>                        追加（Markdown表格会转原生表格并自动估算列宽；不写空行/横线）
  create <标题> [正文]                       新建文档（正文同append）
  insert-image  <URL> <图片路径> [align=1] [width=0]   插入图片（align: 1=左 2=居中 3=右）
  update-image  <URL> <block_id> [align=1] [width=0] [height=0]  调整图片块对齐/尺寸
  push-wiki     <md文件> <节点URL> [标题]    推到节点下（导入后自动估算表格列宽并清理空行/横线）
  push-wiki-top <md文件> <节点URL> [标题]    推到知识库顶层（导入后自动估算表格列宽并清理空行/横线）
  fix-mentions  <URL>                       把文档内 @姓名 纯文本替换为真正的飞书提及
"""
import os, sys, json, time, re, fcntl, subprocess, threading, unicodedata, urllib.parse
import requests
import requests.adapters

# 瞬时网络错误自动重试（SSL EOF / 连接重置 / 429/5xx）。
# 连接阶段失败对任何方法都安全重试（请求未发出）；读阶段只重试幂等方法，
# 避免消息类 POST 重发造成重复推送。退避 ~2s/4s/8s。
_retry = requests.adapters.Retry(
    total=3, connect=3, read=2, backoff_factor=2,
    status_forcelist=(429, 500, 502, 503),
)
_session = requests.Session()
_session.mount("https://", requests.adapters.HTTPAdapter(max_retries=_retry))
requests.get, requests.post = _session.get, _session.post
requests.put, requests.patch, requests.delete = _session.put, _session.patch, _session.delete

BASE = "https://open.feishu.cn/open-apis"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
MAIL_COMMANDS = {
    "mail-list", "mail-get", "mail-download", "mail-folders", "mail-rules",
    "mail-classify-install", "mail-classify", "invoice-collect",
}
PROFILE = os.environ.get("FEISHU_PROFILE")
if not PROFILE:
    PROFILE = "mail" if len(sys.argv) > 1 and sys.argv[1] in MAIL_COMMANDS else "default"
ENV = os.path.join(ROOT, ".feishu-mail.env" if PROFILE == "mail" else ".infidive-docs.env")
DEFAULT_TOK = os.path.join(ROOT, ".feishu-mail-token.json" if PROFILE == "mail" else ".infidive-docs-token.json")

def _token_file():
    path = os.environ.get("FEISHU_TOKEN_FILE", DEFAULT_TOK)
    return path if os.path.isabs(path) else os.path.join(ROOT, path)

TOK  = _token_file()
LOCK = TOK + ".lock"
BOT_TOKEN_REFRESH_SKEW = 120
_BOT_TOKEN_LOCK = threading.Lock()
_BOT_TOKEN_CACHE = {"token": None, "exp": 0.0}

# ── 自动检测 skill 更新 ────────────────────────────────────────────────────────

def _check_update():
    """每小时最多检查一次远端是否有新版本，有则提示用户 git pull。"""
    repo = os.path.join(HERE, "..", "..")
    stamp = os.path.join(HERE, "..", ".update-check")
    try:
        if os.path.exists(stamp) and time.time() - os.path.getmtime(stamp) < 3600:
            return
        open(stamp, "w").close()
        subprocess.run(["git", "fetch", "--quiet"], cwd=repo, timeout=5,
                       capture_output=True)
        local  = subprocess.check_output(["git", "rev-parse", "HEAD"],
                                         cwd=repo).strip()
        remote = subprocess.check_output(["git", "rev-parse", "@{u}"],
                                         cwd=repo).strip()
        if local != remote:
            print("⚠️  feishu skill 有新版本，运行以下命令更新：")
            print("   cd ~/infiDive-skills && git pull\n")
    except Exception:
        pass

_check_update()

# ── 用户映射（姓名 → open_id）─────────────────────────────────────────────────
USERS = {
    # 团队花名册不入公开仓，私有部署时按此格式补齐：
    # "张三": "ou_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
}

# ── 凭证 ──────────────────────────────────────────────────────────────────────

def _app():
    if not os.path.exists(ENV):
        sys.exit(f"[FATAL] 缺凭证 {ENV}（需 FEISHU_APP_ID / FEISHU_APP_SECRET）")
    env = {}
    for ln in open(ENV):
        ln = ln.strip()
        if "=" in ln and not ln.startswith("#"):
            k, v = ln.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env["FEISHU_APP_ID"], env["FEISHU_APP_SECRET"]

def _valid(st):
    return st.get("access_token") and time.time() < st.get("exp", 0) - 120

def _reauth_hint(reason):
    """token 不可用时的恢复指引。给 agent 看的：按步骤走，不要试浏览器自动化。"""
    setup = os.path.abspath(os.path.join(ROOT, "setup.py"))
    prefix = ""
    if PROFILE != "default":
        prefix += f"FEISHU_PROFILE={PROFILE} "
    if os.environ.get("FEISHU_TOKEN_FILE"):
        prefix += f"FEISHU_TOKEN_FILE={os.environ['FEISHU_TOKEN_FILE']} "
    return (
        f"[FATAL] {reason}\n"
        "需要用户重新授权一次（约30秒）。恢复步骤（不要尝试用浏览器自动化打开 feishu.cn，也不要直接跑交互式 setup.py）：\n"
        f"  1. 运行 `{prefix}python3 {setup} --url`，把打印出的授权链接【原样】发给用户，请用户在浏览器打开并点「授权」\n"
        "  2. 授权后页面会跳到 https://example.com/?code=XXX...（页面打不开是正常的），请用户把地址栏的完整 URL 粘回来\n"
        f"  3. 运行 `{prefix}python3 {setup} --code '<用户粘贴的完整URL>'` 完成换 token，然后重试原命令"
    )

def _token():
    st = json.load(open(TOK)) if os.path.exists(TOK) else {}
    if _valid(st):
        return st["access_token"]
    if not st.get("refresh_token"):
        sys.exit(_reauth_hint(f"{TOK} 缺 token，需先 OAuth 授权"))
    aid, asec = _app()
    lf = open(LOCK, "w")
    fcntl.flock(lf, fcntl.LOCK_EX)
    try:
        st = json.load(open(TOK)) if os.path.exists(TOK) else {}
        if _valid(st):
            return st["access_token"]
        d = requests.post(f"{BASE}/authen/v2/oauth/token",
            json={"grant_type": "refresh_token", "client_id": aid, "client_secret": asec,
                  "refresh_token": st["refresh_token"]}, timeout=20).json()
        if not d.get("access_token"):
            sys.exit(_reauth_hint(f"user token 刷新失败（refresh_token 已失效或被轮换）: {d}"))
        new = {"access_token": d["access_token"],
               "exp": time.time() + d.get("expires_in", 7200),
               "refresh_token": d.get("refresh_token", st["refresh_token"])}
        tmp = TOK + ".tmp"
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            os.write(fd, json.dumps(new).encode())
        finally:
            os.close(fd)
        os.chmod(tmp, 0o600); os.replace(tmp, TOK); os.chmod(TOK, 0o600)
        return new["access_token"]
    finally:
        fcntl.flock(lf, fcntl.LOCK_UN); lf.close()

def _invalidate_bot_token():
    """清除进程内 bot token；收到 401/99991663 后调用。"""
    with _BOT_TOKEN_LOCK:
        _BOT_TOKEN_CACHE["token"] = None
        _BOT_TOKEN_CACHE["exp"] = 0.0

def _bot_token(force_refresh=False):
    """获取 tenant_access_token；force_refresh 用于无效 token 后立即刷新。"""
    with _BOT_TOKEN_LOCK:
        now = time.time()
        if force_refresh:
            _BOT_TOKEN_CACHE["token"] = None
            _BOT_TOKEN_CACHE["exp"] = 0.0
        elif (_BOT_TOKEN_CACHE["token"] and
              now < _BOT_TOKEN_CACHE["exp"] - BOT_TOKEN_REFRESH_SKEW):
            return _BOT_TOKEN_CACHE["token"]

        _BOT_TOKEN_CACHE["token"] = None
        _BOT_TOKEN_CACHE["exp"] = 0.0
        aid, asec = _app()
        r = requests.post(f"{BASE}/auth/v3/tenant_access_token/internal",
            json={"app_id": aid, "app_secret": asec}, timeout=10).json()
        token = r.get("tenant_access_token")
        if not token:
            sys.exit(f"[FATAL] 获取 bot token 失败: {r}")
        try:
            expire = float(r["expire"])
        except (KeyError, TypeError, ValueError):
            expire = 0.0
        if expire > 0:
            _BOT_TOKEN_CACHE["token"] = token
            _BOT_TOKEN_CACHE["exp"] = time.time() + expire
        return token

def _h():
    return {"Authorization": f"Bearer {_token()}", "Content-Type": "application/json; charset=utf-8"}

def _bot_h(force_refresh=False):
    return {"Authorization": f"Bearer {_bot_token(force_refresh=force_refresh)}", "Content-Type": "application/json; charset=utf-8"}

def _bot_token_invalid(response):
    if getattr(response, "status_code", None) == 401:
        return True
    try:
        return str(response.json().get("code")) == "99991663"
    except ValueError:
        return False

def _bot_request(method, url, **kwargs):
    """bot 消息/CardKit 请求；无效 token 时只强制刷新并重试一次。"""
    request = getattr(requests, method)

    def send(force_refresh=False):
        headers = dict(kwargs.get("headers") or {})
        headers.update(_bot_h(force_refresh=force_refresh))
        request_kwargs = {k: v for k, v in kwargs.items() if k != "headers"}
        return request(url, headers=headers, **request_kwargs)

    response = send()
    if _bot_token_invalid(response):
        _invalidate_bot_token()
        return send(force_refresh=True)
    return response

def _get(path, **params):
    r = requests.get(f"{BASE}{path}", headers=_h(), params=params or None, timeout=20).json()
    if r.get("code") != 0:
        sys.exit(f"[ERR] {path}: {r.get('msg')} ({r.get('code')})")
    return r.get("data", {})

def _post(path, body):
    r = requests.post(f"{BASE}{path}", headers=_h(), json=body, timeout=30).json()
    if r.get("code") != 0:
        sys.exit(f"[ERR] {path}: {r.get('msg')} ({r.get('code')})")
    return r.get("data", {})

def _json(data):
    return json.dumps(data, ensure_ascii=False, indent=2)

def _json_arg(value):
    if os.path.isfile(value):
        value = open(value, encoding="utf-8").read()
    return json.loads(value)

def _download(path, dest, **params):
    r = requests.get(f"{BASE}{path}", headers={"Authorization": f"Bearer {_token()}"},
                     params=params or None, stream=True, timeout=120)
    if r.status_code != 200:
        try:
            err = r.json()
        except Exception:
            err = r.text[:300]
        return f"下载失败: {err}"
    with open(dest, "wb") as f:
        for chunk in r.iter_content(1024 * 256):
            if chunk:
                f.write(chunk)
    return f"✓ 已保存 {dest}"

# ── 个人邮箱 ──────────────────────────────────────────────────────────────────

def _mail_api(mailbox_id="me"):
    from feishu_mail import FeishuMailAPI
    return FeishuMailAPI(BASE, _h, mailbox_id=mailbox_id)

def mail_list(limit=20):
    from feishu_mail import list_mail
    return _json(list_mail(_mail_api(), limit))

def mail_get(message_id):
    return _json(_mail_api().get_message(message_id))

def mail_download(message_id, destination):
    from feishu_mail import download_mail
    return _json(download_mail(_mail_api(), message_id, destination))

def mail_folders():
    return _json(_mail_api().list_folders())

def mail_rules():
    return _json(_mail_api().list_rules())

def mail_classify_install(arguments):
    from feishu_mail_classify import MailClassificationManager, parse_install_args
    options = parse_install_args(arguments)
    return _json(MailClassificationManager(_mail_api()).install(apply=options.apply))

def mail_classify(arguments):
    from feishu_mail_classify import MailClassificationManager, parse_classify_args
    options = parse_classify_args(arguments)
    if options.limit < 1:
        sys.exit("[ERR] --limit 必须大于 0")
    return _json(MailClassificationManager(_mail_api()).classify(
        limit=options.limit, apply=options.apply,
    ))

def invoice_collect(arguments):
    from feishu_mail import InvoiceArchiver, parse_collect_args
    options = parse_collect_args(arguments)
    if options.limit < 1:
        sys.exit("[ERR] --limit 必须大于 0")
    return _json(InvoiceArchiver(_mail_api(options.mailbox), options.root).collect(
        limit=options.limit, dry_run=options.dry_run,
    ))

# ── 消息 ──────────────────────────────────────────────────────────────────────

def send_text(receive_id, id_type, text):
    d = _post(f"/im/v1/messages?receive_id_type={id_type}", {
        "receive_id": receive_id,
        "msg_type": "text",
        "content": json.dumps({"text": text}),
    })
    return f"✓ message_id={d.get('message_id')}"

def send_text_bot(receive_id, id_type, text):
    r = _bot_request("post", f"{BASE}/im/v1/messages?receive_id_type={id_type}",
        json={"receive_id": receive_id, "msg_type": "text",
              "content": json.dumps({"text": text})}, timeout=30).json()
    if r.get("code") != 0:
        sys.exit(f"[ERR] bot send: {r.get('msg')} ({r.get('code')})")
    return f"✓ message_id={r['data'].get('message_id')}"

def send_card(chat_id, card):
    if os.path.isfile(card):
        card = open(card).read()
    d = _post("/im/v1/messages?receive_id_type=chat_id", {
        "receive_id": chat_id,
        "msg_type": "interactive",
        "content": card,
    })
    return f"✓ message_id={d.get('message_id')}"

def send_card_bot(chat_id, card):
    if os.path.isfile(card):
        card = open(card).read()
    r = _bot_request("post", f"{BASE}/im/v1/messages?receive_id_type=chat_id",
        json={"receive_id": chat_id, "msg_type": "interactive", "content": card},
        timeout=30).json()
    if r.get("code") != 0:
        sys.exit(f"[ERR] bot send-card: {r.get('msg')} ({r.get('code')})")
    return f"✓ message_id={r['data'].get('message_id')}"

def _md_card(md, title=None, template="blue"):
    card = {"config": {"wide_screen_mode": True},
            "elements": [{"tag": "markdown", "content": md}]}
    if title:
        card["header"] = {"template": template,
                          "title": {"tag": "plain_text", "content": title}}
    return json.dumps(card, ensure_ascii=False)

def send_md(receive_id, id_type, md, title=None):
    """以用户身份发渲染后的 Markdown 卡片（标题/列表/加粗/链接都会渲染）。md 可为文本或文件路径。"""
    if os.path.isfile(md):
        md = open(md, encoding="utf-8").read()
    d = _post(f"/im/v1/messages?receive_id_type={id_type}", {
        "receive_id": receive_id,
        "msg_type": "interactive",
        "content": _md_card(md, title),
    })
    return f"✓ message_id={d.get('message_id')}"

def send_md_bot(receive_id, id_type, md, title=None, reply_to=None):
    """以 App(bot) 身份发渲染后的 Markdown 卡片，可发给 open_id/chat_id，适合无人值守推送。
    reply_to 传入 message_id 时以"回复该消息"形式发出（此时 receive_id/id_type 仅作退化兜底）。"""
    if os.path.isfile(md):
        md = open(md, encoding="utf-8").read()
    content = _md_card(md, title)
    if reply_to:
        r = _bot_request("post", f"{BASE}/im/v1/messages/{reply_to}/reply",
                          json={"msg_type": "interactive", "content": content}, timeout=30).json()
        if r.get("code") == 0:
            return f"✓ message_id={r['data'].get('message_id')}"
        # 被回复消息已撤回/过期 → 退化为普通发送
    r = _bot_request("post", f"{BASE}/im/v1/messages?receive_id_type={id_type}",
        json={"receive_id": receive_id, "msg_type": "interactive",
              "content": content}, timeout=30).json()
    if r.get("code") != 0:
        sys.exit(f"[ERR] bot send-md: {r.get('msg')} ({r.get('code')})")
    return f"✓ message_id={r['data'].get('message_id')}"


def update_md_bot(message_id, md, title=None):
    """更新 bot 已发出的 Markdown 卡片（PATCH），用于流式输出/进度刷新。
    message_id 从 send_md_bot 返回串里取。注意飞书对同一卡片的更新有频控，建议 ≥1 秒节流。"""
    if os.path.isfile(md):
        md = open(md, encoding="utf-8").read()
    r = _bot_request("patch", f"{BASE}/im/v1/messages/{message_id}",
        json={"content": _md_card(md, title)}, timeout=30).json()
    if r.get("code") != 0:
        sys.exit(f"[ERR] bot update-md: {r.get('msg')} ({r.get('code')})")
    return "✓ updated"


def send_interactive_bot(receive_id, id_type, card):
    """以 App(bot) 身份发交互卡片（含按钮/动作），card 为 dict 或已序列化 JSON 串。
    返回 message_id（按钮回调换卡时要用）。失败抛 RuntimeError 而非 sys.exit——
    本函数会在长连接回调线程里被间接调用，不能把整个进程 exit 掉。"""
    content = card if isinstance(card, str) else json.dumps(card, ensure_ascii=False)
    r = _bot_request("post", f"{BASE}/im/v1/messages?receive_id_type={id_type}",
        json={"receive_id": receive_id, "msg_type": "interactive", "content": content}, timeout=30).json()
    if r.get("code") != 0:
        raise RuntimeError(f"bot send-interactive: {r.get('msg')} ({r.get('code')})")
    return r["data"].get("message_id")


def update_card_bot(message_id, card):
    """整卡替换 bot 已发出的交互卡片（PATCH），用于按钮点击后把卡片换成结果态
    （按钮消失、防重复点击）。card 为 dict 或 JSON 串。失败抛 RuntimeError。"""
    content = card if isinstance(card, str) else json.dumps(card, ensure_ascii=False)
    r = _bot_request("patch", f"{BASE}/im/v1/messages/{message_id}",
        json={"content": content}, timeout=30).json()
    if r.get("code") != 0:
        raise RuntimeError(f"bot update-card: {r.get('msg')} ({r.get('code')})")
    return "✓ updated"


# ---- 流式卡片（CardKit streaming）：真打字机效果，客户端逐字渲染 ----

def stream_card_start(receive_id, id_type, initial_md, element_id="md_main", reply_to=None):
    """创建流式卡片实体并发送。返回 card_id，后续用 stream_card_update/finish 增量更新。
    与 update_md_bot（整卡 PATCH，视觉跳变）不同，流式卡片由客户端做平滑打印动画。
    reply_to 传入某条 message_id 时，卡片以"回复该消息"形式发出（群里问答成对、@到提问人），
    此时 receive_id/id_type 被忽略——回复目标由被回复消息决定。"""
    card = {"schema": "2.0",
            "config": {"streaming_mode": True,
                       "streaming_config": {"print_frequency_ms": {"default": 30},
                                            "print_step": {"default": 2},
                                            "print_strategy": "fast"}},
            "body": {"elements": [{"tag": "markdown", "content": initial_md, "element_id": element_id}]}}
    r = _bot_request("post", f"{BASE}/cardkit/v1/cards",
                      json={"type": "card_json", "data": json.dumps(card, ensure_ascii=False)}, timeout=30).json()
    if r.get("code") != 0:
        sys.exit(f"[ERR] cardkit create: {r.get('msg')} ({r.get('code')})")
    card_id = r["data"]["card_id"]
    content = json.dumps({"type": "card", "data": {"card_id": card_id}})
    if reply_to:
        r2 = _bot_request("post", f"{BASE}/im/v1/messages/{reply_to}/reply",
                           json={"msg_type": "interactive", "content": content}, timeout=30).json()
        if r2.get("code") != 0:  # 被回复消息可能已撤回/过期，退化为普通发送
            r2 = _bot_request("post", f"{BASE}/im/v1/messages?receive_id_type={id_type}",
                               json={"receive_id": receive_id, "msg_type": "interactive",
                                     "content": content}, timeout=30).json()
    else:
        r2 = _bot_request("post", f"{BASE}/im/v1/messages?receive_id_type={id_type}",
                           json={"receive_id": receive_id, "msg_type": "interactive",
                                 "content": content}, timeout=30).json()
    if r2.get("code") != 0:
        sys.exit(f"[ERR] cardkit send: {r2.get('msg')} ({r2.get('code')})")
    return card_id


def stream_card_update(card_id, content, sequence, element_id="md_main"):
    """流式增量更新卡片文本。sequence 必须严格递增；建议 ≥0.5s 节流。"""
    r = _bot_request("put", f"{BASE}/cardkit/v1/cards/{card_id}/elements/{element_id}/content",
                     json={"content": content, "sequence": sequence}, timeout=30).json()
    if r.get("code") != 0:
        sys.exit(f"[ERR] cardkit update: {r.get('msg')} ({r.get('code')})")
    return "✓"


def stream_card_finish(card_id, content, sequence, element_id="md_main"):
    """定稿：写入最终内容并关闭流式模式（光标动画消失）。"""
    stream_card_update(card_id, content, sequence, element_id)
    r = _bot_request("patch", f"{BASE}/cardkit/v1/cards/{card_id}/settings",
                       json={"settings": json.dumps({"config": {"streaming_mode": False}}),
                             "sequence": sequence + 1}, timeout=30).json()
    if r.get("code") != 0:
        sys.exit(f"[ERR] cardkit finish: {r.get('msg')} ({r.get('code')})")
    return "✓ finished"

def reply_msg(message_id, text):
    d = _post(f"/im/v1/messages/{message_id}/reply", {
        "msg_type": "text",
        "content": json.dumps({"text": text}),
    })
    return f"✓ reply_id={d.get('message_id')}"

def msg_get(message_id):
    return _json(_get(f"/im/v1/messages/{message_id}"))

def msg_list(chat_id, limit=20):
    d = _get(f"/im/v1/messages", container_id_type="chat",
             container_id=chat_id, page_size=limit)
    msgs = d.get("items", [])
    lines = []
    for m in msgs:
        sender = m.get("sender", {}).get("id", "?")
        ts = m.get("create_time", "")
        ct = m.get("msg_type", "")
        body = m.get("body", {}).get("content", "")
        try:
            body = json.loads(body).get("text", body)
        except Exception:
            pass
        lines.append(f"{ts}\t{sender}\t[{ct}] {body[:80]}")
    return "\n".join(lines) or "(无消息)"

def msg_recent(chat_id, limit=20):
    """最近 N 条消息，按时间正序返回（最新在最后）。
    注意 msg_list 是 oldest-first（从群历史最早开始）——读"近期上下文"必须用本函数。"""
    d = _get("/im/v1/messages", container_id_type="chat",
             container_id=chat_id, page_size=int(limit), sort_type="ByCreateTimeDesc")
    lines = []
    for m in reversed(d.get("items", [])):
        sender = m.get("sender", {}).get("id", "?")
        ts = m.get("create_time", "")
        ct = m.get("msg_type", "")
        body = m.get("body", {}).get("content", "")
        try:
            body = json.loads(body).get("text", body)
        except Exception:
            pass
        lines.append(f"{ts}\t{sender}\t[{ct}] {body[:80]}")
    return "\n".join(lines) or "(无消息)"
def last_reply(chat_id, sender=None, limit=20):
    """读某会话最新一条回复（newest-first）。sender 指定 open_id 只看该人；
    不指定则跳过 bot 自己(cli_*)，返回最近一条真人消息——用于感知新人是否回复。"""
    d = _get("/im/v1/messages", container_id_type="chat",
             container_id=chat_id, page_size=int(limit), sort_type="ByCreateTimeDesc")
    for m in d.get("items", []):
        sid = m.get("sender", {}).get("id", "")
        if sender and sid != sender:
            continue
        if not sender and str(sid).startswith("cli_"):
            continue
        body = m.get("body", {}).get("content", "")
        try:
            body = json.loads(body).get("text", body)
        except Exception:
            pass
        return _json({"sender": sid, "create_time": m.get("create_time"),
                      "message_id": m.get("message_id"),
                      "msg_type": m.get("msg_type"), "text": body})
    return "(无匹配回复)"

def msg_search(query, limit=20):
    found, chat_page = [], ""
    max_hits = int(limit)
    while len(found) < max_hits:
        p = {"page_size": 50}
        if chat_page:
            p["page_token"] = chat_page
        chats = requests.get(f"{BASE}/im/v1/chats", headers=_h(), params=p, timeout=20).json()
        if chats.get("code") != 0:
            return f"搜索失败: {chats}"
        data = chats.get("data", {})
        for chat in data.get("items", []):
            if len(found) >= max_hits:
                break
            chat_id = chat.get("chat_id")
            msgs = requests.get(f"{BASE}/im/v1/messages", headers=_h(),
                                params={"container_id_type": "chat", "container_id": chat_id,
                                        "page_size": 50}, timeout=20).json()
            if msgs.get("code") != 0:
                continue
            for m in msgs.get("data", {}).get("items", []):
                body = m.get("body", {}).get("content", "")
                text = body
                try:
                    parsed = json.loads(body)
                    text = parsed.get("text") or parsed.get("content") or body
                except Exception:
                    pass
                if query in str(text):
                    found.append({
                        "chat_name": chat.get("name", ""),
                        "chat_id": chat_id,
                        "message_id": m.get("message_id"),
                        "create_time": m.get("create_time"),
                        "msg_type": m.get("msg_type"),
                        "text": str(text)[:300],
                    })
                if len(found) >= max_hits:
                    break
        if not data.get("has_more"):
            break
        chat_page = data.get("page_token", "")
    return _json(found)

def msg_resource(message_id, file_key, dest, res_type="file"):
    return _download(f"/im/v1/messages/{message_id}/resources/{file_key}", dest, type=res_type)

def upload_image(image_path):
    with open(image_path, "rb") as f:
        r = requests.post(f"{BASE}/im/v1/images",
                          headers={"Authorization": f"Bearer {_token()}"},
                          data={"image_type": "message"},
                          files={"image": (os.path.basename(image_path), f)},
                          timeout=120).json()
    if r.get("code") != 0:
        sys.exit(f"[ERR] 上传图片失败: {r}")
    return r["data"]["image_key"]

def send_image(receive_id, id_type, image_path):
    image_key = upload_image(image_path)
    d = _post(f"/im/v1/messages?receive_id_type={id_type}", {
        "receive_id": receive_id,
        "msg_type": "image",
        "content": json.dumps({"image_key": image_key}),
    })
    return f"✓ image_key={image_key}\n✓ message_id={d.get('message_id')}"

def upload_im_file(file_path, file_type="stream"):
    with open(file_path, "rb") as f:
        r = requests.post(f"{BASE}/im/v1/files",
                          headers={"Authorization": f"Bearer {_token()}"},
                          data={"file_type": file_type, "file_name": os.path.basename(file_path)},
                          files={"file": (os.path.basename(file_path), f)},
                          timeout=120).json()
    if r.get("code") != 0:
        sys.exit(f"[ERR] 上传消息文件失败: {r}")
    return r["data"]["file_key"]

def send_file(receive_id, id_type, file_path, file_type="stream"):
    file_key = upload_im_file(file_path, file_type)
    d = _post(f"/im/v1/messages?receive_id_type={id_type}", {
        "receive_id": receive_id,
        "msg_type": "file",
        "content": json.dumps({"file_key": file_key}),
    })
    return f"✓ file_key={file_key}\n✓ message_id={d.get('message_id')}"

# ── 群/会话 ───────────────────────────────────────────────────────────────────

def chat_list():
    items, page = [], ""
    while True:
        p = {"page_size": 100}
        if page: p["page_token"] = page
        r = requests.get(f"{BASE}/im/v1/chats", headers=_h(), params=p, timeout=20).json()
        if r.get("code") != 0: sys.exit(f"[ERR] {r}")
        data = r.get("data", {})
        items += data.get("items", [])
        if not data.get("has_more"): break
        page = data.get("page_token", "")
    return "\n".join(f"{c.get('chat_id')}\t{c.get('name','')}\t成员{c.get('member_count',0)}" for c in items)

def chat_info(chat_id):
    d = _get(f"/im/v1/chats/{chat_id}")
    return json.dumps(d, ensure_ascii=False, indent=2)

def chat_members(chat_id):
    items, page = [], ""
    while True:
        p = {"page_size": 100}
        if page: p["page_token"] = page
        r = requests.get(f"{BASE}/im/v1/chats/{chat_id}/members", headers=_h(), params=p, timeout=20).json()
        if r.get("code") != 0: sys.exit(f"[ERR] {r}")
        data = r.get("data", {})
        items += data.get("items", [])
        if not data.get("has_more"): break
        page = data.get("page_token", "")
    return "\n".join(f"{m.get('member_id')}\t{m.get('name','')}" for m in items)

def chat_create(name, open_ids=""):
    body = {"name": name, "chat_mode": "group", "chat_type": "private"}
    if open_ids:
        body["user_id_list"] = [i.strip() for i in open_ids.split(",") if i.strip()]
    d = _post("/im/v1/chats", body)
    return f"✓ chat_id={d.get('chat_id')}"

def chat_search(query, limit=20):
    d = _get("/im/v1/chats/search", query=query, page_size=int(limit))
    return _json(d)

# ── 用户/组织 ─────────────────────────────────────────────────────────────────

def me():
    d = _get("/authen/v1/user_info")
    return json.dumps(d, ensure_ascii=False, indent=2)

def user_info(open_id):
    d = _get("/contact/v3/users/" + open_id, user_id_type="open_id")
    return json.dumps(d.get("user", d), ensure_ascii=False, indent=2)

def dept_list(dept_id="0"):
    d = _get("/contact/v3/departments", department_id=dept_id,
             user_id_type="open_id", department_id_type="open_department_id", page_size=50)
    items = d.get("items", [])
    return "\n".join(f"{i.get('open_department_id')}\t{i.get('name')}\t成员{i.get('member_count',0)}" for i in items)

def dept_members(dept_id):
    items, page = [], ""
    while True:
        p = {"department_id": dept_id, "department_id_type": "open_department_id",
             "user_id_type": "open_id", "page_size": 50}
        if page: p["page_token"] = page
        r = requests.get(f"{BASE}/contact/v3/users", headers=_h(), params=p, timeout=20).json()
        if r.get("code") != 0: sys.exit(f"[ERR] {r}")
        data = r.get("data", {})
        items += data.get("items", [])
        if not data.get("has_more"): break
        page = data.get("page_token", "")
    return "\n".join(f"{u.get('open_id')}\t{u.get('name')}\t{u.get('email','')}" for u in items)

# ── 日历 ──────────────────────────────────────────────────────────────────────

def cal_list():
    d = _get("/calendar/v4/calendars")
    return "\n".join(
        f"{c.get('calendar_id')}\t{c.get('summary','')}\t{c.get('type','')}"
        for c in d.get("calendar_list", [])
    )

def cal_events(calendar_id, days=7):
    now = int(time.time())
    end = now + int(days) * 86400
    d = _get(f"/calendar/v4/calendars/{calendar_id}/events",
             start_time=str(now), end_time=str(end), page_size=50)
    events = d.get("items", [])
    lines = []
    for e in events:
        start = e.get("start_time", {}).get("timestamp", "")
        title = e.get("summary", "")
        eid   = e.get("event_id", "")
        lines.append(f"{start}\t{title}\t{eid}")
    return "\n".join(lines) or "(无事件)"

def cal_create(calendar_id, summary, start, end):
    d = _post(f"/calendar/v4/calendars/{calendar_id}/events", {
        "summary": summary,
        "start_time": {"timestamp": str(int(time.mktime(time.strptime(start, "%Y-%m-%dT%H:%M:%S+08:00"))))},
        "end_time":   {"timestamp": str(int(time.mktime(time.strptime(end,   "%Y-%m-%dT%H:%M:%S+08:00"))))},
    })
    return f"✓ event_id={d.get('event',{}).get('event_id')}"

# ── 知识库 ────────────────────────────────────────────────────────────────────

def wiki_spaces():
    items, page = [], ""
    while True:
        p = {"page_size": 50}
        if page: p["page_token"] = page
        r = requests.get(f"{BASE}/wiki/v2/spaces", headers=_h(), params=p, timeout=20).json()
        if r.get("code") != 0: sys.exit(f"[ERR] {r}")
        data = r.get("data", {})
        items += data.get("items", [])
        if not data.get("has_more"): break
        page = data.get("page_token", "")
    return "\n".join(f"{s.get('space_id')}\t{s.get('name','')}\t{s.get('description','')}" for s in items)

def wiki_nodes(space_id, parent_token=""):
    p = {"page_size": 50}
    if parent_token: p["parent_node_token"] = parent_token
    items, page = [], ""
    while True:
        if page: p["page_token"] = page
        r = requests.get(f"{BASE}/wiki/v2/spaces/{space_id}/nodes", headers=_h(), params=p, timeout=20).json()
        if r.get("code") != 0: sys.exit(f"[ERR] {r}")
        data = r.get("data", {})
        items += data.get("items", [])
        if not data.get("has_more"): break
        page = data.get("page_token", "")
    return "\n".join(
        f"{n.get('node_token')}\t{n.get('obj_type','')}\t{n.get('title','')}"
        for n in items
    )

def wiki_tree(space_id, depth=2, parent="", indent=0):
    p = {"page_size": 50}
    if parent: p["parent_node_token"] = parent
    r = requests.get(f"{BASE}/wiki/v2/spaces/{space_id}/nodes", headers=_h(), params=p, timeout=20).json()
    if r.get("code") != 0: return
    for n in r.get("data", {}).get("items", []):
        prefix = "  " * indent + ("└─ " if indent else "")
        print(f"{prefix}{n.get('title','(无标题)')}\t[{n.get('obj_type','')}]\t{n.get('node_token','')}")
        if indent < int(depth) - 1 and n.get("has_child"):
            wiki_tree(space_id, depth, n["node_token"], indent + 1)

def _wiki_node_info(node_token):
    return requests.get(f"{BASE}/wiki/v2/spaces/get_node", headers=_h(), params={"token": node_token}, timeout=20).json()["data"]["node"]

def wiki_node_info(wiki_url_or_token):
    """查节点详情：所属 space_id、obj_type、obj_token 等，copy/move/rename 前先看这个。"""
    return _json(_wiki_node_info(_extract_node_token(wiki_url_or_token)))

def wiki_copy(wiki_url_or_token, target_space_id, target_parent_token="", title=None):
    """整节点复制到目标知识库/节点下，连图片等富媒体一起搬，不像 push-wiki 走 markdown 导入会丢图。
    源文档本身已是 wiki 节点、或图片/富媒体为主时优先用这个而不是 push-wiki。
    target_parent_token 留空 = 复制到目标知识库顶层。"""
    node = _extract_node_token(wiki_url_or_token)
    sid = _wiki_node_info(node)["space_id"]
    body = {"target_space_id": target_space_id}
    if target_parent_token: body["target_parent_token"] = target_parent_token
    if title: body["title"] = title
    return _json(_post(f"/wiki/v2/spaces/{sid}/nodes/{node}/copy", body))

def wiki_move(wiki_url_or_token, target_space_id, target_parent_token=""):
    """整节点移动到目标知识库/节点下（原节点消失，跨空间移动）。
    对 target_parent_token 指向的节点没有编辑权会报 no destination parent node permission；
    留空移到目标知识库顶层通常不受此限制。常见流程：先 copy/move 到顶层保底成功，
    再等节点所有者开权限或本人拿到目标分类节点编辑权后，对新节点二次 move 归位。"""
    node = _extract_node_token(wiki_url_or_token)
    sid = _wiki_node_info(node)["space_id"]
    body = {"target_space_id": target_space_id}
    if target_parent_token: body["target_parent_token"] = target_parent_token
    return _json(_post(f"/wiki/v2/spaces/{sid}/nodes/{node}/move", body))

def wiki_rename(wiki_url_or_token, title):
    """改节点标题。只改知识库侧的节点标题，不改文档正文里的标题块——正文首行标题要另外用 update 命令改。"""
    node = _extract_node_token(wiki_url_or_token)
    sid = _wiki_node_info(node)["space_id"]
    return _json(_post(f"/wiki/v2/spaces/{sid}/nodes/{node}/update_title", {"title": title}))

# ── 多维表格 Base/Bitable ─────────────────────────────────────────────────────

def _base_token(url_or_token):
    m = re.search(r"/base/([A-Za-z0-9]+)", url_or_token)
    if m:
        return m.group(1)
    m = re.search(r"/wiki/([A-Za-z0-9]+)", url_or_token)
    if m:
        d = requests.get(f"{BASE}/wiki/v2/spaces/get_node", headers=_h(),
                         params={"token": m.group(1)}, timeout=20).json()
        if d.get("code") != 0:
            sys.exit(f"[FATAL] wiki 节点解析失败: {d}")
        return d["data"]["node"]["obj_token"]
    return url_or_token

def base_tables(base):
    app_token = _base_token(base)
    items, page = [], ""
    while True:
        p = {"page_size": 100}
        if page:
            p["page_token"] = page
        r = requests.get(f"{BASE}/bitable/v1/apps/{app_token}/tables",
                         headers=_h(), params=p, timeout=20).json()
        if r.get("code") != 0:
            sys.exit(f"[ERR] base-tables: {r}")
        data = r.get("data", {})
        items.extend(data.get("items", []))
        if not data.get("has_more"):
            break
        page = data.get("page_token", "")
    return "\n".join(f"{i.get('table_id')}\t{i.get('name','')}\t{i.get('revision','')}" for i in items)

def base_create_app(name, folder_token=""):
    body = {"name": name}
    if folder_token:
        body["folder_token"] = folder_token
    d = _post("/bitable/v1/apps", body)
    return _json(d)

def base_create_table(base, table_name, fields, view_name="默认视图"):
    app_token = _base_token(base)
    field_defs = _json_arg(fields)
    body = {
        "table": {
            "name": table_name,
            "default_view_name": view_name,
            "fields": field_defs,
        }
    }
    d = _post(f"/bitable/v1/apps/{app_token}/tables", body)
    return _json(d)

def base_fields(base, table_id):
    app_token = _base_token(base)
    items, page = [], ""
    while True:
        p = {"page_size": 100}
        if page:
            p["page_token"] = page
        r = requests.get(f"{BASE}/bitable/v1/apps/{app_token}/tables/{table_id}/fields",
                         headers=_h(), params=p, timeout=20).json()
        if r.get("code") != 0:
            sys.exit(f"[ERR] base-fields: {r}")
        data = r.get("data", {})
        items.extend(data.get("items", []))
        if not data.get("has_more"):
            break
        page = data.get("page_token", "")
    return _json(items)

def base_records(base, table_id, limit=20):
    app_token = _base_token(base)
    d = _get(f"/bitable/v1/apps/{app_token}/tables/{table_id}/records", page_size=int(limit))
    # 表为空时飞书返回 items: null（不是 []）；dict.get 的 default 只在键缺失时生效，
    # 键存在值为 None 会原样透传——调用方 json.loads() 后拿到 None 直接 `for r in records`
    # 就地崩溃（2026-07-06/07 两处调用方各中招一次）。在唯一的数据出口就地拦死。
    items = d.get("items", d)
    return _json(items if items is not None else [])

def base_search(base, table_id, body, limit=20):
    app_token = _base_token(base)
    r = requests.post(f"{BASE}/bitable/v1/apps/{app_token}/tables/{table_id}/records/search",
                      headers=_h(), params={"page_size": int(limit)}, json=_json_arg(body),
                      timeout=30).json()
    if r.get("code") != 0:
        sys.exit(f"[ERR] base-search: {r}")
    return _json(r.get("data", {}))

def base_create(base, table_id, fields):
    app_token = _base_token(base)
    d = _post(f"/bitable/v1/apps/{app_token}/tables/{table_id}/records",
              {"fields": _json_arg(fields)})
    return _json(d)

def base_update(base, table_id, record_id, fields):
    app_token = _base_token(base)
    r = requests.put(f"{BASE}/bitable/v1/apps/{app_token}/tables/{table_id}/records/{record_id}",
                     headers=_h(), json={"fields": _json_arg(fields)}, timeout=30).json()
    if r.get("code") != 0:
        sys.exit(f"[ERR] base-update: {r}")
    return _json(r.get("data", {}))

def base_delete(base, table_id, record_id):
    app_token = _base_token(base)
    r = requests.delete(f"{BASE}/bitable/v1/apps/{app_token}/tables/{table_id}/records/{record_id}",
                        headers=_h(), timeout=30).json()
    if r.get("code") != 0:
        sys.exit(f"[ERR] base-delete: {r}")
    return "✓ 已删除"

# ── 云空间文件 ───────────────────────────────────────────────────────────────

def drive_root():
    d = requests.get(f"{BASE}/drive/explorer/v2/root_folder/meta",
                     headers={"Authorization": f"Bearer {_token()}"},
                     timeout=20).json()
    if d.get("code") != 0:
        sys.exit(f"[ERR] drive-root: {d}")
    return d.get("data", {}).get("token", "")

def drive_upload(folder_token, file_path, file_name=None):
    file_name = file_name or os.path.basename(file_path)
    size = os.path.getsize(file_path)
    with open(file_path, "rb") as f:
        r = requests.post(f"{BASE}/drive/v1/files/upload_all",
                          headers={"Authorization": f"Bearer {_token()}"},
                          data={"file_name": file_name, "parent_type": "explorer",
                                "parent_node": folder_token, "size": str(size)},
                          files={"file": (file_name, f)}, timeout=120).json()
    if r.get("code") != 0:
        sys.exit(f"[ERR] drive-upload: {r}")
    return _json(r.get("data", {}))

def drive_download(file_token, dest):
    return _download(f"/drive/v1/files/{file_token}/download", dest)

def media_download(file_token, dest):
    return _download(f"/drive/v1/medias/{file_token}/download", dest)

# ── 云文档 ────────────────────────────────────────────────────────────────────

def _docid(url_or_id):
    m = re.search(r"/docx/([A-Za-z0-9]+)", url_or_id)
    if m: return m.group(1)
    m = re.search(r"/wiki/([A-Za-z0-9]+)", url_or_id)
    if m:
        d = requests.get(f"{BASE}/wiki/v2/spaces/get_node", headers=_h(),
                         params={"token": m.group(1)}, timeout=20).json()
        if d.get("code") != 0: sys.exit(f"[FATAL] wiki 节点解析失败: {d}")
        return d["data"]["node"]["obj_token"]
    return url_or_id

def list_docs():
    d = requests.get(f"{BASE}/drive/v1/files", headers=_h(), params={"page_size": 30}, timeout=20).json()
    if d.get("code") != 0: return f"列举失败: {d}"
    return "\n".join(f"{f.get('type')}\t{f.get('token')}\t{f.get('name')}" for f in d.get("data", {}).get("files", []))

def read_doc(docid):
    out, page = [], ""
    while True:
        p = {"page_size": 500}
        if page: p["page_token"] = page
        d = requests.get(f"{BASE}/docx/v1/documents/{docid}/blocks", headers=_h(), params=p, timeout=20).json()
        if d.get("code") != 0: return f"读取失败: {d}"
        data = d.get("data", {})
        for b in data.get("items", []):
            for v in b.values():
                if isinstance(v, dict) and "elements" in v:
                    t = "".join(e.get("text_run", {}).get("content", "") for e in v["elements"])
                    if t: out.append(t)
        if not data.get("has_more"): break
        page = data.get("page_token", "")
    return "\n".join(out)

def get_blocks(docid):
    out, page = [], ""
    while True:
        p = {"page_size": 500}
        if page: p["page_token"] = page
        d = requests.get(f"{BASE}/docx/v1/documents/{docid}/blocks", headers=_h(), params=p, timeout=20).json()
        if d.get("code") != 0: return f"读取失败: {d}"
        data = d.get("data", {})
        for b in data.get("items", []):
            txt = ""
            for v in b.values():
                if isinstance(v, dict) and "elements" in v:
                    txt = "".join(e.get("text_run", {}).get("content", "") for e in v["elements"])
            out.append(f"{b.get('block_id')}\tt={b.get('block_type')}\t{txt[:70]}")
        if not data.get("has_more"): break
        page = data.get("page_token", "")
    return "\n".join(out)

def update_block(docid, block_id, new_text):
    body = {"update_text_elements": {"elements": _text_elements(new_text)}}
    d = requests.patch(f"{BASE}/docx/v1/documents/{docid}/blocks/{block_id}",
                       headers=_h(), json=body, timeout=30).json()
    return "✓ 已更新" if d.get("code") == 0 else f"更新失败: {d}"

_DOC_OBJ_TYPES = {  # 飞书云文档 URL path 段 -> obj_type 枚举（官方 MentionObjType）
    "doc": 1, "sheet": 3, "sheets": 3, "base": 8, "bitable": 8,
    "mindnote": 11, "file": 12, "slide": 15, "slides": 15,
    "wiki": 16, "docx": 22,
}
_FEISHU_LINK_RE = re.compile(
    r"https?://[\w.-]+\.(?:feishu\.cn|larksuite\.com|feishu\.net)/"
    r"(doc|docx|sheets?|base|bitable|wiki|mindnote|file|slides?)/([A-Za-z0-9]+)[^\s\)\]]*"
)

def _text_elements(text):
    """把一段文字拆成 text_run + mention_doc 元素：文字里的飞书云文档/知识库链接会变成
    自动拉取标题的文档预览卡片（mention_doc），而不是退化成纯文本超链接。"""
    elements, last = [], 0
    for m in _FEISHU_LINK_RE.finditer(text):
        if m.start() > last:
            elements.append({"text_run": {"content": text[last:m.start()]}})
        obj_type = _DOC_OBJ_TYPES.get(m.group(1))
        elements.append({"mention_doc": {
            "token": m.group(2),
            "obj_type": obj_type,
            "url": urllib.parse.quote(m.group(0), safe=""),
        }})
        last = m.end()
    if last < len(text):
        elements.append({"text_run": {"content": text[last:]}})
    return elements or [{"text_run": {"content": text}}]

def _text_block(text):
    m = re.match(r"^(#{1,6})\s+(.*)$", text)
    if m:
        level = len(m.group(1))
        block_type = 2 + level
        field = f"heading{level}"
        return {"block_type": block_type, field: {"elements": _text_elements(m.group(2).strip())}}
    return {"block_type": 2, "text": {"elements": _text_elements(text)}}

def _post_children(docid, children, index=-1):
    for i in range(0, len(children), 40):
        d = requests.post(f"{BASE}/docx/v1/documents/{docid}/blocks/{docid}/children",
                          headers=_h(), json={"children": children[i:i + 40], "index": index},
                          timeout=30).json()
        if d.get("code") != 0:
            return d
        index = -1
    return {"code": 0}

def _append_text_lines(docid, lines):
    children = [_text_block(ln) for ln in lines if _keep_text_line(ln)]
    return _post_children(docid, children) if children else {"code": 0}

def _is_md_divider_line(line):
    return bool(re.fullmatch(r"\s*(?:-{3,}|\*{3,}|_{3,})\s*", line))

def _keep_text_line(line):
    return bool(line.strip()) and not _is_md_divider_line(line)

def _split_md_row(line):
    s = line.strip()
    if s.startswith("|"): s = s[1:]
    if s.endswith("|"): s = s[:-1]
    cells, buf, esc = [], [], False
    for ch in s:
        if esc:
            buf.append(ch); esc = False
        elif ch == "\\":
            esc = True
        elif ch == "|":
            cells.append("".join(buf).strip()); buf = []
        else:
            buf.append(ch)
    cells.append("".join(buf).strip())
    return cells

def _is_md_table_sep(line):
    cells = _split_md_row(line)
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", c.strip()) for c in cells)

def _is_md_table_at(lines, i):
    return i + 1 < len(lines) and "|" in lines[i] and _is_md_table_sep(lines[i + 1])

def _read_md_table(lines, start):
    rows = [_split_md_row(lines[start])]
    i = start + 2
    while i < len(lines) and "|" in lines[i].strip():
        rows.append(_split_md_row(lines[i]))
        i += 1
    cols = max(len(r) for r in rows)
    rows = [(r + [""] * cols)[:cols] for r in rows]
    return rows, i

def _display_width(text):
    total = 0
    for ch in text:
        total += 2 if unicodedata.east_asian_width(ch) in ("F", "W") else 1
    return total

def _table_column_widths(rows):
    cols = len(rows[0])
    widths = []
    for c in range(cols):
        units = max(_display_width(row[c]) for row in rows)
        widths.append(max(80, min(520, 28 + units * 7)))
    total = sum(widths)
    if total <= 760:
        return widths
    scale = 760 / total
    return [max(80, int(w * scale)) for w in widths]

def _batch_update_text(docid, updates):
    for i in range(0, len(updates), 40):
        d = requests.patch(f"{BASE}/docx/v1/documents/{docid}/blocks/batch_update",
                           headers=_h(), params={"document_revision_id": -1},
                           json={"requests": updates[i:i + 40]}, timeout=30).json()
        if d.get("code") != 0:
            return d
    return {"code": 0}

def _all_blocks(docid):
    items, page = [], ""
    while True:
        p = {"page_size": 500}
        if page:
            p["page_token"] = page
        d = requests.get(f"{BASE}/docx/v1/documents/{docid}/blocks",
                         headers=_h(), params=p, timeout=20).json()
        if d.get("code") != 0:
            return d, []
        data = d.get("data", {})
        items.extend(data.get("items", []))
        if not data.get("has_more"):
            return {"code": 0}, items
        page = data.get("page_token", "")

def _create_table_single(docid, rows):
    table = {
        "block_type": 31,
        "table": {"property": {
            "row_size": len(rows),
            "column_size": len(rows[0]),
            "column_width": _table_column_widths(rows),
            "header_row": True,
        }},
    }
    d = requests.post(f"{BASE}/docx/v1/documents/{docid}/blocks/{docid}/children",
                      headers=_h(), json={"children": [table], "index": -1}, timeout=30).json()
    if d.get("code") != 0:
        return d
    cell_ids = d["data"]["children"][0]["table"]["cells"]
    b, blocks = _all_blocks(docid)
    if b.get("code") != 0:
        return b
    text_by_cell = {
        block.get("parent_id"): block.get("block_id")
        for block in blocks
        if block.get("block_type") == 2
    }
    updates = []
    for cell_id, value in zip(cell_ids, [v for row in rows for v in row]):
        text_id = text_by_cell.get(cell_id)
        if text_id:
            updates.append({
                "block_id": text_id,
                "update_text_elements": {"elements": [{"text_run": {"content": value}}]},
            })
    return _batch_update_text(docid, updates)

def _create_table(docid, rows):
    # 飞书 docx 建表 API 对单次 row_size>=10 会返回 1770001 invalid param（已实测复现，与内容无关）。
    # 超过 9 行时拆成多张表格、重复表头，绕开该限制。
    MAX_ROWS = 9
    if len(rows) <= MAX_ROWS:
        return _create_table_single(docid, rows)
    header, body = rows[0], rows[1:]
    step = MAX_ROWS - 1
    for i in range(0, len(body), step):
        chunk = [header] + body[i:i + step]
        d = _create_table_single(docid, chunk)
        if d.get("code") != 0:
            return d
    return {"code": 0}

def _text_content(block):
    for value in block.values():
        if isinstance(value, dict) and "elements" in value:
            return "".join(e.get("text_run", {}).get("content", "") for e in value["elements"])
    return ""

def _table_rows_from_blocks(table_block, blocks):
    cells = table_block.get("table", {}).get("cells", [])
    prop = table_block.get("table", {}).get("property", {})
    cols = prop.get("column_size") or 0
    if not cells or not cols:
        return []
    text_by_cell = {}
    for block in blocks:
        parent = block.get("parent_id")
        if parent in cells:
            text_by_cell[parent] = text_by_cell.get(parent, "") + _text_content(block)
    values = [text_by_cell.get(cell_id, "") for cell_id in cells]
    return [values[i:i + cols] for i in range(0, len(values), cols)]

def _set_table_column_widths(docid, table_id, widths):
    for idx, width in enumerate(widths):
        d = requests.patch(f"{BASE}/docx/v1/documents/{docid}/blocks/{table_id}",
                           headers=_h(), params={"document_revision_id": -1},
                           json={"update_table_property": {
                               "column_index": idx,
                               "column_width": int(width),
                           }}, timeout=30).json()
        if d.get("code") != 0:
            return d
    return {"code": 0}

def _cleanup_doc_blocks(docid):
    d, blocks = _all_blocks(docid)
    if d.get("code") != 0:
        return d, 0
    targets = []
    for block in blocks:
        if block.get("parent_id") != docid:
            continue
        if block.get("block_type") == 22:
            targets.append(block["block_id"])
        elif block.get("block_type") == 2 and not _text_content(block).strip():
            targets.append(block["block_id"])
    deleted = 0
    for block_id in targets:
        r = delete_block(docid, block_id)
        if not r.startswith("✓"):
            return {"code": -1, "msg": r}, deleted
        deleted += 1
    return {"code": 0}, deleted

def _autofit_tables(docid):
    d, blocks = _all_blocks(docid)
    if d.get("code") != 0:
        return d, 0
    count = 0
    for block in blocks:
        if block.get("block_type") != 31:
            continue
        rows = _table_rows_from_blocks(block, blocks)
        if not rows:
            continue
        d = _set_table_column_widths(docid, block["block_id"], _table_column_widths(rows))
        if d.get("code") != 0:
            return d, count
        count += 1
    return {"code": 0}, count

def append_doc(docid, text):
    lines = text.split("\n")
    pending, i, tables = [], 0, 0
    while i < len(lines):
        if _is_md_table_at(lines, i):
            if pending:
                d = _append_text_lines(docid, pending)
                if d.get("code") != 0:
                    return f"追加失败: {d}"
                pending = []
            rows, i = _read_md_table(lines, i)
            d = _create_table(docid, rows)
            if d.get("code") != 0:
                return f"追加表格失败: {d}"
            tables += 1
        else:
            pending.append(lines[i])
            i += 1
    if pending:
        d = _append_text_lines(docid, pending)
        if d.get("code") != 0:
            return f"追加失败: {d}"
    return f"✓ 已追加（原生表格 {tables} 个）" if tables else "✓ 已追加"

def create_doc(title, content=""):
    d = requests.post(f"{BASE}/docx/v1/documents", headers=_h(), json={"title": title}, timeout=30).json()
    if d.get("code") != 0: return f"创建失败: {d}"
    tok = d["data"]["document"]["document_id"]
    if content: append_doc(tok, content)
    return f"✓ token={tok}"

def _top_children(docid):
    out, page = [], ""
    while True:
        p = {"page_size": 500}
        if page: p["page_token"] = page
        d = requests.get(f"{BASE}/docx/v1/documents/{docid}/blocks/{docid}/children",
                         headers=_h(), params=p, timeout=20).json()
        data = d.get("data", {})
        out += [b["block_id"] for b in data.get("items", [])]
        if not data.get("has_more"): break
        page = data.get("page_token", "")
    return out

def delete_block(docid, block_id):
    ch = _top_children(docid)
    if block_id not in ch: return f"块不在顶层: {block_id}"
    i = ch.index(block_id)
    d = requests.delete(f"{BASE}/docx/v1/documents/{docid}/blocks/{docid}/children/batch_delete",
                        headers=_h(), json={"start_index": i, "end_index": i + 1}, timeout=30).json()
    return "✓ 已删除" if d.get("code") == 0 else f"删除失败: {d}"

def insert_after(docid, after_block_id, text, block_type=2):
    ch = _top_children(docid)
    if after_block_id not in ch: return f"块不在顶层: {after_block_id}"
    i = ch.index(after_block_id) + 1
    # docx 块类型：2=text 3=heading1 4=heading2 5=heading3 6=heading4（字段名与类型一致）
    field = {2: "text", 3: "heading1", 4: "heading2", 5: "heading3", 6: "heading4"}.get(block_type, "text")
    blk = {"block_type": block_type, field: {"elements": _text_elements(text)}}
    d = requests.post(f"{BASE}/docx/v1/documents/{docid}/blocks/{docid}/children",
                      headers=_h(), json={"children": [blk], "index": i}, timeout=30).json()
    return "✓ 已插入" if d.get("code") == 0 else f"插入失败: {d}"

def insert_image(docid, img_path, align=1, width=0):
    """上传本地图片并插入文档末尾。align: 1=左 2=居中 3=右"""
    size = os.path.getsize(img_path)
    fname = os.path.basename(img_path)
    with open(img_path, "rb") as f:
        up = requests.post(f"{BASE}/drive/v1/medias/upload_all",
            headers={"Authorization": f"Bearer {_token()}"},
            data={"file_name": fname, "parent_type": "docx_image",
                  "parent_node": docid, "size": str(size)},
            files={"file": (fname, f)}, timeout=120).json()
    if up.get("code") != 0: return f"上传失败: {up}"
    file_token = up["data"]["file_token"]
    img_obj = {"file_token": file_token, "align": align}
    if width: img_obj["width"] = int(width)
    r = requests.post(f"{BASE}/docx/v1/documents/{docid}/blocks/{docid}/children",
        headers=_h(), json={"children": [{"block_type": 27, "image": img_obj}]},
        timeout=30).json()
    if r.get("code") != 0: return f"插入失败: {r}"
    block_id = r["data"]["children"][0]["block_id"]
    return f"✓ 已插入图片块 {block_id}"


def update_image(docid, block_id, align=1, width=0, height=0):
    """调整已有图片块的对齐方式和尺寸。"""
    patch = {"align": int(align)}
    if width:  patch["width"]  = int(width)
    if height: patch["height"] = int(height)
    r = requests.patch(f"{BASE}/docx/v1/documents/{docid}/blocks/{block_id}",
        headers=_h(), json={"update_image": patch}, timeout=30).json()
    return "✓ 已更新图片块" if r.get("code") == 0 else f"更新失败: {r}"


def _extract_node_token(wiki_url_or_token):
    """从 URL 或裸 node_token 中提取 node_token。"""
    m = re.search(r"/wiki/([A-Za-z0-9]+)", wiki_url_or_token)
    return m.group(1) if m else wiki_url_or_token.strip()

def push_wiki(md_path, wiki_url_or_token, title=None, to_top=False):
    title = title or os.path.splitext(os.path.basename(md_path))[0]
    tok = _token()
    h = {"Authorization": f"Bearer {tok}"}
    root = requests.get(f"{BASE}/drive/explorer/v2/root_folder/meta", headers=h, timeout=20).json().get("data", {}).get("token", "")
    name = os.path.basename(md_path); size = os.path.getsize(md_path)
    with open(md_path, "rb") as f:
        up = requests.post(f"{BASE}/drive/v1/medias/upload_all", headers=h,
            data={"file_name": name, "parent_type": "ccm_import_open", "size": str(size),
                  "extra": json.dumps({"obj_type": "docx", "file_extension": "md"})},
            files={"file": (name, f)}, timeout=120).json()
    if up.get("code") != 0: return f"上传失败: {up}"
    ft = up["data"]["file_token"]
    imp = requests.post(f"{BASE}/drive/v1/import_tasks", headers=_h(),
        json={"file_extension": "md", "file_token": ft, "type": "docx", "file_name": title,
              "point": {"mount_type": 1, "mount_key": root}}, timeout=30).json()
    if imp.get("code") != 0: return f"导入失败: {imp}"
    ticket = imp["data"]["ticket"]; docx_tok = None
    for _ in range(30):
        r = requests.get(f"{BASE}/drive/v1/import_tasks/{ticket}", headers=_h(), timeout=20).json().get("data", {}).get("result", {})
        if r.get("job_status") == 0: docx_tok = r["token"]; break
        time.sleep(2)
    if not docx_tok: return "导入超时"
    clean, cleaned_count = _cleanup_doc_blocks(docx_tok)
    fit, table_count = _autofit_tables(docx_tok)
    node = _extract_node_token(wiki_url_or_token)
    info = requests.get(f"{BASE}/wiki/v2/spaces/get_node", headers=_h(), params={"token": node}, timeout=20).json()["data"]["node"]
    sid = info["space_id"]
    body = {"obj_type": "docx", "obj_token": docx_tok}
    if not to_top: body["parent_wiki_token"] = node
    mv = requests.post(f"{BASE}/wiki/v2/spaces/{sid}/nodes/move_docs_to_wiki", headers=_h(), json=body, timeout=30).json()
    if mv.get("code") != 0: return f"移入知识库失败: {mv}"
    loc = "顶层" if to_top else "节点「{}」下".format(info.get("title", "?"))
    suffix = f"；已自动收窄表格 {table_count}个" if fit.get("code") == 0 and table_count else ""
    if fit.get("code") != 0:
        suffix = f"；表格列宽调整失败: {fit}"
    if clean.get("code") == 0 and cleaned_count:
        suffix += f"；已清理空行/横线 {cleaned_count}个"
    elif clean.get("code") != 0:
        suffix += f"；空行/横线清理失败: {clean}"
    return f"✓ 已推送「{title}」到 {loc}{suffix}"

def wiki_classify(md_path, space_id, depth=3):
    """打印知识库目录树 + 文档摘要，供分类决策使用。"""
    print(f"=== 知识库目录（space_id={space_id}，depth={depth}）===")
    wiki_tree(space_id, depth)
    print("\n=== 文档内容摘要（前 800 字）===")
    try:
        with open(md_path, encoding="utf-8") as f:
            content = f.read(800)
        print(content)
        if os.path.getsize(md_path) > 800:
            print(f"\n... （共约 {os.path.getsize(md_path)} 字节，已截断）")
    except Exception as e:
        print(f"读取文件失败: {e}")
    print("\n--- 根据以上目录结构和文档内容，选择合适的 node_token，再运行 push-wiki ---")

def _split_mentions(text, style=None):
    """把含 @姓名 的字符串拆成 text_run + mention_user 元素列表，保留原始样式。"""
    pattern = re.compile("@(" + "|".join(re.escape(n) for n in USERS) + ")")
    parts = pattern.split(text)
    elements = []
    for i, part in enumerate(parts):
        if i % 2 == 0:
            if part:
                tr = {"content": part}
                if style:
                    tr["text_element_style"] = style
                elements.append({"text_run": tr})
        else:
            mu = {"user_id": USERS[part]}
            if style:
                mu["text_element_style"] = style
            elements.append({"mention_user": mu})
    return elements

def fix_mentions(docid):
    """扫描文档所有块，把 @姓名 纯文本替换为真正的飞书提及。"""
    _pattern = re.compile("@(" + "|".join(re.escape(n) for n in USERS) + ")")
    all_blocks, page = [], ""
    while True:
        p = {"page_size": 500}
        if page: p["page_token"] = page
        d = requests.get(f"{BASE}/docx/v1/documents/{docid}/blocks",
                         headers=_h(), params=p, timeout=20).json()
        if d.get("code") != 0: return f"读取失败: {d}"
        data = d.get("data", {})
        all_blocks.extend(data.get("items", []))
        if not data.get("has_more"): break
        page = data.get("page_token", "")

    updated = 0
    for block in all_blocks:
        block_id = block.get("block_id")
        for key, val in block.items():
            if not isinstance(val, dict) or "elements" not in val:
                continue
            elements = val["elements"]
            full_text = "".join(e.get("text_run", {}).get("content", "") for e in elements)
            if not _pattern.search(full_text):
                continue
            new_elements = []
            for elem in elements:
                tr = elem.get("text_run", {})
                content = tr.get("content", "")
                if content and _pattern.search(content):
                    style = tr.get("text_element_style")
                    new_elements.extend(_split_mentions(content, style))
                else:
                    new_elements.append(elem)
            r = requests.patch(f"{BASE}/docx/v1/documents/{docid}/blocks/{block_id}",
                               headers=_h(),
                               params={"document_revision_id": -1},
                               json={"update_text_elements": {"elements": new_elements}},
                               timeout=30).json()
            if r.get("code") == 0:
                updated += 1
                print(f"  ✓ {block_id}: {full_text[:60]}")
            else:
                print(f"  ✗ {block_id}: {r.get('msg', r)}")
            break
    return f"✓ 共更新 {updated} 个块"

# ── 冒烟测试 ──────────────────────────────────────────────────────────────────

def smoke_test():
    cases = [
        ("身份验证",   "me",          lambda: me()),
        ("群列表",     "chat-list",   lambda: chat_list()),
        ("知识库列表", "wiki-spaces", lambda: wiki_spaces()),
        ("云文档列表", "list",        lambda: list_docs()),
        ("日历列表",   "cal-list",    lambda: cal_list()),
        ("通讯录",     "dept-list",   lambda: dept_list("0")),
        ("云空间根目录", "drive-root", lambda: drive_root()),
    ]
    ok, fail = 0, 0
    print("=" * 45)
    print("飞书 skill · 功能自检")
    print("=" * 45)
    for label, cmd, fn in cases:
        try:
            result = fn()
            # 把返回值转字符串后判断是否含错误标记
            s = str(result)
            if any(x in s for x in ("99991663", "99991679", "无权限", "Unauthorized", "FATAL", "[ERR]")):
                raise RuntimeError(s[:80])
            print(f"  ✅  {label}（{cmd}）")
            ok += 1
        except (Exception, SystemExit) as e:
            print(f"  ❌  {label}（{cmd}）— {e}")
            fail += 1
    print("-" * 45)
    print(f"  共 {ok+fail} 项：{ok} 通过 / {fail} 失败")
    if fail:
        print("  失败项通常是权限未开启，可在飞书开发者后台补充并重新 OAuth 授权。")
    print("=" * 45)

# ── 入口 ──────────────────────────────────────────────────────────────────────

def main():
    a = sys.argv[1:]
    if not a: print(__doc__); return
    cmd = a[0]

    # 个人邮箱
    if   cmd == "mail-list":      print(mail_list(int(a[1]) if len(a) > 1 else 20))
    elif cmd == "mail-get":       print(mail_get(a[1]))
    elif cmd == "mail-download":  print(mail_download(a[1], a[2]))
    elif cmd == "mail-folders":   print(mail_folders())
    elif cmd == "mail-rules":     print(mail_rules())
    elif cmd == "mail-classify-install": print(mail_classify_install(a[1:]))
    elif cmd == "mail-classify":  print(mail_classify(a[1:]))
    elif cmd == "invoice-collect": print(invoice_collect(a[1:]))
    # 消息
    elif cmd == "send-text":     print(send_text(a[1], a[2], a[3]))
    elif cmd == "send-text-bot": print(send_text_bot(a[1], a[2], a[3]))
    elif cmd == "send-card":    print(send_card(a[1], a[2]))
    elif cmd == "send-card-bot": print(send_card_bot(a[1], a[2]))
    elif cmd == "send-md":      print(send_md(a[1], a[2], a[3], a[4] if len(a) > 4 else None))
    elif cmd == "send-md-bot":  print(send_md_bot(a[1], a[2], a[3], a[4] if len(a) > 4 else None))
    elif cmd == "update-md-bot": print(update_md_bot(a[1], a[2], a[3] if len(a) > 3 else None))
    elif cmd == "reply":        print(reply_msg(a[1], a[2]))
    elif cmd == "msg-list":     print(msg_list(a[1], int(a[2]) if len(a) > 2 else 20))
    elif cmd == "msg-recent":   print(msg_recent(a[1], int(a[2]) if len(a) > 2 else 20))
    elif cmd == "last-reply":   print(last_reply(a[1], a[2] if len(a) > 2 and a[2] != "-" else None, int(a[3]) if len(a) > 3 else 20))
    elif cmd == "msg-get":      print(msg_get(a[1]))
    elif cmd == "msg-search":   print(msg_search(a[1], int(a[2]) if len(a) > 2 else 20))
    elif cmd == "msg-resource": print(msg_resource(a[1], a[2], a[3], a[4] if len(a) > 4 else "file"))
    elif cmd == "send-image":   print(send_image(a[1], a[2], a[3]))
    elif cmd == "send-file":    print(send_file(a[1], a[2], a[3], a[4] if len(a) > 4 else "stream"))
    # 群
    elif cmd == "chat-list":    print(chat_list())
    elif cmd == "chat-info":    print(chat_info(a[1]))
    elif cmd == "chat-members": print(chat_members(a[1]))
    elif cmd == "chat-create":  print(chat_create(a[1], a[2] if len(a) > 2 else ""))
    elif cmd == "chat-search":  print(chat_search(a[1], int(a[2]) if len(a) > 2 else 20))
    # 用户
    elif cmd == "me":           print(me())
    elif cmd == "user-info":    print(user_info(a[1]))
    elif cmd == "dept-list":    print(dept_list(a[1] if len(a) > 1 else "0"))
    elif cmd == "dept-members": print(dept_members(a[1]))
    # 日历
    elif cmd == "cal-list":     print(cal_list())
    elif cmd == "cal-events":   print(cal_events(a[1], int(a[2]) if len(a) > 2 else 7))
    elif cmd == "cal-create":   print(cal_create(a[1], a[2], a[3], a[4]))
    # 知识库
    elif cmd == "wiki-spaces":   print(wiki_spaces())
    elif cmd == "wiki-nodes":    print(wiki_nodes(a[1], a[2] if len(a) > 2 else ""))
    elif cmd == "wiki-tree":     wiki_tree(a[1], int(a[2]) if len(a) > 2 else 2)
    elif cmd == "wiki-classify": wiki_classify(a[1], a[2], int(a[3]) if len(a) > 3 else 3)
    elif cmd == "wiki-node-info": print(wiki_node_info(a[1]))
    elif cmd == "wiki-copy":     print(wiki_copy(a[1], a[2], a[3] if len(a) > 3 else "", a[4] if len(a) > 4 else None))
    elif cmd == "wiki-move":     print(wiki_move(a[1], a[2], a[3] if len(a) > 3 else ""))
    elif cmd == "wiki-rename":   print(wiki_rename(a[1], a[2]))
    # 多维表格
    elif cmd == "base-create-app": print(base_create_app(a[1], a[2] if len(a) > 2 else ""))
    elif cmd == "base-create-table": print(base_create_table(a[1], a[2], a[3], a[4] if len(a) > 4 else "默认视图"))
    elif cmd == "base-tables":  print(base_tables(a[1]))
    elif cmd == "base-fields":  print(base_fields(a[1], a[2]))
    elif cmd == "base-records": print(base_records(a[1], a[2], int(a[3]) if len(a) > 3 else 20))
    elif cmd == "base-search":  print(base_search(a[1], a[2], a[3], int(a[4]) if len(a) > 4 else 20))
    elif cmd == "base-create":  print(base_create(a[1], a[2], a[3]))
    elif cmd == "base-update":  print(base_update(a[1], a[2], a[3], a[4]))
    elif cmd == "base-delete":  print(base_delete(a[1], a[2], a[3]))
    # 云空间文件
    elif cmd == "drive-root":     print(drive_root())
    elif cmd == "drive-upload":   print(drive_upload(a[1], a[2], a[3] if len(a) > 3 else None))
    elif cmd == "drive-download": print(drive_download(a[1], a[2]))
    elif cmd == "media-download": print(media_download(a[1], a[2]))
    # 云文档
    elif cmd == "list":         print(list_docs())
    elif cmd == "read":         print(read_doc(_docid(a[1])))
    elif cmd == "blocks":       print(get_blocks(_docid(a[1])))
    elif cmd == "update":       print(update_block(_docid(a[1]), a[2], a[3]))
    elif cmd == "append":       print(append_doc(_docid(a[1]), a[2]))
    elif cmd == "delete":       print(delete_block(_docid(a[1]), a[2]))
    elif cmd == "insert-after": print(insert_after(_docid(a[1]), a[2], a[3], int(a[4]) if len(a) > 4 else 2))
    elif cmd == "create":       print(create_doc(a[1], a[2] if len(a) > 2 else ""))
    elif cmd == "insert-image": print(insert_image(_docid(a[1]), a[2], int(a[3]) if len(a) > 3 else 1, int(a[4]) if len(a) > 4 else 0))
    elif cmd == "update-image": print(update_image(_docid(a[1]), a[2], int(a[3]) if len(a) > 3 else 1, int(a[4]) if len(a) > 4 else 0, int(a[5]) if len(a) > 5 else 0))
    elif cmd == "push-wiki":    print(push_wiki(a[1], a[2], a[3] if len(a) > 3 else None))
    elif cmd == "push-wiki-top":print(push_wiki(a[1], a[2], a[3] if len(a) > 3 else None, to_top=True))
    elif cmd == "fix-mentions": print(fix_mentions(_docid(a[1])))
    elif cmd == "test":         smoke_test()
    else: sys.exit(f"未知命令: {cmd}\n\n运行不带参数查看帮助")

if __name__ == "__main__":
    main()
