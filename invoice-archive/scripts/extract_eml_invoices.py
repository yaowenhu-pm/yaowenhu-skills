#!/usr/bin/env python3
"""从飞书邮箱拉取"发票相关邮件"里的 .eml 套娃附件，拆出内层 PDF；
同时列出内层/正文里的发票下载链接（可信直链自动下载）。

用法：在 feishu skill 目录下运行（依赖其 scripts/feishu.py 授权体系）：
  FEISHU_PROFILE=mail python3 extract_eml_invoices.py [--mailbox me] [--limit 200] [--out /tmp/eml_extract] [--feishu-skill ~/.claude/skills/feishu]

可信直链（requests 直接下）：京东 jdcloud-oss.com、税务局 *.chinatax.gov.cn、
淘宝 einvoice.taobao.com、转转 zhuanstatic.com。
百望 pis.baiwang.com → 真实端点 /bwmg/mix/bw/downloadFormat?param=<完整128位hex>&formatType=PDF
同程 finance.17u.cn → 云票汇 /invoicecloud/gateway/invoice/batchDownLoadFiles/<token> 返回 zip
（这两家的链接会打印出来，端点规律见 SKILL.md）
"""
import argparse
import email
import email.policy
import html as htmllib
import re
import sys
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument('--mailbox', default='me')
ap.add_argument('--limit', type=int, default=200)
ap.add_argument('--out', default='/tmp/eml_extract')
ap.add_argument('--feishu-skill', default=str(Path.home() / '.claude/skills/feishu'))
args = ap.parse_args()

sys.path.insert(0, str(Path(args.feishu_skill).expanduser() / 'scripts'))
import feishu            # noqa: E402
import feishu_mail as fm # noqa: E402
import requests          # noqa: E402

TRUSTED = ('jdcloud-oss.com', 'chinatax.gov.cn', 'einvoice.taobao.com', 'zhuanstatic.com')
out = Path(args.out)
out.mkdir(parents=True, exist_ok=True)
api = feishu._mail_api(args.mailbox)
n_pdf = n_link = 0

for mid in api.list_message_ids(args.limit):
    msg = api.get_message(mid)
    if not fm.is_invoice_message(msg):
        continue
    subj = msg.get('subject', '')
    bodies = []  # (来源说明, html正文)
    outer = fm.decode_mail_text(msg.get('body_html'))
    if outer:
        bodies.append((f'正文[{subj[:20]}]', outer))
    for a in fm.non_inline_attachments(msg):
        if not a.get('filename', '').lower().endswith('.eml'):
            continue
        data = api._get(api._mailbox_path(f"/messages/{mid}/attachments/download_url"),
                        {"attachment_ids": a['id']})
        for u in data.get('download_urls', []):
            r = requests.get(u['download_url'], timeout=60)
            r.raise_for_status()
            inner = email.message_from_bytes(r.content, policy=email.policy.default)
            for part in inner.walk():
                fn = part.get_filename() or ''
                if fn.lower().endswith('.pdf'):
                    payload = part.get_payload(decode=True)
                    if payload and payload.lstrip().startswith(b'%PDF-'):
                        f = out / fm.safe_filename(fn)
                        k = 2
                        while f.exists():
                            f = out / f'{Path(fm.safe_filename(fn)).stem}_{k}.pdf'
                            k += 1
                        f.write_bytes(payload)
                        n_pdf += 1
                        print(f'拆出PDF: {f.name}  (来自 {subj[:24]})')
            for part in inner.walk():
                if part.get_content_type() == 'text/html':
                    bodies.append((f'eml内层[{inner.get("subject","")[:20]}]', part.get_content()))
                    break
    for src, body in bodies:
        for raw in re.findall(r'href="([^"]+)"', body):
            link = htmllib.unescape(raw)  # 千万别用显示截断的URL——从原始HTML取完整链接
            if not link.startswith('http'):
                continue
            if any(t in link for t in TRUSTED):
                try:
                    resp = requests.get(link, timeout=90)
                    if resp.content.lstrip().startswith(b'%PDF-'):
                        f = out / f'link_{abs(hash(link)) % 10 ** 8}.pdf'
                        f.write_bytes(resp.content)
                        n_pdf += 1
                        print(f'直链PDF: {f.name}  ({src})')
                    elif resp.content[:2] == b'PK':
                        f = out / f'link_{abs(hash(link)) % 10 ** 8}.zip'
                        f.write_bytes(resp.content)
                        print(f'直链ZIP(需解包,文件名可能GBK): {f.name}  ({src})')
                except Exception as e:
                    print(f'直链失败: {link[:80]} {e}')
            elif re.search(r'发票|invoice|fapiao|baiwang|17u\.cn|efapiao', link, re.I):
                n_link += 1
                print(f'待人工/浏览器链接: {link[:150]}  ({src})')

print(f'\n完成：拆出/直链 PDF {n_pdf} 个，剩余需处理链接 {n_link} 个，输出目录 {out}')
