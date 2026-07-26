---
name: personal-brand-builder
description: 个人品牌一站式打磨：简历（docx/LaTeX）撰写与审校、个人主页（GitHub Pages）重构、全平台头像昵称简介统一、账号改名迁移善后。当用户说"改简历/优化简历/审校简历"、"做个人主页/重构主页/个人网站"、"统一头像昵称"、"写自我介绍/简介"、"GitHub 账号改名了"、"投递准备"、"个人品牌"时使用。适合求职期学生与职场人把简历、主页、社交身份打磨成一套自洽的品牌系统。
---

# Personal Brand Builder

把一个人的简历、个人主页和全平台身份打磨成**一套自洽的品牌系统**。本 skill 来自一次真实的 10 小时端到端实践（简历三轮迭代 + 主页完整重构 + 账号迁移善后），沉淀为可直接执行的工作流。

## 核心原则（先读这个）

1. **用户的既有文档是事实的唯一权威**。从语料、笔记、聊天记录里挖到的日期和数字，与用户自己写的简历冲突时，一律以简历为准，冲突点明确报告。
2. **数据口径诚实**：区分"目标"（盗版风险降 50% 是团队目标）、"平台成果"（单价降 70% 是平台整体）、"个人产出"（两份 PRD 是本人写的）、"预估"（节降 5HC 要写"按当前量测算预计"）。口径含糊的简历经不起面试追问。
3. **删掉会让读者打折扣的信息**。面向大众的简介不写"27 届本科"（触发"学生能懂什么"的先入为主）；HR 自然会看简历，简历里才放届数。同理："求职意向："这类标签词、自封的头衔（"XX 实践者"）都删。
4. **每次改动立即验证**。改 docx 后重新渲染看版式；改 LaTeX 后查页数和字体嵌入；改网页后本地起服务看桌面/375px/暗色三态；推送后轮询线上生效。没验证过的改动不算完成。
5. **审美克制**：能用留白就不用分隔线，能用一种颜色就不用两种，能删的字都删。参考 kongge.space / jerryzhang.me 的文字优先风格。

## 工作流一：简历

### 1.1 素材 → 简历段落

- 从用户的工作语料（日报、PRD、周报、分享稿）提取：时间线、职责、可量化数字、问题-方案-结果链。
- 每段经历的骨架：`公司 · 部门 | 角色 | 时间` + 业务一句话 + 2-4 条 bullet，每条 bullet 以粗体短语开头（"风险定位标注："），正文遵循"问题 → 我做了什么 → 可验证结果"。
- 编辑已有 docx：unzip → 改 `word/document.xml`（先合并碎片化 run）→ 重打包 → 用与原段落**完全相同的 XML 样式模板**插入新内容，保证字体字号列表样式一致。

### 1.2 审校清单（逐项过）

- [ ] 段落结构：标题行与正文是否误合并在同一段落
- [ ] 日期：区间格式统一；bullet 里的日期带年份；上线时间不能晚于离职时间
- [ ] 错别字与术语拼写（Embedding 不是 Enbedding）
- [ ] 内部黑话：Stella、CAP 这类内部系统名，首次出现加一句括注
- [ ] 表述一致："从 0 到 1" 与 "0-1" 选一种；引号全用中文弯引号""，禁用「」
- [ ] 半角/全角标点混用（冒号、括号）
- [ ] 文件名：投递文件名不能带内部版本备注（"(百度充实版)" 这种 HR 看得到）
- [ ] 外部 review（如让另一个模型评审）逐条判断：采纳 / 驳回（附证据）/ 搁置（缺数据），不照单全收——工具报的"字体缺失"可能是它自己的渲染器问题，用 `pdffonts`/`pdftotext` 实证后再动手

### 1.3 LaTeX 单页简历（推荐终态）

- 引擎：`tectonic`（Homebrew 安装，自动拉包）。
- 中文字体：macOS 用 `Hiragino Sans GB`（W3/W6 配对）。注意它无 ToUnicode 映射，若在意解析器兼容可换 `Songti SC` 或 `Lantinghei SC`（有映射），但**视觉优先，poppler 类主流解析器无映射也能正确提取**——用 `pdftotext resume.pdf -` 实测。
- 版式：`extarticle` 9pt、A4 边距 0.9-1.3cm、`titlesec` 细线小节、条目宏 `\entry{左粗}{中灰}{右日期}`、itemize 紧凑间距。溢出一页时优先删"与后文 bullet 重复的业务首句"，其次压行距。
- 照片：`\includegraphics` 放 header 右侧 minipage，证件照裁 3:4、600px 宽即可（2cm 打印 ≈ 760dpi）。
- 每次改完：编译 → `pypdf` 查页数 → 同步投递用命名副本 → 用户偏好的阅读器打开给用户看。

## 工作流二：个人主页（GitHub Pages）

### 2.1 方案先行，不要直接写代码

- 用户说"不喜欢"时，**给 2-3 个气质差异明显的方向**（摄影集 / 杂志 / Bento 格子…）配视觉稿让用户选；连续两次不中就停止盲猜，直接要参照网站。
- 拿到参照站：curl 抓 HTML + CSS，提取它的设计 token（版心宽度、配色变量、字号体系、组件模式），照骨架适配用户内容，明确"照搬什么 / 替换什么 / 用户的差异化是什么"。

### 2.2 实现要点（framework-free 静态站）

- 结构：`index.html` 挂载点 + `js/data.js`（全部内容，改文案只动它）+ `js/components/*.js`（区块渲染）+ `styles/`（tokens → base → layout → components → responsive 分层）。无构建步骤。
- 深浅色三态：CSS 变量 + `prefers-color-scheme` 默认跟随系统 + `data-theme` 手动覆盖存 localStorage + `<head>` 内联 3 行防闪脚本。
- 微信场景：复制按钮用 `navigator.clipboard` 加 `execCommand` 降级（微信内置浏览器兼容）；公众号入口点击开二维码大图（大图长按识别比页面小图好用）。
- 图片：hero 照片方裁 720px、90KB 内；原始几 MB 大图不进仓库。
- 验证流：本地 `http.server` → 桌面截图 → 375px 截图 → 暗色截图 → 控制台无报错 → `node --check` 全部 JS → push → 轮询线上 `curl` 生效。

### 2.3 内容策略

- Hero：问候语 + 一段有数字的叙事 + 3-4 个胶囊按钮（简历 / GitHub / 邮件 / 微信）。按钮顺序按访客转化漏斗：先证据（简历、GitHub）后联系。
- 简介一条链走天下：`AI PM | 学校 | 公司A → 公司B → 公司C → 现状`，箭头表推进感；各平台简介栏统一贴这条。
- 页脚放个人 slogan，标题栏只放名字——**名字本身就是最好的标题**。
- 大陆可达性：`*.github.io` 在大陆手机端大概率打不开。终态方案是自有域名 + Cloudflare 代理；投简历前先用手机蜂窝网络实测主页链接。

## 工作流三：全平台身份统一

| 元素 | 策略 |
|---|---|
| 头像 | 全平台同一张（同一裁切），选构图干净的单人照 |
| 昵称 | 内容平台"名字-职业"（重名区分 + 定位速达）；正式场合（求职微信/简历/内部 IM）用本名 |
| 简介 | 上面那条链，全平台统一贴 |
| handle/域名 | 与昵称对齐（如 `yaowenhu-pm` ↔ 胡耀文-PM ↔ yaowenhu.com），别绑定学校等会过期的身份 |
| 邮箱 | 国内投递用秒收秒回的邮箱（foxmail/QQ）；品牌对外用与 handle 一致的 Gmail；终态是自有域名邮箱 + 转发 |

## 工作流四：账号改名迁移清单（血泪版）

GitHub 账号改名后，旧 `*.github.io` 域名**不重定向**，逐项检查：

- [ ] 用户主页仓库改名为 `<新用户名>.github.io`（否则建站直接失效）
- [ ] 所有仓库 README 里的旧域名/旧用户名链接（`grep -rn` 全仓库扫）
- [ ] 仓库 homepage 字段（About 侧栏链接）
- [ ] 被转移仓库的 Pages 开关（转移会静默关闭，`has_pages` 查、API 重开）
- [ ] **CORS/Origin 白名单**：Cloudflare Worker、统计服务里硬编码的旧域名（403 的根源）
- [ ] **OAuth 登录白名单**：worker/后端里写死的旧 GitHub login
- [ ] 本地克隆的 remote、目录名、启动配置
- [ ] 简历和各平台简介里的主页链接
- 教训：改名影响的不只是链接，还有**所有做了来源校验的服务**。

## 常用命令速查

```bash
# LaTeX
tectonic resume.tex && pdffonts resume.pdf && pdftotext resume.pdf - | head
# docx 检查
python merge_runs.py unpacked/ && python validate.py out.docx --original in.docx
# 主页本地验证
python3 -m http.server 4173
find js -name '*.js' -print0 | xargs -0 -n1 node --check
# 部署轮询
until curl -s https://SITE/js/data.js | grep -q "标志字符串"; do sleep 5; done
# 域名可用性
whois yaowenhu.com | grep -i "no match" ; curl -sL https://rdap.org/domain/xxx.com -o /dev/null -w "%{http_code}"  # 404=未注册
```
