#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""飞书"整篇一张大表"调研文档引擎（research-doc skill）

用法：
  1. 用 feishu.py create 新建云文档，把 token 填到 DOCID
  2. 按需修改 ROWS / SUMMARY / OUTLINE_TEXT / CHART_DIR / ATTACH
  3. python3 feishu_bigtable.py   （清空文档并整体重建）

内容标记语法（rich_lines 引擎解析）：
  **加粗**            关键数字/结论词（状态跨行延续，不会残留星号）
  [文字](url)         真实可点链接
  ⟨CHART⟩图.png|图注   该格=图注文字+嵌入图表（PNG 放 CHART_DIR）
  ⟨FILES⟩说明文字      该格=文字+ATTACH 里的全部文件附件
  自动断行：句号/分号后；序号①②③前；冒号后接多点列举时；括号内不断行

⚠️ 协作约定：用户在飞书手动改过此文档后，禁止再整体重建（会覆盖用户改动），
   只做增量修改（PATCH 单块 / POST 单元格 children / replace_file）。

坑位说明见 SKILL.md 第六节，本脚本已全部内置处理，改动时勿退步。
"""
import sys, os, re, time, requests
sys.path.insert(0, os.path.expanduser('~/.claude/skills/feishu'))
import scripts.feishu as F

# ==================== 按项目修改区 ====================
DOCID = '在此填入文档token'
CHART_DIR = os.path.expanduser('~/your-project/charts')   # 图表PNG目录
CHART = '⟨CHART⟩'
FILES = '⟨FILES⟩'

ATTACH = [  # (本地路径, 展示文件名) —— 数据文件附件，嵌入含 ⟨FILES⟩ 标记的单元格
    # (os.path.expanduser('~/your-project/data.csv'), '数据_全部N条.csv'),
]

SUMMARY = (
 '一句话说清研究对象是什么、样本多大。\n'
 '核心命题：**一句话命题（注意"原因之一"式留余地表述）。**\n'
 '三个发现：发现一（带**关键数字**）；发现二；发现三。\n'
 '对业务：启发一；启发二；启发三。\n**数据截止：YYYY-MM-DD（采集当日快照）。**')

OUTLINE_TEXT = (
 '核心命题——一句话（此行避免使用冒号分号句号，防止被拆行）\n'
 '　• 引言（研究逻辑 · 样本与数据）\n'
 '　• H1 假设一〔强〕\n'
 '　　- 关键数据点\n'
 '　• H2 假设二〔强〕\n'
 '　• H3 假设三〔中偏弱〕\n'
 '　• 结论与产品启发\n'
 '　• 研究边界与不严谨处\n'
 '　• 附录与参考资料')

ROWS = [
 ('类型', '事项', '说明'),
 ('摘要', '核心结论', SUMMARY),
 ('目录', '结构一览', OUTLINE_TEXT),
 ('引言', '研究逻辑', '先立假设，再用数据逐一证实或证伪。'),
 ('引言', '数据来源', '来源与方式。**采集时间：YYYY-MM-DD。**所有数字为采集时刻快照。'),
 ('引言', '三类内容区分', '严格区分：①**实测数据**（可复核）；②**机械统计**（规则公开）；③**解读与假设**（主观判断，显式标注）。'),
 # ('H1〔强〕\n短语一\n短语二', '假设', '……'),
 # ('H1〔强〕\n短语一\n短语二', '数据论证〔图〕', CHART + 'h1.png|图注，含**关键数字**。'),
 # ('H1〔强〕\n短语一\n短语二', '小结', '**成立（强佐证）。**……'),
 # ('参考资料', '研究对象', '[对象名](https://真实链接)（补充说明）。'),
 # ('附录', '数据文件', FILES + '数据文件见下方附件（可直接下载）：文件一说明；文件二说明。'),
]

COL_WIDTHS = [110, 185, 470]
# ======================================================


# ---------- 富文本引擎（勿轻易改动，规则见 SKILL.md） ----------
def rich_lines(content):
    """解析 **加粗**(跨行延续) 与 [文字](url)，按规则切行。
    切行：\n；句号/分号后；序号①②③前；冒号后接多点列举(同段含分号)时；括号内不切。"""
    import urllib.parse
    LINK_RE = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')
    tokens, pos = [], 0
    for m in LINK_RE.finditer(content):
        if m.start() > pos:
            tokens.append(('t', content[pos:m.start()]))
        tokens.append(('l', m.group(1), m.group(2)))
        pos = m.end()
    if pos < len(content):
        tokens.append(('t', content[pos:]))

    lines, cur, buf, bold = [], [], '', False

    def flush_buf():
        nonlocal buf
        if buf:
            el = {'text_run': {'content': buf}}
            if bold:
                el['text_run']['text_element_style'] = {'bold': True}
            cur.append(el)
            buf = ''

    def flush_line():
        nonlocal cur
        if cur and ''.join(e['text_run']['content'] for e in cur).strip():
            lines.append(cur)
        cur = []

    CIRCLED = '①②③④⑤⑥⑦⑧⑨⑩'
    depth = 0  # 括号深度：括号内不拆行
    for tok in tokens:
        if tok[0] == 'l':
            flush_buf()
            cur.append({'text_run': {'content': tok[1],
                'text_element_style': {'link': {'url': urllib.parse.quote(tok[2], safe='')}}}})
            continue
        seg, i = tok[1], 0
        while i < len(seg):
            if seg.startswith('**', i):
                flush_buf(); bold = not bold; i += 2; continue
            ch = seg[i]
            if ch in '（(':
                depth += 1
            elif ch in '）)':
                depth = max(0, depth - 1)
            if ch == '\n':
                flush_buf(); flush_line(); i += 1; continue
            if depth == 0 and ch in CIRCLED and (buf.strip() or cur):
                flush_buf(); flush_line()
            buf += ch
            if depth == 0 and ch in '。；':
                flush_buf(); flush_line()
            elif depth == 0 and ch == '：':
                rest = seg[i+1:]
                nl = rest.find('\n')
                scope = rest[:nl] if nl >= 0 else rest
                if '；' in scope:
                    flush_buf(); flush_line()
            i += 1
    flush_buf(); flush_line()
    return lines


def text_blocks(prefix, content, align=None):
    defs, ids = [], []
    lines = rich_lines(content) or [[{'text_run': {'content': ' '}}]]  # 空格兜底：cell的children不能为空
    for j, els in enumerate(lines):
        bid = f'{prefix}_{j}'
        blk = {'block_id': bid, 'block_type': 2, 'text': {'elements': els}}
        if align:
            blk['text']['style'] = {'align': align}
        defs.append(blk); ids.append(bid)
    return defs, ids


# ---------- 构建流程 ----------
def clear():
    ch = F._top_children(DOCID)
    if ch:
        requests.delete(f'{F.BASE}/docx/v1/documents/{DOCID}/blocks/{DOCID}/children/batch_delete',
                        headers=F._h(), json={'start_index': 0, 'end_index': len(ch)}, timeout=30)
    print('清空完成')


def build():
    R, C = len(ROWS), 3
    cells = [f'c{i}' for i in range(R*C)]
    desc = [{'block_id': 'T', 'block_type': 31,
             'table': {'property': {'row_size': R, 'column_size': C, 'header_row': True}},
             'children': cells}]
    chart_order = []
    for r, row in enumerate(ROWS):
        for c, val in enumerate(row):
            cid = cells[r*C + c]
            if c == 0:
                first = (r == 0) or (ROWS[r][0] != ROWS[r-1][0])
                kdefs, kids = text_blocks(f'k{r}_{c}', (val if first else '') or ' ', align=1)
            elif isinstance(val, str) and val.startswith(CHART):
                name, cap = val[len(CHART):].split('|', 1)
                kdefs, kids = text_blocks(f'k{r}_{c}', cap)
                kdefs.append({'block_id': f'img{r}', 'block_type': 27, 'image': {}})
                kids.append(f'img{r}')
                chart_order.append(name)
            elif isinstance(val, str) and val.startswith(FILES):
                kdefs, kids = text_blocks(f'k{r}_{c}', val[len(FILES):])
            else:
                kdefs, kids = text_blocks(f'k{r}_{c}', val)
            desc.append({'block_id': cid, 'block_type': 32, 'table_cell': {}, 'children': kids})
            desc += kdefs
    payload = {'index': -1, 'children_id': ['T'], 'descendants': desc}
    r = requests.post(f'{F.BASE}/docx/v1/documents/{DOCID}/blocks/{DOCID}/descendant',
                      headers=F._h(), json=payload, timeout=120).json()
    print('建表 code=', r.get('code'), r.get('msg'), '| 总块数≈', len(desc))
    return (r.get('code') == 0), chart_order


def fill_charts(chart_order):
    time.sleep(1)
    _, blocks = F._all_blocks(DOCID)
    empties = [b['block_id'] for b in blocks
               if b.get('block_type') == 27 and not b.get('image', {}).get('token')]
    for bid, name in zip(empties, chart_order):
        path = os.path.join(CHART_DIR, name)
        with open(path, 'rb') as f:
            up = requests.post(f'{F.BASE}/drive/v1/medias/upload_all',
                headers={'Authorization': f'Bearer {F._token()}'},
                data={'file_name': name, 'parent_type': 'docx_image',
                      'parent_node': bid, 'size': str(os.path.getsize(path))},
                files={'file': (name, f)}, timeout=120).json()
        pr = requests.patch(f'{F.BASE}/docx/v1/documents/{DOCID}/blocks/{bid}',
                            headers=F._h(), json={'replace_image': {'token': up['data']['file_token']}},
                            timeout=30).json()
        print(f'  图 {name} -> {"✓" if pr.get("code")==0 else pr}')


def attach_files():
    if not ATTACH:
        return
    _, blocks = F._all_blocks(DOCID)
    tbl = [b for b in blocks if b.get('block_type') == 31][0]
    cells = tbl['table']['cells']; C = 3
    row = next(i for i, r in enumerate(ROWS) if isinstance(r[2], str) and r[2].startswith(FILES))
    cell = cells[row*C + 2]
    # 两阶段：先建完所有空文件块 → sleep+重新GET全量块（否则replace_file报1770025）→ 再回填
    for _ in ATTACH:
        requests.post(f'{F.BASE}/docx/v1/documents/{DOCID}/blocks/{cell}/children',
                      headers=F._h(), json={'children': [{'block_type': 23, 'file': {}}], 'index': -1},
                      timeout=30).json()
    time.sleep(4)
    _, blocks_now = F._all_blocks(DOCID)
    fids = [b['block_id'] for b in blocks_now
            if b.get('block_type') == 23 and not b.get('file', {}).get('token')]
    for fid, (path, showname) in zip(fids, ATTACH):
        with open(path, 'rb') as f:
            up = requests.post(f'{F.BASE}/drive/v1/medias/upload_all',
                headers={'Authorization': f'Bearer {F._token()}'},
                data={'file_name': showname, 'parent_type': 'docx_file',
                      'parent_node': fid, 'size': str(os.path.getsize(path))},
                files={'file': (showname, f)}, timeout=120).json()
        pr = requests.patch(f'{F.BASE}/docx/v1/documents/{DOCID}/blocks/{fid}',
                            headers=F._h(), params={'document_revision_id': -1},
                            json={'replace_file': {'token': up['data']['file_token']}}, timeout=30).json()
        print(f'  附件 {showname} -> {"✓" if pr.get("code")==0 else pr.get("code")}')


def merge_and_widths():
    _, blocks = F._all_blocks(DOCID)
    tbl = [b for b in blocks if b.get('block_type') == 31][0]
    tid = tbl['block_id']
    groups, start = [], 1
    for i in range(2, len(ROWS)):
        if ROWS[i][0] != ROWS[i-1][0]:
            groups.append((start, i)); start = i
    groups.append((start, len(ROWS)))
    for s, e in groups:
        if e - s > 1:
            requests.patch(f'{F.BASE}/docx/v1/documents/{DOCID}/blocks/{tid}', headers=F._h(),
                params={'document_revision_id': -1},
                json={'merge_table_cells': {'row_start_index': s, 'row_end_index': e,
                                            'column_start_index': 0, 'column_end_index': 1}}, timeout=30)
    for idx, w in enumerate(COL_WIDTHS):
        requests.patch(f'{F.BASE}/docx/v1/documents/{DOCID}/blocks/{tid}', headers=F._h(),
            params={'document_revision_id': -1},
            json={'update_table_property': {'column_index': idx, 'column_width': w}}, timeout=30)
    print(f'合并 {sum(1 for s,e in groups if e-s>1)} 组 + 列宽已设')
    # 合并会重置对齐：合并后重新补左对齐（带重试与节流防频控）
    time.sleep(1)
    _, blocks2 = F._all_blocks(DOCID)
    tbl2 = [b for b in blocks2 if b.get('block_type') == 31][0]
    cells2 = tbl2['table']['cells']; C = 3
    col0 = {cells2[r*C + 0] for r in range(len(ROWS))}
    n = 0
    for b in blocks2:
        if b.get('block_type') == 2 and b.get('parent_id') in col0:
            for _ in range(3):
                try:
                    rr = requests.patch(f'{F.BASE}/docx/v1/documents/{DOCID}/blocks/{b["block_id"]}',
                        headers=F._h(), params={'document_revision_id': -1},
                        json={'update_text_style': {'style': {'align': 1}, 'fields': [1]}}, timeout=30).json()
                except Exception:
                    time.sleep(1.5); continue
                if rr.get('code') == 0:
                    n += 1; break
                time.sleep(1)
            time.sleep(0.15)
    print(f'合并后补左对齐 {n} 个文字块')


def verify():
    _, blocks = F._all_blocks(DOCID)
    tbl = [b for b in blocks if b.get('block_type') == 31][0]
    star = sum(1 for b in blocks if b.get('block_type') == 2 and
               '**' in ''.join(e.get('text_run', {}).get('content', '') for e in b.get('text', {}).get('elements', [])))
    imgs = sum(1 for b in blocks if b.get('block_type') == 27 and b['image'].get('token'))
    files = sum(1 for b in blocks if b.get('block_type') == 23 and b['file'].get('token'))
    print(f'自检：{tbl["table"]["property"]["row_size"]}行 | **残留:{star} | 图:{imgs} | 附件:{files}')


if __name__ == '__main__':
    clear()
    ok, chart_order = build()
    if ok:
        fill_charts(chart_order)
        attach_files()
        merge_and_widths()
        verify()
