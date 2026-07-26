<div align="center">

# 🧰 yaowenhu-skills

#### 我自己每天在用的 Agent Skills，跑顺了才放出来

[![License](https://img.shields.io/badge/License-MIT-3B82F6?style=for-the-badge)](./LICENSE)
[![Skills](https://img.shields.io/badge/Skills-6-10B981?style=for-the-badge)](#-skills)
[![AgentSkills](https://img.shields.io/badge/AgentSkills-Standard-8B5CF6?style=for-the-badge)](https://agentskills.io)

![Claude Code](https://img.shields.io/badge/Claude_Code-Skill-D97706?style=flat-square&logo=anthropic&logoColor=white)
![Codex](https://img.shields.io/badge/Codex-Skill-10B981?style=flat-square&logo=openai&logoColor=white)

</div>

每个 Skill 都是一个包含 `SKILL.md` 的目录，遵循 [Agent Skills](https://agentskills.io) 开放标准，Claude Code、Codex 等兼容 Agent 会根据 `description` 字段自动加载触发。这里的东西都在我自己的日常工作里跑过一段时间，坑基本踩完了才沉淀成 Skill。

---

## 📋 目录

| 名字 | 一句话 |
|---|---|
| ✍️ [**elegant-docs**](#%EF%B8%8F-elegant-docs优雅文档) | 写文档、评文档、润色草稿时默认短、结论前置、结构可扫。纯提示词，零依赖 |
| 📐 [**table-docs**](#-table-docs三列表格文档) | 把任何条目型文档装进"类型 \| 事项 \| 说明"三列大表，只搬结构不改一个字 |
| 🔬 [**research-doc**](#-research-doc调研报告) | 先立假设再用数据打靶的调研报告方法论 + 飞书"一张大表"生产引擎 |
| 📄 [**prd-doc**](#-prd-doc-prd-撰写) | PRD 撰写纪律：数值可实现、指标↔埋点对账、待定项闭环、评审回填 |
| 🧾 [**invoice-archive**](#-invoice-archive邮箱发票归集) | 把邮箱里所有形态的发票（附件/eml 套娃/正文链接/图片票）归集成一个干净的报销文件夹 |
| 📊 [**creator-stats**](#-creator-stats创作者数据录入) | 抖音/小红书创作者主页公开数据批量录入 CSV，驱动你自己登录态的 Chrome，不写爬虫 |

其中四个文档类 Skill 是一条血统链：`elegant-docs`（写作基线）→ `table-docs`（三列表格结构）→ `research-doc`（调研方法论 + 飞书大表引擎）→ `prd-doc`（继承前两者，只补 PRD 特有部分）。

---

## 📦 安装方式

Skill 本质是一个目录，放进 Agent 的 skills 路径即可，无需安装命令。也可以直接跟你的 Agent 说：

```
帮我安装这个 skill：https://github.com/yaowenhu-pm/yaowenhu-skills/tree/main/<skill-name>
```

手动安装（软链方式，仓库 `git pull` 即完成升级）：

```bash
git clone https://github.com/yaowenhu-pm/yaowenhu-skills.git ~/yaowenhu-skills

# Claude Code
mkdir -p ~/.claude/skills
for s in elegant-docs table-docs research-doc prd-doc invoice-archive creator-stats; do
  ln -s ~/yaowenhu-skills/$s ~/.claude/skills/$s
done

# Codex 同理，路径换成 ~/.codex/skills
```

装完新开会话即生效。你的 Agent 不支持 Skill 也没关系：把对应目录的 `SKILL.md` 全文当成项目规则文件（或直接贴进对话）让 Agent 照着执行，效果一致。

---

## ✨ Skills

<table>
<tr><td>

### ✍️ elegant-docs（优雅文档）

让 Agent 写文档、评估文档、润色草稿时默认遵守一套硬约束：短、结论前置、结构可扫、去术语。纯提示词 Skill，零依赖，装上就能用。

**怎么触发**

```
帮我润色一下这篇文档
写一份 README / 方案 / 报告
看看这篇文档有什么问题
```

→ [SKILL.md](./elegant-docs/SKILL.md)

</td></tr>
</table>

<table>
<tr><td>

### 📐 table-docs（三列表格文档）

入职指南、操作清单、配置说明、FAQ 这类条目型文档，正文主体固定用"类型 | 事项 | 说明"三列大表，不用章节 + 段落的传统结构。

核心纪律是**只转换结构，不改写文字**：原文的每一句话、每个数字、每个链接都能在表格里找到对应位置。需要润色是 elegant-docs 的事，两步分开。对原文里已有的表格也有一套不拆、不脑补的处理规则。

**怎么触发**

```
按我的表格格式来
像入职指南那样整理成表格
整理成 类型|事项|说明 三列
```

→ [SKILL.md](./table-docs/SKILL.md)

</td></tr>
</table>

<table>
<tr><td>

### 🔬 research-doc（调研报告）

账号拆解、竞品研究、数据分析这类"用数据回答问题"的调研报告。核心主张：**先立假设，再用数据打靶**——不罗列发现，让每个数字都在回答一个明确的问题。

三块东西都在里面：

- **立论与论证纪律**：九条硬规则，每条都来自一次真实翻车（理论标签贴错、n=1 写成结论、归一化口径驱动结论、时间混杂变量……），交付前内置对抗性审查
- **写作红线**：结论不说满、判断带客观依据、引用可溯源、区分实测/统计/解读三类内容
- **飞书大表引擎**（`scripts/feishu_bigtable.py`）：整篇一张"类型｜事项｜说明"大表，图表和数据文件嵌进单元格，文档自包含可复跑；飞书 descendant 接口的十几个坑全部内置

**怎么触发**

```
做一份调研 / 研究报告
写成飞书大表那种格式
把这些分析结论整理成先立假设再论证的文档
```

→ [SKILL.md](./research-doc/SKILL.md)

</td></tr>
</table>

<table>
<tr><td>

### 📄 prd-doc（PRD 撰写）

PRD / 需求文档 / 数值体系规格的撰写与评审闭环。文档结构继承 table-docs，生产管线继承 research-doc，本 Skill 只补 PRD 特有的纪律：

- **数值必须可实现**：给公式 + 逐级数表，禁止"适当增加""视情况而定"
- **每个参数三件套**：默认值｜是否进远程配置｜生效层级
- **指标 ↔ 埋点对账**：每个指标指得到埋点事件，每个事件答得出"谁用它做什么决策"
- **待定项闭环**：行内 🔵 标记 + "待拍板项"集中汇总，拍板后回填不留悬空
- **评审后升版本、记修订、保留修正痕迹**，用户手改过的文档只做增量修改

**怎么触发**

```
写个 PRD / 出需求文档
按需求逻辑详述那个格式来
评审结论回填一下，升个版本
```

→ [SKILL.md](./prd-doc/SKILL.md)

</td></tr>
</table>

<table>
<tr><td>

### 🧾 invoice-archive（邮箱发票归集）

把邮箱里所有和发票有关的东西变成一个干净的报销文件夹：`序号_开票日期_销售方_金额元.pdf` 平铺 + 一份带总金额的汇总 CSV。

**铁律：邮件只要提到发票，无论什么形态都必须拿下来。** 只收 PDF 附件会漏掉大头（一次实测：只扫附件拿到 38 张，按本流程补完是 83 张）。覆盖四类形态：

- PDF 附件（收集器全量扫描 + SHA256/发票号码双重去重台账）
- `.eml` 转发套娃里的内层 PDF
- 正文下载链接（京东/税务局/淘宝直链自动下；百望云、同程云票汇这类 JS 页面给出真实下载端点）
- 图片版发票（解左上角二维码取要素并验真）

入库后自动核对抬头税号、按日期编号，终审做文件↔CSV↔票面三方对账，零差异才算完。

**怎么触发**

```
把邮箱里的发票都下载整理一下
发票入库 / 发票去重 / 出一份发票汇总表
查一下这张发票真伪
```

→ [SKILL.md](./invoice-archive/SKILL.md)

</td></tr>
</table>

<table>
<tr><td>

### 📊 creator-stats（创作者数据录入）

抖音/小红书创作者主页大盘数据批量录入 CSV：昵称、账号 ID、粉丝数、获赞数、关注数、作品数、IP 属地、简介。

驱动你本机已登录的真实 Chrome 逐页访问主页、纯文本解析公开数据——不写爬虫、不破解签名、不绕验证码。增量落盘，支持断点续跑，适合几十到几百个账号的一次性录入。

**怎么触发**

```
帮我把这批抖音/小红书主页的粉丝数整理成表格
这些达人的数据录入 CSV
```

→ [SKILL.md](./creator-stats/SKILL.md)

</td></tr>
</table>

---

## 前置要求

| Skill | 依赖 |
|---|---|
| elegant-docs / table-docs / prd-doc | 无（纯提示词） |
| research-doc | 图表用 Python + matplotlib；产出飞书文档需自备飞书开放平台应用授权（引擎脚本依赖一个提供 token 的 `feishu.py`，未随本仓库发布，方法论部分可独立使用） |
| prd-doc（产出飞书文档时） | 同 research-doc |
| invoice-archive | `pip3 install pypdf`；macOS（解二维码用系统 swift + CoreImage）；第 1 步邮箱扫描依赖飞书邮箱授权（同上，未随仓库发布），第 2-5 步脚本独立可用 |
| creator-stats | 本机 Chrome 需安装 **Claude in Chrome** 扩展，且抖音、小红书为登录态 |

---

## License

[MIT](./LICENSE)
