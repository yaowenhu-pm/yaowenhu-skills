#!/usr/bin/env python3
"""链接归一化：混合的抖音/小红书链接(短链+PC链接) -> normalized.csv

用法:
    python3 normalize.py input_links.txt
输入: 任意文本，每行或行内包含链接均可（自动正则抽取 URL）
输出: normalized.csv  列: 序号,平台,原始链接,主页URL,备注
"""
import csv
import re
import sys
import time
import urllib.request

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

URL_RE = re.compile(r'https?://[^\s"\'<>，。;；)）\]】]+')


def resolve_redirect(url: str) -> str:
    """跟随重定向拿最终 URL（短链解析不需要签名）。"""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.geturl()
    except Exception as e:
        # 部分链接跟到最后一跳会 4xx，但重定向历史里已有目标；退而求其次手动跟 Location
        try:
            import http.client
            from urllib.parse import urlparse
            cur = url
            for _ in range(8):
                p = urlparse(cur)
                conn = (http.client.HTTPSConnection if p.scheme == "https"
                        else http.client.HTTPConnection)(p.netloc, timeout=15)
                conn.request("GET", p.path + ("?" + p.query if p.query else ""),
                             headers={"User-Agent": UA})
                r = conn.getresponse()
                loc = r.getheader("Location")
                conn.close()
                if r.status in (301, 302, 303, 307, 308) and loc:
                    cur = loc if loc.startswith("http") else f"{p.scheme}://{p.netloc}{loc}"
                    continue
                return cur
            return cur
        except Exception:
            return f"ERROR: {e}"


def canonicalize(url: str):
    """返回 (平台, 主页URL, 备注)。"""
    # 抖音 sec_uid
    m = re.search(r'(?:douyin\.com/user/|share/user/)(MS4w[\w\-=]+)', url)
    if m:
        return ("抖音", f"https://www.douyin.com/user/{m.group(1)}", "")
    # 小红书 user id（保留 xsec_token，无 token 的主页部分场景打不开）
    m = re.search(r'xiaohongshu\.com/user/profile/([0-9a-f]{24})(\?[^#]*)?', url)
    if m:
        token = ""
        if m.group(2) and "xsec_token" in m.group(2):
            tm = re.search(r'xsec_token=([^&]+)', m.group(2))
            if tm:
                token = f"?xsec_token={tm.group(1)}&xsec_source=pc_search"
        return ("小红书", f"https://www.xiaohongshu.com/user/profile/{m.group(1)}{token}", "")
    return ("未知", url, "无法识别的主页格式")


def main(path: str):
    text = open(path, encoding="utf-8").read()
    raw_urls = URL_RE.findall(text)
    print(f"抽取到 {len(raw_urls)} 条 URL")

    rows, seen = [], set()
    for i, raw in enumerate(raw_urls, 1):
        url, note = raw, ""
        if re.search(r'(v\.douyin\.com|xhslink\.com|iesdouyin\.com/share)', raw):
            url = resolve_redirect(raw)
            time.sleep(0.5)
            if url.startswith("ERROR"):
                rows.append(("未知", raw, "", f"短链解析失败 {url}"))
                print(f"[{i}/{len(raw_urls)}] 解析失败: {raw}")
                continue
        platform, home, note = canonicalize(url)
        key = home.split("?")[0]
        if key in seen:
            continue
        seen.add(key)
        rows.append((platform, raw, home, note))
        print(f"[{i}/{len(raw_urls)}] {platform} {home[:80]}")

    with open("normalized.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["序号", "平台", "原始链接", "主页URL", "备注"])
        for n, (p, raw, home, note) in enumerate(rows, 1):
            w.writerow([n, p, raw, home, note])

    from collections import Counter
    print("\n== 汇总 ==", dict(Counter(r[0] for r in rows)))
    print(f"去重后共 {len(rows)} 条 -> normalized.csv")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "input_links.txt")
