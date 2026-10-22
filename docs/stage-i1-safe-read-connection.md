# I1 — 安全连接准备契约 / Safe read connection readiness

## 本轮结论与交付

审查基准：main `0c9a9a324665173503c6c6e0ef4ee6a3cd308609`（PR #83、#84
已合并）。**尚不能安全启动浏览器到 T1 的实时链路。** 本轮采用产品要求允许的
降级范围：连接契约、现有能力清单及可执行的隔离数据库验收测试。没有启动后端
监听器、增加 API、修改前端或声称完成在线连接。PR #83/#84 不再修改。

关键阻碍不是任务 SQL，而是浏览器身份与传输：G3b 仅有进程内 ASGI 入口，
没有任务路由；G3a 仅有注入式虚构 code exchange，没有浏览器绑定的登录，
Cookie、Origin/CSRF、可信启动或监听器部署契约也未落实。不能把成员下拉框、
本机访问权、URL 中的 Person、测试 proof 或复制的 bearer 变成临时登录。

## 已检查的实际能力

| 边界 | 已有能力 | 仍缺少 / 不可推断 |
| --- | --- | --- |
| G2a / G2b2 | SQL 当前成员、来源/独立 publication 权限；哈希会话、绑定/成员 epoch、过期/撤销、事务内重查 | 真实登录、客户端会话交付、生产部署 |
| G3a `LoginFlow` | 注入式虚构 OIDC code/PKCE/state/nonce 流程 | 浏览器绑定、真实 IDP、可信 key discovery、MFA/恢复 |
| G3b `FictionalReadAPI` | 仅进程内 `GET /v0/workbench`，当前 opaque session + G2a 权限 | 任务/Pending 路由、本地服务启动、浏览器请求支持 |
| T1 `TaskService` | `tasks`、`pending`、`history`，以及独立确认的内部 `apply`、`verify_outcome` | HTTP 契约、前端连接、生产数据/任务生产者 |
| H1 / UX1 | 同一中英文家庭界面、主题、成员切换、内存任务/个人决定 | 真实身份、持久化、服务端授权；成员选择只切换演示 |
| H2 | 实际 G3b 响应生成的虚构历史文件 | 实时请求、当前权限、T1 待办；不能用作私人数据缓存 |

G3b 的 `published_steps` 是独立 publication 字段，**不是** T1 已接受待办。
它的 `400 request_unavailable` 是统一的进程内错误，不能假设已有 401/403/503
或浏览器 CORS 行为。允许的请求头甚至不支持普通浏览器请求配置。
H1 CSP 的 `connect-src 'none'` 仍然保持，不能为了接线悄悄取消。

参考：[T1](v0-1-durable-household-tasks.md)、[G3b](v0-1-fictional-read-api.md)、
[会话](v0-1-session-service-boundary.md)、[G3a](v0-1-oidc-login-foundation.md)、
[G2a](v0-1-durable-household-authorization.md)、[UX1](v0-1-unified-household-ux.md)、
[H2](v0-1-offline-backend-workbench.md)。这些实现没有被复制或替换。

## 当前数据流与下一步最小读链路

当前可执行的隔离测试：

```text
批准的 T1 Elm 虚构测试配置 → 临时迁移后的 SQL 数据库
离线 verifier proof → SessionService 建立两个独立会话
TaskService.tasks(bearer) → household transaction
  → 当前 session / binding / membership
  → 独立 task_member_grant → SQL count / filter / page
  → 最小 TaskView（事务退出成功后才返回）
```

测试配置是特权 fixture，不是登录或客户端入口。接受任务只用于准备虚构测试状态，
I1 不暴露任何写入能力。两位平等成年人读同一 `household_task`，不建立个人任务库。

下一步拟议数据流（**尚未实现**）：

```text
现有 Samas 家庭 UI 的明确「本地开发测试」模式
  → 经批准的浏览器登录/会话和同源传输边界
  → 新的、单独评审的任务 GET adapter
  → 原有 TaskService.tasks（每次请求重新授权）
  → 严格 JSON allowlist → 替换当前任务页面和计数
```

既有接口：一个进程内 GET，加上上述 Python 内部方法。**本 PR 新增运行接口：0。**
拟议任务 GET 的路径、版本、浏览器错误码、登录方式仍待批准，不是假定已存在的 API。
不先实现 bearer 输入框、hard-coded token、查询参数身份、公开 fixture 初始化或
从会话调用 `harness_context()` 的捷径。首个浏览器里程碑也不应暴露 T1 `apply()`。

## 首个任务读取契约

可映射的现有 `TaskView` 字段：`id`、`step`、`assignee`、`status`、
`approved_date`、`revision`、`rights_revision`、`can_edit`、`can_history`。
Page 仅有 `items`、`total`、`has_more`；limit 为 1–20，offset 为 0–1,000,000，
可选固定 `Step` 过滤，按资源 ID 稳定排序。不是任意文本搜索或按任意日期排序。
未来 JSON 只能显式映射批准字段，不通用序列化 ORM；不返回 bearer、hash、
来源 ID、私人标题/证据、acceptance provenance 或私有 freshness 警告。

待办标题只能来自固定中性 Step 的译文；不能从私人邮件补全。日期仅显示明确批准的
`approved_date`，null 不生成日期。`pending/completed` 是家庭跟踪状态，不代表外部
活动完成。计数与分页由数据库授权查询给出，前端不得从两人的数据并集计算。
能力字段不等于本轮允许写入；本地连接模式未来也应保持只读，隐藏写按钮并在后端拒绝写。

T1 Pending 需要来源 observation 与独立 proposal-read 权限；Safety 有独立 security
权限。Review/Defer/Needs information 只是个人 annotation，Accept 独立确认；
CAS、精确 evidence/definition/generation、recipient plan 和实际 actor/request 历史
都由服务端验证。任务 history 另需权限，私人 review history 仅当前 actor。
T1 没有 UX1 的个人 archive/reopen 命令；Defer 仍留在 unresolved Pending，不能把
浏览器的分类行为伪装成已持久化。首轮只读接线不显示可提交的个人处理控件。

## 必须执行的 UI 状态契约（待浏览器实现验收）

| 状态 | 预期展示 | 禁止行为 |
| --- | --- | --- |
| 请求中 | 简短「正在读取家庭待办」/ “Loading household tasks” | 先填入离线演示任务/旧私人页面 |
| 服务不可用或超时 | 「暂时无法连接本地测试服务」及显式重试入口 | 自动退回 H1 fixtures、声称保存成功 |
| 请求/JSON 契约失败 | 内容不可用，不渲染部分字段 | 忽略未知字段或误报空列表 |
| 会话无效/权限不可建立 | 通用访问不可用，不披露身份/事项是否存在 | 显示缓存详情、从成员下拉框重新认证 |
| 当前授权任务为空 | 「暂无家庭待办」，显示服务端授权 total=0 | 暗示整个家庭没有私人事项 |
| 后续请求发现撤权 | 清除该连接视图的旧数据，重新获取当前范围 | 保留旧详情/计数/历史作为授权租约 |

这些是验收定义，不是已交付的 UI。现有离线 UI 不新增假“后端连接”按钮或失败模拟。
错误不显示驱动异常、令牌、私人内容。不存在的 task 和不可访问 task 不应可区分。
未来详情/history 必须独立重新授权，不能凭列表中出现过就读取。

事务沿用 SQLite `BEGIN IMMEDIATE`、PostgreSQL READ COMMITTED household row lock。
已提交撤销改变下一次读；测试不证明最终读取到网络发送的无泄露原子性。
已发送的数据无法追回，跨请求分页不是一致快照；不实现可重用私人缓存、自动后台重试。

## Windows PowerShell：本轮可执行验收

在仓库根目录、已安装项目依赖的 Python 3.12 环境运行。不要启动真实运行数据库，
不要运行本地 Alembic upgrade/register/ingestion，也不要配置真实 DATABASE_URL。

```powershell
# 拒绝意外使用环境中已有的测试目标；默认仅 pytest 自有临时 SQLite。
if (Test-Path Env:TEST_DATABASE_URL) { throw 'Use a clean test shell, or separately approve a disposable PostgreSQL test target.' }
.\.venv\Scripts\python.exe -m pytest -q tests/test_i1_read_readiness.py
.\.venv\Scripts\python.exe -m pytest -q tests/test_household_tasks.py tests/test_household_sessions.py tests/test_fictional_read_api.py
.\.venv\Scripts\python.exe -m pip check
git diff --check

# 现有独立离线应用；它不连接以上服务，成员下拉框不是登录。
Start-Process (Resolve-Path '.\prototypes\h0-workbench\index.html').Path
```

没有合法的 I1 后端启动命令或端到端浏览器登录命令可提供；不要用 `http.server`、
直接部署 G3b、关闭 CSP 或浏览器安全开关来替代。PostgreSQL 16 在 CI 的专用数据库
运行完整相同测试，每项独有 schema；不接触用户运行数据库。H2 仍可按其原文档
生成历史虚构预览，但不算任务实时接线，也不是本轮替代实现。

## 实际验证范围与限制

新增 15 项 readiness probes 复用批准的 T1 虚构 fixture、真实迁移/会话/授权服务，
验证空页与认证失败的区别、两成员统一任务、授权分页计数、源权限独立、任务撤权、
无私人来源 SQL 读取、准备参数后撤销 session/member/binding、跨家庭/伪造身份拒绝、
故障不返回旧数据、隐藏 Pending 变化不影响任务投影、查询边界。
fixture 的内部接受仅用于测试准备；没有向用户开放提交。
原有并发、CAS、重放、UNKNOWN、迁移 round-trip、字段隐私及浏览器回归保持不变。
本轮不声称执行了未实现的浏览器错误状态或 Windows 联机验收；无新 UI 截图可提供。
实际完整 SQLite/PostgreSQL CI 数字及链接在 PR 描述，不从历史 CI 推断。

## 后续审批顺序

1. 批准隔离本地浏览器身份/会话启动契约：fixture-only 临时数据库、禁止运行 DB
   发现、显式 opt-in、loopback/Host/Origin/DNS-rebinding 防护、session secret 交付与
   生命周期、Cookie/CSRF、错误/资源限制、测试身份非生产认证。不能只选一个 server
   包就视为这些问题已解决。真实 OIDC/生产部署仍单独评审。
2. 评审最小同源 Tasks GET adapter，复用 T1，不变更授权；验证两成员、撤权、空页、
   错误、断开、分页与响应交付限制。离线模式和连接模式显式分开，绝不混合数据源。
3. 只读通过独立评审及 Windows 验收后，再分别设计 Accept/Edit/Pending 写入：服务端
   当前能力、独立确认、版本绑定、CAS、精确请求幂等、UNKNOWN 对账，不能盲重试。
   Archive/Reopen 需新持久化契约，不用前端内存冒充后端支持。

不选择真实 IDP、框架或部署商，不开启真实家庭数据、提供方、AI、任务自动提取、
外部写入或 standing consent。此 PR 保持 OPEN，等待 ChatGPT、Muse 和用户审查。
