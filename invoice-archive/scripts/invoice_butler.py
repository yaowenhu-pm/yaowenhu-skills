#!/usr/bin/env python3
"""invoice_butler —— 发票入库/编号/审计一体化工具。

子命令：
  ingest <src_dir>   解析 src_dir 里的发票 PDF：查重(SHA256+发票号码)、核对抬头税号、
                     重命名"日期_销售方_金额元.pdf"、复制进发票库、追加 发票汇总.csv
  renumber           按开票日期给全库 PDF 加两位序号前缀，同步 CSV 序号列并重算总金额
  audit              终审：文件↔CSV对账、金额三方核对、抬头税号、发票号码查重、
                     图片版发票自动解二维码核验（macOS CoreImage）

依赖：python3 + pypdf；audit 的二维码解码需要 macOS（swift + CoreImage）。
默认发票库 ~/Desktop/发票，默认抬头/税号从环境变量 INVOICE_BUYER / INVOICE_TAX 读取。
"""
import argparse
import csv
import hashlib
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    from pypdf import PdfReader
except ImportError:
    sys.exit("缺依赖：pip3 install pypdf")

UPPER = "零壹贰叁肆伍陆柒捌玖拾佰仟万亿圆元角分整正负"
BAD_CHARS = re.compile(r'[\\/:*?"<>| ]')
FIELDS = ['序号', '邮箱', '邮件日期', '发件人', '主题', '原文件名', '保存文件', '物品', '金额', '处理状态']
SELLER_RE = re.compile(
    r'([一-龥（）·]{3,36}?(?:有限公司|有限责任公司|股份有限公司|工艺品店|商贸有限公司|'
    r'个体工商户|合作社|旅行社|服务部|分公司|商行|店))')
QRDECODE = Path(__file__).with_name('qrdecode.swift')


def flat_text(pdf, pages=2):
    t = ''.join(p.extract_text() or '' for p in PdfReader(str(pdf)).pages[:pages])
    return re.sub(r'\s+', '', t).replace('(', '（').replace(')', '）')


def parse_invoice(pdf, buyer_name, buyer_tax):
    """从 PDF 文本层解析发票要素。图片版发票会解析失败（用 audit 的二维码路径核验）。"""
    try:
        flat = flat_text(pdf)
    except Exception as e:
        return {'err': f'读取失败:{e}'}
    r = {}
    m = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日', flat)
    if m:
        r['date'] = f"{m.group(1)}{int(m.group(2)):02d}{int(m.group(3)):02d}"
    # 价税合计：优先"大写金额+¥数字"，其次"（小写）"，数字可能在 ¥ 前面
    m = (re.search(rf'[{UPPER}]{{3,}}[¥￥](-?[\d,]+\.\d{{2}})', flat)
         or re.search(r'[（(]小写[）)][¥￥]?(-?[\d,]+\.\d{2})', flat))
    if m:
        r['amount'] = m.group(1).replace(',', '')
    m = re.search(r'发票号码[：:]?(\d{18,20})', flat) or re.search(r'(\d{20})', flat)
    if m:
        r['no'] = m.group(1)
    sellers = [c for c in SELLER_RE.findall(flat)
               if buyer_name[:3] not in c and '银行' not in c and '税务' not in c]
    if sellers:
        r['seller'] = sellers[0]
    r['title_ok'] = (buyer_name in flat) and (buyer_tax in flat)
    items = re.findall(r'\*[^*]{2,14}\*([^*¥]{2,26})', flat)
    if items:
        r['item'] = re.sub(r'(规格型号|单位|数量|单价|金额|税率|征收率|税额).*$', '', items[0])[:24]
    r['red'] = r.get('amount', '').startswith('-') or ('被红冲' in flat)
    return r


def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def load_csv(root):
    p = root / '发票汇总.csv'
    if not p.exists():
        return []
    return list(csv.DictReader(p.open(encoding='utf-8-sig')))


def write_csv(root, rows):
    with (root / '发票汇总.csv').open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)


def decode_qr(pdf):
    """抽出 PDF 内嵌图片，用 CoreImage 解二维码。数电票 QR 格式:
    01,32, ,发票号码,金额,YYYYMMDD, ,校验位 —— 这是查验系统扫的权威数据。"""
    try:
        imgs = [im for pg in PdfReader(str(pdf)).pages for im in pg.images]
    except Exception:
        return None
    with tempfile.TemporaryDirectory() as td:
        paths = []
        for i, im in enumerate(imgs):
            f = Path(td) / f'{i}{Path(im.name).suffix or ".png"}'
            f.write_bytes(im.data)
            paths.append(str(f))
        if not paths:
            return None
        out = subprocess.run(['swift', str(QRDECODE), *paths],
                             capture_output=True, text=True).stdout
    for line in out.splitlines():
        m = re.search(r'01,\d+,\s*[^,]*,(\d{18,20}),(-?[\d.]+),(\d{8})', line)
        if m:
            return {'no': m.group(1), 'amount': m.group(2), 'date': m.group(3)}
    return None


# ---------------- ingest ----------------

def cmd_ingest(args):
    root, src = Path(args.root).expanduser(), Path(args.src)
    root.mkdir(exist_ok=True)
    rows = load_csv(root)
    total_rows = [r for r in rows if r.get('邮箱') == '总金额']
    rows = [r for r in rows if r.get('邮箱') != '总金额']

    # 现有库的查重索引（文件名可能带 NN_ 序号前缀）
    seen_sha, seen_no = {}, {}
    for p in root.glob('*.pdf'):
        seen_sha[sha256(p)] = p.name
        try:
            m = re.search(r'(\d{20})', flat_text(p, 1))
            if m:
                seen_no[m.group(1)] = p.name
        except Exception:
            pass

    ingested, dups, skips = [], [], []
    for pdf in sorted(src.glob('*.pdf')):
        h = sha256(pdf)
        if h in seen_sha:
            dups.append((pdf.name, '同内容→' + seen_sha[h]))
            continue
        info = parse_invoice(pdf, args.buyer_name, args.buyer_tax)
        no = info.get('no', '')
        if no and no in seen_no:
            dups.append((pdf.name, '同发票号→' + seen_no[no]))
            continue
        if info.get('err') or not (info.get('date') and info.get('seller') and info.get('amount')):
            # 文本解析失败 → 尝试二维码（图片版发票）
            qr = decode_qr(pdf)
            if qr:
                if qr['no'] in seen_no:
                    dups.append((pdf.name, '同发票号(QR)→' + seen_no[qr['no']]))
                    continue
                info.update(date=qr['date'], amount=qr['amount'], no=qr['no'])
                info.setdefault('seller', re.sub(r'\.pdf$', '', BAD_CHARS.sub('', pdf.stem))[:20])
                info['title_ok'] = info.get('title_ok', False)
                print(f'  ⚠ {pdf.name}: 图片版发票，要素取自二维码，抬头请人工看图核对')
            else:
                skips.append((pdf.name, info.get('err') or f"解析不全 {info}"))
                continue
        seen_sha[h] = pdf.name
        if info.get('no'):
            seen_no[info['no']] = pdf.name
        tag = ('_红冲' if info.get('red') else '') + ('' if info.get('title_ok') else '_抬头待核')
        base = f"{info['date']}_{BAD_CHARS.sub('', info['seller'])[:40]}_{info['amount']}元{tag}"
        target = root / (base + '.pdf')
        n = 2
        while target.exists():  # 同日同商家同金额必须加尾缀，rename 会静默覆盖！
            suffix = f"_尾号{info['no'][-6:]}" if info.get('no') else f"_{n}"
            target = root / (base + suffix + '.pdf')
            n += 1
        shutil.copy(pdf, target)
        rows.append({'序号': '', '邮箱': args.source, '邮件日期': f"{info['date'][:4]}-{info['date'][4:6]}-{info['date'][6:]}",
                     '发件人': '', '主题': args.note, '原文件名': pdf.name, '保存文件': str(target),
                     '物品': info.get('item', ''), '金额': info['amount'], '处理状态': '已保存'})
        ingested.append(target.name)
        print('入库:', target.name)

    for n_, why in dups:
        print('重复丢弃:', n_, '|', why)
    for n_, why in skips:
        print('跳过(需人工):', n_, '|', why)

    saved = [r for r in rows if r['处理状态'] == '已保存']
    total = sum(float(r['金额']) for r in saved)
    rows.append({'序号': '', '邮箱': '总金额', '邮件日期': '', '发件人': '', '主题': '', '原文件名': '',
                 '保存文件': '', '物品': '', '金额': f'{total:.2f}', '处理状态': ''})
    write_csv(root, rows)
    print(f'\n入库 {len(ingested)}，重复 {len(dups)}，跳过 {len(skips)}；'
          f'库存 {len(saved)} 张，总金额 {total:.2f} 元。别忘了跑 renumber。')


# ---------------- renumber ----------------

def cmd_renumber(args):
    root = Path(args.root).expanduser()
    pdfs = sorted(root.glob('*.pdf'), key=lambda p: re.sub(r'^\d{2,3}_', '', p.name))
    width = max(2, len(str(len(pdfs))))
    final_map = {}
    for i, pdf in enumerate(pdfs, 1):
        bare = re.sub(r'^\d{2,3}_', '', pdf.name)
        new = root / f'{i:0{width}d}_{bare}'
        if new != pdf:
            tmp = root / f'.tmp_{i:0{width}d}_{bare}'  # 两段式换名防环
            pdf.rename(tmp)
            final_map[str(pdf)] = (tmp, new)
        else:
            final_map[str(pdf)] = (pdf, new)
    for old, (tmp, new) in final_map.items():
        if tmp != new:
            tmp.rename(new)
    path_map = {old: str(new) for old, (_, new) in final_map.items()}

    rows = load_csv(root)
    seq = {v: f'{i:0{width}d}' for i, v in enumerate(sorted(path_map.values()), 1)}
    for r in rows:
        if r.get('保存文件') in path_map:
            r['保存文件'] = path_map[r['保存文件']]
        r['序号'] = seq.get(r.get('保存文件', ''), '')
    rows.sort(key=lambda r: (r['序号'] == '', r.get('邮箱') == '总金额', r['序号'] or r.get('邮件日期', '')))
    saved = [r for r in rows if r.get('处理状态') == '已保存']
    total = sum(float(r['金额']) for r in saved)
    for r in rows:
        if r.get('邮箱') == '总金额':
            r['金额'] = f'{total:.2f}'
    write_csv(root, rows)
    print(f'重编号 {len(pdfs)} 张 (1-{len(pdfs)})，总金额 {total:.2f}')


# ---------------- audit ----------------

def cmd_audit(args):
    root = Path(args.root).expanduser()
    issues = []
    pdfs = sorted(root.glob('*.pdf'))
    rows = load_csv(root)
    total_row = next((r for r in rows if r.get('邮箱') == '总金额'), None)
    saved = [r for r in rows if r.get('处理状态') == '已保存']

    if len(saved) != len(pdfs):
        issues.append(f'数量不符: 文件{len(pdfs)} vs CSV{len(saved)}')
    for miss in {str(p) for p in pdfs} - {r['保存文件'] for r in saved}:
        issues.append(f'文件不在CSV: {Path(miss).name}')
    for miss in {r['保存文件'] for r in saved} - {str(p) for p in pdfs}:
        issues.append(f'CSV指向不存在的文件: {miss}')

    prefixed = [p for p in pdfs if re.match(r'^\d{2,3}_', p.name)]
    if prefixed:
        seqs = [int(re.match(r'^(\d+)_', p.name).group(1)) for p in prefixed]
        if seqs != list(range(1, len(prefixed) + 1)):
            issues.append('序号不连续')
    for r in saved:
        fn = Path(r['保存文件']).name
        m = re.search(r'_(-?[\d.]+)元', fn)
        if not m or abs(float(m.group(1)) - float(r['金额'])) > 0.001:
            issues.append(f'金额不一致(CSV vs 文件名): {fn}')

    s_csv = sum(float(r['金额']) for r in saved)
    s_file = sum(float(re.search(r'_(-?[\d.]+)元', p.name).group(1)) for p in pdfs
                 if re.search(r'_(-?[\d.]+)元', p.name))
    if total_row and not (abs(s_csv - s_file) < 0.001 and abs(s_csv - float(total_row['金额'])) < 0.001):
        issues.append(f'总额不一致: csv={s_csv:.2f} file={s_file:.2f} 总行={total_row["金额"]}')

    invoice_nos, image_cnt = {}, 0
    for p in pdfs:
        fn_m = re.search(r'_(-?[\d.]+)元', p.name)
        fn_amt = fn_m.group(1) if fn_m else None
        fn_date_m = re.search(r'(\d{8})_', p.name)
        fn_date = fn_date_m.group(1) if fn_date_m else None
        try:
            flat = flat_text(p)
        except Exception as e:
            issues.append(f'读取失败: {p.name} {e}')
            continue
        m = (re.search(rf'[{UPPER}]{{3,}}[¥￥](-?[\d,]+\.\d{{2}})', flat)
             or re.search(r'[（(]小写[）)][¥￥]?(-?[\d,]+\.\d{2})', flat))
        if m:  # 文本票
            if fn_amt and abs(float(m.group(1).replace(',', '')) - float(fn_amt)) > 0.001:
                issues.append(f'票面金额与文件名不符: {p.name} 票面={m.group(1)}')
            if (args.buyer_name not in flat) or (args.buyer_tax not in flat):
                issues.append(f'抬头/税号异常: {p.name}')
            no_m = re.search(r'发票号码[：:]?(\d{18,20})', flat) or re.search(r'(\d{20})', flat)
            no = no_m.group(1) if no_m else None
        else:  # 图片票 → 解二维码（QR 是权威数据，票面印刷可能有 bug）
            image_cnt += 1
            qr = decode_qr(p)
            if not qr:
                issues.append(f'图片票二维码解码失败(需人工看图): {p.name}')
                continue
            no = qr['no']
            if fn_amt and abs(float(qr['amount']) - float(fn_amt)) > 0.001:
                issues.append(f'QR金额与文件名不符: {p.name} QR={qr["amount"]}')
            if fn_date and qr['date'] != fn_date:
                issues.append(f'QR日期与文件名不符: {p.name} QR={qr["date"]}')
        if no:
            if no in invoice_nos:
                issues.append(f'发票号码重复: {p.name} 与 {invoice_nos[no]} ({no})')
            invoice_nos[no] = p.name

    print(f'共 {len(pdfs)} 张（文本 {len(pdfs)-image_cnt} / 图片 {image_cnt}），'
          f'号码登记 {len(invoice_nos)}，合计 {s_csv:.2f} 元')
    if issues:
        print(f'❌ {len(issues)} 个问题:')
        for i in issues:
            print(' -', i)
        sys.exit(1)
    print('✅ 全部核对通过，零差异')


def main():
    import os
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--root', default='~/Desktop/发票', help='发票库目录（默认 ~/Desktop/发票）')
    ap.add_argument('--buyer-name', default=os.environ.get('INVOICE_BUYER', ''), help='报销抬头（公司全名，全角括号）')
    ap.add_argument('--buyer-tax', default=os.environ.get('INVOICE_TAX', ''), help='统一社会信用代码')
    sub = ap.add_subparsers(dest='cmd', required=True)
    pi = sub.add_parser('ingest')
    pi.add_argument('src', help='待入库 PDF 所在目录')
    pi.add_argument('--source', default='邮箱', help='CSV 邮箱列的来源标注')
    pi.add_argument('--note', default='', help='CSV 主题列备注')
    sub.add_parser('renumber')
    sub.add_parser('audit')
    args = ap.parse_args()
    if args.cmd in ('ingest', 'audit') and not (args.buyer_name and args.buyer_tax):
        sys.exit('必须提供抬头与税号：--buyer-name/--buyer-tax 或环境变量 INVOICE_BUYER/INVOICE_TAX')
    {'ingest': cmd_ingest, 'renumber': cmd_renumber, 'audit': cmd_audit}[args.cmd](args)


if __name__ == '__main__':
    main()
