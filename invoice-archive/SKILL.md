---
name: invoice-archive
description: 邮箱发票全量归集与报销整理。当用户说"下载/整理/归集邮箱里的发票""发票入库""收发票""发票去重""核对发票抬头/税号""发票编号""发票汇总表""报销发票整理""查一下这张发票真伪"，或提到邮件里有发票要处理时使用。覆盖飞书邮箱（含公共邮箱）的 PDF 附件、.eml 转发套娃、正文下载链接（京东/淘宝/税务局/百望/同程/转转）、图片版发票四类形态；产出统一命名+序号的发票库和带总金额的汇总 CSV，自动去重、核验抬头税号、解二维码验真。
---

# invoice-archive · 邮箱发票全量归集

把邮箱里所有和发票有关的东西变成一个干净的报销文件夹：
`发票/` 下平铺 `序号_开票日期_销售方_金额元.pdf` + 一份 `发票汇总.csv`（末行总金额）。

**铁律：邮件只要提到发票，无论什么形态都必须拿下来。** 只收 PDF 附件会漏掉大头
（一次实测：收集器只拿到 38 张，按本流程补完是 83 张 / 18.5 万元）。

## 前置条件

1. 已安装并授权 **feishu skill**（个人邮箱 OAuth，`FEISHU_PROFILE=mail`；公共邮箱如
   `pay@company.com` 用 `--mailbox` 指定，需有访问权）。
2. `pip3 install pypdf`；macOS（audit 解二维码用系统 swift + CoreImage）。
3. 向用户确认两件事：**报销抬头全名 + 统一社会信用代码**（下文 `$BUYER` / `$TAX`，
   注意公司名里的括号用全角），以及涉及哪几个邮箱。

## 标准流程（五步）

### 第 1 步 · 收集器扫附件（覆盖形态①：PDF 附件）

```bash
cd <feishu-skill目录>
python3 scripts/feishu.py invoice-collect --root ~/Desktop/发票/.collector --limit 500
python3 scripts/feishu.py invoice-collect --root ~/Desktop/发票/.collector --limit 500 --mailbox pay@company.com
```

- `.collector/` 是**机器去重台账**（隐藏目录）：`发票汇总.csv` 里的来源ID/SHA256
  保证已处理的邮件永不重复下载。**不要动、不要删这个目录**；人类可读的汇总表是
  发票库根目录那份，两者字段不同，别混用。
- 新下载的文件落在 `.collector/YYYY/MM/` 里，待第 3 步入库。

### 第 2 步 · 扫盲区（形态②③④：eml 套娃 / 正文链接 / 图片票）

```bash
cd <本skill目录>/scripts
FEISHU_PROFILE=mail python3 extract_eml_invoices.py --mailbox me --out /tmp/eml_extract
```

它会：拆 `.eml` 附件里的内层 PDF；对**可信直链**（京东 jdcloud-oss、税务局
chinatax.gov.cn、淘宝 einvoice.taobao.com、转转 zhuanstatic.com）直接下载；
其余发票链接打印出来人工处理。已知的两家 JS 页面套路：

| 平台 | 邮件里的链接 | 真实下载端点 |
|---|---|---|
| 百望云 | `pis.baiwang.com/smkp-vue/previewInvoiceAllEle?param=…` | 同域 `/bwmg/mix/bw/downloadFormat?param=<param>&formatType=PDF`，param 是 128 位 hex，**不完整会报 AES 长度错** |
| 同程云票汇 | `finance.17u.cn/invoicecloud/d/<短码>` | 跳转后同域 `/invoicecloud/gateway/invoice/batchDownLoadFiles/<token>`，返回 zip |

没见过的 JS 页面：用浏览器打开 → 从 performance 资源列表 / `<a>` 标签里挖真实端点
→ curl。用浏览器自动化时**必须显式传 tab_id**（默认操作的是用户当前活跃标签页），
用完关掉自己开的标签页。

### 第 3 步 · 入库（解析、去重、核抬头、重命名）

```bash
export INVOICE_BUYER='某某（北京）科技有限责任公司'   # 换成实际报销抬头（注意全角括号）
export INVOICE_TAX='91110000XXXXXXXXXX'              # 换成实际统一社会信用代码
python3 invoice_butler.py ingest /tmp/eml_extract --source '本人邮箱(eml拆出)'
python3 invoice_butler.py ingest ~/Desktop/发票/.collector/2026 --source '本人邮箱'  # 收集器新下的
```

ingest 做的事：SHA256 + 发票号码双重查重 → 解析开票日期/销售方/价税合计 →
核对抬头税号（不符的文件名加 `_抬头待核`）→ 命名 `日期_销售方_金额元.pdf` 复制进库
→ 追加汇总 CSV。文本层解析失败的（图片版发票）自动改走二维码取要素。

### 第 4 步 · 编号

```bash
python3 invoice_butler.py renumber
```

按开票日期排序加两位序号前缀（文件多于 99 张自动加宽），CSV 序号列同步、重算总金额。
**每次 ingest 之后都要 renumber**。

### 第 5 步 · 终审

```bash
python3 invoice_butler.py audit
```

零差异才算完：文件↔CSV 一一对应、票面金额=文件名=CSV 三方一致、总金额三种算法互验、
抬头税号全对、发票号码全库唯一（图片票自动解二维码核验）。有问题逐条列出。

## 惯例与坑（实战沉淀，别重踩）

- **发票号码一票一号**。若几张票票面印同一号码，先别下结论——解左上角二维码
  （QR 是查验系统扫的权威数据，格式 `01,32, ,号码,金额,日期, ,校验位`）。
  实测过一批四张票面同号，QR 解出是连号四张真票，开票平台把号码贴图盖错了。
- **红冲票**（负数金额/含"被红冲"）：红字发票和被冲销的蓝票都不能报销。默认删除，
  但 CSV 行要保留、状态标"红冲已删除"（删行会让台账去重失效导致重新下载）。
- **重复票**只留一份 PDF；同一张票的 xml/ofd 副本不留。
- **同日同商家同金额会撞名**：`Path.rename`/复制会静默覆盖，必须先查重加尾号
  （invoice_butler 已内置，自写脚本时小心）。
- **别用显示截断的 URL**：淘宝/百望的 token 很长，回邮件原始 HTML 取完整链接。
- 淘宝打包下载是 zip 且**文件名 GBK 编码**（`filename.encode('cp437').decode('gbk')`）。
- 图片版发票 pypdf 抽 images 往往抽到二维码而非票面；看票面用
  `qlmanage -t -s 1400 -o <dir> <pdf>` 渲整页再看图。
- "开票申请处理成功"类通知（附件是扫码小票照片）不是发票，对应 PDF 会另行发来。
- 报销单/合并发票/zip 合集一律**拆散成单张**入库，外壳删掉。
- 收尾时向用户报告：新增几张、去重几张、跳过几张（及原因）、总金额，
  以及需要人工留意的票（抬头待核、票面异常、待浏览器处理的链接）。
