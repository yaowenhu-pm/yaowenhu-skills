#!/usr/bin/env python3
"""把 get_page_text 抓到的主页文本解析成一行 CSV，append 到 results.csv。

用法:
    python3 parse_stats.py --url <主页URL> [--raw <原始链接>] [--seq <序号>] \
        [--out results.csv] < pagetext.txt

平台自动识别（文本含"抖音号："/"小红书号："）。解析失败/命中登录页也会落一行，
状态列标明原因，方便断点重跑。纯标准库。
"""
import argparse
import csv
import datetime
import os
import re
import sys

HEADER = ["序号", "平台", "昵称", "账号ID", "粉丝数", "获赞数", "关注数",
          "作品/笔记数", "IP属地", "简介", "粉丝数原文", "获赞数原文",
          "主页URL", "原始链接", "采集时间", "状态"]

NUM_RE = re.compile(r'^\d+(?:\.\d+)?(?:万|亿)?$')


def to_int(s: str):
    """'8.3万' -> 83000, '4303' -> 4303。非数字返回空串。"""
    s = s.strip()
    m = re.match(r'^(\d+(?:\.\d+)?)(万|亿)?$', s)
    if not m:
        return ""
    n = float(m.group(1))
    n *= {"万": 10000, "亿": 100000000, None: 1}[m.group(2)]
    return int(round(n))


def grab(lines, label, direction):
    """direction='after': 标签行的下一行是数字(抖音)；'before': 上一行是数字(小红书)。"""
    for i, ln in enumerate(lines):
        if ln == label:
            j = i + 1 if direction == "after" else i - 1
            if 0 <= j < len(lines) and NUM_RE.match(lines[j]):
                return lines[j]
    return ""


def parse_douyin(lines):
    d = {"平台": "抖音"}
    d["粉丝数原文"] = grab(lines, "粉丝", "after")
    d["获赞数原文"] = grab(lines, "获赞", "after")
    d["关注数"] = to_int(grab(lines, "关注", "after"))
    # 昵称 = 统计块（“关注”且下一行是数字）的上一行；跳过导航栏里的“关注”
    for i, ln in enumerate(lines):
        if (ln == "关注" and 0 < i < len(lines) - 1
                and NUM_RE.match(lines[i + 1]) and lines[i - 1]):
            d["昵称"] = lines[i - 1]
            break
    # 作品数 = 第一处“作品”行的下一行数字
    d["作品/笔记数"] = to_int(grab(lines, "作品", "after"))
    bio = []
    for i, ln in enumerate(lines):
        m = re.match(r'^抖音号[:：]\s*(.+)$', ln)
        if m:
            d["账号ID"] = m.group(1).strip()
            for x in lines[i + 1:]:
                if x in ("分享主页", "关注", "私信"):
                    break
                mm = re.match(r'^IP属地[:：]\s*(.+)$', x)
                if mm:
                    d["IP属地"] = mm.group(1).strip()
                elif re.match(r'^\d+岁$', x) or x in ("男", "女"):
                    pass
                elif re.match(r'^[一-龥]{2,8}·[一-龥]{2,8}$', x) and "IP属地" not in d:
                    d["IP属地"] = x
                elif x:
                    bio.append(x)
            break
    d["简介"] = " ".join(bio)
    return d


def parse_xhs(lines):
    d = {"平台": "小红书"}
    d["粉丝数原文"] = grab(lines, "粉丝", "before")
    d["获赞数原文"] = grab(lines, "获赞与收藏", "before")
    d["关注数"] = to_int(grab(lines, "关注", "before"))
    d["作品/笔记数"] = ""  # 网页版主页不展示笔记总数
    bio = []
    for i, ln in enumerate(lines):
        m = re.match(r'^小红书号[:：]\s*(.+)$', ln)
        if m:
            d["账号ID"] = m.group(1).strip()
            if i > 0:
                d["昵称"] = lines[i - 1]
            for x in lines[i + 1:]:
                if NUM_RE.match(x) or x == "关注":
                    break
                mm = re.match(r'^IP属地[:：]\s*(.+)$', x)
                if mm:
                    d["IP属地"] = mm.group(1).strip()
                elif x:
                    bio.append(x)
            break
    d["简介"] = " ".join(bio)
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--raw", default="")
    ap.add_argument("--seq", default="")
    ap.add_argument("--out", default="results.csv")
    args = ap.parse_args()

    text = sys.stdin.read()
    lines = [ln.strip() for ln in text.splitlines()]

    if re.search(r'(扫码登录|登录后推荐更懂你的笔记|手机号登录)', text) and "小红书号" not in text and "抖音号" not in text:
        row = {"平台": "", "状态": "需登录/被风控跳转"}
    elif "抖音号" in text:
        row = parse_douyin(lines)
    elif "小红书号" in text:
        row = parse_xhs(lines)
    else:
        row = {"平台": "", "状态": "解析失败:未识别平台"}

    row.setdefault("状态", "ok" if row.get("粉丝数原文") else "解析失败:无粉丝数")
    row["粉丝数"] = to_int(row.get("粉丝数原文", ""))
    row["获赞数"] = to_int(row.get("获赞数原文", ""))
    row["主页URL"] = args.url
    row["原始链接"] = args.raw
    row["序号"] = args.seq
    row["采集时间"] = datetime.date.today().isoformat()

    new = not os.path.exists(args.out)
    with open(args.out, "a", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=HEADER)
        if new:
            w.writeheader()
        w.writerow({k: row.get(k, "") for k in HEADER})
    print(f"[{row['状态']}] {row.get('平台','')} {row.get('昵称','')} 粉丝={row.get('粉丝数','')} -> {args.out}")


if __name__ == "__main__":
    main()
