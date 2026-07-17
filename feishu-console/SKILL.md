---
name: feishu-console
description: 飞书开发者后台操作。当用户要给飞书应用(infidive-全功能助手)添加权限/scope/事件订阅、发布应用版本、排查"事件不推送/API 报权限错误(99991679等)/事件订阅不生效"、或提到"开发者后台/open.feishu.cn/添加事件/加权限"时使用。通过浏览器自动化完成后台点击，含发布与验证。
---

# feishu-console · 飞书开发者后台操作

给 `infidive-全功能助手`（app_id `cli_aab5c810a4f89bd9`）加权限/事件、发版本。**全流程可用浏览器自动化替用户完成**（Claude in Chrome），前提：浏览器已登录飞书且是 App 协作者。

## 判断：你要加的是哪种东西

| 症状/需求 | 类型 | 入口 |
|---|---|---|
| API 报 `99991679` / `Unauthorized...required privileges: [xxx]` | **权限 scope** | `open.feishu.cn/app/cli_aab5c810a4f89bd9/auth` |
| 长连接通了但收不到某类事件 | **事件订阅** | `open.feishu.cn/app/cli_aab5c810a4f89bd9/event` |

## 流程 A：添加事件

1. 打开 event 页 → 右上「Add Events」
2. 搜索框输事件 key（如 `drive.file`）——**注意有 Tenant / User 两个 tab**：
   - 按**文件订阅**（`/drive/v1/files/{token}/subscribe` 用 user token 调的）→ 必须勾 **User Token-Based** 版
   - App 身份（bot、tenant_access_token）收事件 → 勾 **Tenant Token-Based** 版
   - 拿不准就两边都勾，无害
3. 点「Add」→ 弹「Suggested scopes to add」→ 标着 `Automatically approved scope` 的直接点「Add Scopes」
4. **必须发版本才生效**：顶部横幅「Create Version」→ 版本号自动 +1，更新说明写清加了什么 → Save → 确认弹窗点「Publish」。企业自建应用**免审核、发布即生效**（弹窗会写 "exempt from review...go live instantly"）
5. **验证**（别跳过）：触发一次该事件（如 `feishu.py append` 编辑一篇已订阅文档），确认监听端 events.jsonl 在 ~10 秒内收到

## 流程 B：添加权限 scope

1. 打开 auth 页（Permissions & Scopes）→ 搜索 scope 名（报错信息里有，如 `bitable:app:readonly`）→ 添加
2. 同样**发版本**（流程 A 第 4 步）
3. ⚠️ **user token 的 scope 不会自动扩展**——新 scope 要让每个用户重新 OAuth：
   ```
   cd ~/.claude/skills/feishu && python3 setup.py
   ```
   同时把新 scope 追加进 `setup.py` 的 `SCOPE` 串（不然重授权也拿不到），改完提交 skills 仓库。
4. 验证：重跑之前报错的 API 调用。

## 已知坑（实测踩过）

- **事件推送 = 后台事件列表 ✓ + （drive.file 类）按文件 subscribe ✓，两个条件缺一不可**。只订阅文件不加后台列表 → ws 连着但永远收不到。
- **飞书没有 wiki 节点"新建"事件**（只有普通云盘文件夹有 `created_in_folder`）。新建文档只能轮询发现——不要浪费时间找这个事件。
- 发版后事件立即生效；**scope 生效但 user token 要重授权**（见流程 B.3）。
- 后台是英文界面时按钮叫 Add Events / Add Scopes / Create Version / Publish。
- **OAuth 授权串里带 App 未开通的 scope 会导致整个授权失败**（错误码 **20027**，页面会列出缺哪些）——`setup.py` 的 SCOPE 必须与后台已开通权限严格一致；加新 scope 的顺序是先后台开通，再改 SCOPE 串，最后重新 OAuth。
- **有些 scope 名在控制台不存在**（如 `im:resource:upload`）——搜不到就搜父级/关键词（`im:resource` 就覆盖 Upload file/image）。控制台搜不到的 scope 从 SCOPE 串里删掉，不要硬留。
- **免审批（Approval required: No）的 scope 添加后立即生效，不需要发版**——顶部横幅保持绿色就说明不用 Create Version；只有事件、需审批权限等改动才要发版。
- OAuth 全流程可自动化：构造 authorize URL → 浏览器打开点 Authorize → 拿回跳 URL 里的 code → `echo "<回跳URL>" | python3 setup.py`（setup.py 从 stdin 读 code）。

## 推荐基线（一次性补齐，避免高频回访后台）

**事件**（已加 ✅ / 建议候补）：
- ✅ `im.message.receive_v1`、`drive.file.edit_v1`(双通道)、`drive.file.title_updated_v1`、`drive.file.deleted_v1`、`drive.file.trashed_v1`
- 候补（要用到再加，勿盲加）：`drive.file.bitable_record_changed_v1`（看板行变更→可做勾选即归档）、`calendar.calendar.event.changed_v4`（日程变更感知）
- ❌ 不要加 `drive.file.read_v1`（每次阅读都推事件，纯噪音）

**scope**：以 `setup.py` 的 `SCOPE` 串为准；已知欠账——`bitable:app:readonly` 已在 App 端但 **user token 未重授权**（promote.py 看板读取被卡），下次跑 `setup.py` 重新 OAuth 即解。

## 与浏览器自动化配合

用 Claude in Chrome 执行时的要点：Add Events 弹窗里勾选后「Events selected: N」计数在左下角，确认数字再点 Add；发布确认弹窗有二次确认；发布成功标志是顶部横幅变绿「The current changes have been published」+ 版本页显示 `Released`。
