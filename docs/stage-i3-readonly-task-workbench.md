# I3 — 家庭待办只读连接 / Authorized task workbench

基准 main：`42e5d5231fc338ed82868929dc42f4312cf6de1d`（I1 #85、I2 #86 已合并）。
这是**实际调用数据库与授权服务的虚构数据连接**，不是连接真实家庭数据。
没有生产登录、任务写入、真实账户、提供方、AI 或 Finance 集成。

相关契约：[I1](stage-i1-safe-read-connection.md)、[I2](stage-i2-local-session-boundary.md)、
[T1](v0-1-durable-household-tasks.md)、[UX1](v0-1-unified-household-ux.md)。

## 实现与数据流

```text
--synthetic-only → I2 自有临时 SQL 数据库 → 固定 T1 fixture 初始化
→ 同源只读家庭界面 → I2 一次性终端批准 → HttpOnly Cookie
→ GET /api/tasks → I2 本地 lease + SessionService.resolve
→ TaskService.tasks 再次在事务中检查 session/binding/member/task grant
→ SQL 授权过滤、计数、排序、分页 → 显式 JSON → 严格浏览器校验 → DOM
```

I3 复用 UX1 的**原始 styles.css**、Samas 文字标识、五项主导航、更多菜单、双语及
系统/浅色/深色交互。小型只读 renderer 不加载 H1 fixtures.js/model.js/presentation.js，
避免未经批准的内存操作。这是明确分开的连接适配器，不是第二个任务系统或管理后台。
将来统一前端入口时也必须保留数据源/能力边界，不复制领域状态或权限引擎。

| 区域 | 当前行为 |
| --- | --- |
| 首页 / 家庭待办 | 当前 Cookie 的 T1 任务、服务端授权总数/分页/固定 Step 筛选 |
| 详情 | 先重新读取当前页，再显示最小中性字段；没有来源/历史请求 |
| 待确认 / 日程 / 安全 / 信息 / 优惠 | 明确“本轮未连接”，不显示离线记录或伪造 0 项 |
| 设置与隐私 | 唯一外观入口、注销测试会话；没有来源/任务权限编辑 |
| 接受 / 编辑 / 归档 / 重新打开 | 无接口、无按钮，不把内存变更冒充保存 |
| 原 file:// H1/UX1 | 完全独立，原文件未改，仍为标签页内存演示 |

首页明确标为“任务总数 / Tracked tasks”，保持服务端 total 不变。任务总数包含 T1
的全部授权跟踪状态（包括 completed），**不是未完成任务统计**。
completed 只表示家庭跟踪，不代表外部执行。日期为 null 时不补造日期；approved_date
不是推断的截止日期。任务标题只翻译中性 school-session/home-visit，不读取私人标题。
其他 Dashboard 数字显示“—”表示未连接，不从当前任务页编造全局日程/安全统计。

I2 仅提取 Cookie 解析、默认拒绝的 GET 扩展和可信 application/terminal lifecycle 复用
接缝；默认 I2 仍无数据路由，会话/CAS/UNKNOWN 不变。没有从 session 调用
harness_context()，没有修改 G2a/G2b2/G3a/G3b/T1 后端代码、迁移或提供方行为。

I3 前端每次明确请求 `limit=12`（API 原默认 2、最大 20 不变），当前 2–3 项授权任务
同页显示；超过 12 项才按服务端 has_more 分页，不拼接或缓存额外任务。
桌面/中屏任务卡片为两列，手机单列。顶部“当前成员 / Current member”为会话只读
显示，与语言和重新读取在同一控制区，不是身份选择器；手机语言仍在“更多”唯一入口。

## GET /api/tasks 契约

仅 I3 模式新增，I2 的四个 session POST 不变。

| 项目 | 限制 |
| --- | --- |
| 网络 | 字面 127.0.0.1、绑定端口的精确 Host；无 LAN、代理信任或 CORS |
| 方法/路径 | 精确 GET /api/tasks，REQUEST_URI 必须一致，拒绝编码别名 |
| 浏览器头 | Sec-Fetch-Site: same-origin；X-Samas-Intent: local-session；Accept: application/json |
| Origin | 浏览器同源 GET 可省略；出现时必须精确同源。不能省略 Fetch Metadata/自定义头 |
| Body | 空；Content-Length 空或 0，无 Content-Type、传输/内容编码 |
| 身份 | 仅当前 HttpOnly Cookie；无 URL 身份、Authorization 或其他 X-* 身份/代理头 |
| Query | 最多 128 ASCII 字符、三个不同参数 limit/offset/step；无空值、重复或百分号别名 |
| limit / offset | 默认 2 / 0；规范整数 1–20 / 0–1,000,000 |
| step | 可选，精确 school-session 或 home-visit，服务端授权 SQL 内过滤 |
| Response | 最多 16,384 bytes，规范 ASCII JSON，no-store/no-cache，原 I2 防护头/CSP |

浏览器普通头不作为权限输入。无任意文本搜索、负责人过滤或独立详情/history 路由。
所有应用拒绝仍统一 400 local_session_unavailable，不暴露身份或任务是否存在。
没有 grant 和确实无任务同为“当前没有可查看的家庭待办”，不披露隐藏人口。

版本 `i3-fictional-task-page-v1`：

```json
{
  "schema": "i3-fictional-task-page-v1",
  "synthetic_only": true,
  "pagination": {"limit": 2, "offset": 0},
  "tasks": {"items": [], "total": 0, "has_more": false}
}
```

item 仅允许 `id, step, assignee, status, approved_date, revision`，是 I1 TaskView 的
只读子集。rights_revision、can_edit/can_history 等权限元数据不发送，没有通用 ORM/
dataclass 序列化。没有来源、Pending ID、邮箱标题、证据、凭据、hash、会话秘密或历史。
G3b published_steps 完全未使用，它们不是已接受任务。

total/items/has_more 来自同一个 T1 Page，不由客户端过滤授权或拼接两成员集合。
同一共享任务只有一个身份，不按观察者重复计数。T1 自行生成 UUID，跨次启动 ID 会
变化，单次数据库内按任务 ID 稳定分页，不按标题推断去重或优先级。
浏览器严格验证 keys/版本/枚举/类型/边界/日期/重复/顺序/分页，要求规范 JSON，
也拒绝重复 key、非规范数值、非有限值；坏响应整体拒绝，不显示部分字段。

## 固定虚构初始化与权限

复用 I2 Willow/Clara/Devon。在 listener 创建前，可信 fixture 注册一个仅 Clara 有
observation/security 权限的 fixture 来源，配置四个新 Pending 与独立 publication plan。
用 verifier 签发的临时 setup session 调用原 T1 ACCEPT（明确 confirm=True）创建三项任务，
再经原 EDIT 将其中一项标为 completed；setup session 随后注销，不交给浏览器。
没有直接 insert household_task、分类或自动提取。第四项 i3-unaccepted 仍未接受。

| 成员 | 授权任务 | 状态 |
| --- | --- | --- |
| Clara | 3 | 两项共同可见，一项仅 Clara 可见 |
| Devon | 2 | 同样的两项共享任务，无私人来源权限 |

共享项中一项有明确虚构批准日期 2035-06-12，另一项 completed 且无日期；个人项也
无日期。这些是测试初始化，不声称用户刚在浏览器接受了任务。
测试撤权/故障由 tests/browser 下的可信控制器执行，不存在浏览器初始化或权限管理
API，也不宣称实现了生产授权变更审计。正式 I3 terminal 仅保留 I2 配对与退出。

TaskService 沿用 SQLite BEGIN IMMEDIATE / PostgreSQL household lock，先前 resolve
不是权限租约：T1 自己再次检查当前成员、会话与独立 task grant。已提交撤销改变下一次
读取。任务投影不查询私人来源/Pending/payload/history，来源撤销和私有安全信息变化
不会改变独立共享任务。任务撤权则改变当前授权计数/分页，不隐藏无关成员的任务。

## 失败与撤权

- 显式导航、筛选、重新读取与语言切换先清旧内容并显示加载；不会先填离线数据。
- 每五秒自动复验仍调用当前 session 与 T1 授权查询。在有界请求期间保留已显示 DOM；
  成功且授权投影未变时不重建导航、设置或详情。此举只稳定焦点，不授予权限租约。
  已授权字段变化时更新内容，详情关闭按钮保持挂载；任务消失时清空并关闭详情。
  一旦发现会话失效、撤权、错误或坏契约，立即移除旧任务、数字及详情 DOM；超时亦如此。
- 网络失败/超时、会话/权限无法验证、JSON 不匹配分别有明确提示；坏响应不保留旧内容。
- 重新读取只检查当前 session 并 GET，不重建会话、重复批准或写任务。
- 有效 session 的任务失败不要求重新配对；失效 session 只能显式发起并经 terminal 批准。
- 详情只使用重新取得的当前页中性字段；撤权/移出当前页时不继续显示旧详情。
- 当前可见连接每五秒重查，配对每两秒，请求五秒超时；theme 仅 CSS，语言/导航重新读。
- 请求序号拒绝晚到的旧响应；pagehide 清显示，BFCache 恢复重新验证。无客户端落盘缓存。
- 仅合并同时在途的 session-status/单次领取请求，结束即丢弃，不缓存授权结果；每次 Tasks
  GET 仍在 T1 中独立重新授权，避免浏览器并发操作重复消费配对 Cookie。
- 服务退出、注销或刷新不会从内存模拟重建任务。

**不声称端到端零撤权竞态**：读事务先完成的响应可能在撤权后送达，已发送字节不能
追回。轮询和超时决定发现时间；下一次 SQL 查询按当前权限。没有可复用权限租约、
push 或跨页一致快照。旧请求序号保护不等于解决网络交付竞态。

I2 限制完全保留：终端批准不是真实认证；HTTP loopback 不是 TLS；Secure Cookie 依赖
实际浏览器支持，Cookie 不按端口隔离。只运行一个实验，使用独立可信浏览器 profile，
不能推广到真实家庭数据或不可信本机服务。不能降低 Secure/HttpOnly 或关闭浏览器安全
保护作兼容回退。生产 OIDC/MFA/HTTPS/部署审查仍未完成。

## Windows PowerShell

从仓库根目录、已有 Python 3.12 环境，一次复制启动：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.lock
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
.\.venv\Scripts\python.exe -u .\prototypes\i3-workbench\serve_workbench.py --synthetic-only
```

打开打印的 127.0.0.1 URL（不要直接打开 I3 HTML 模板）。点击“发起请求”，核对公开
编号，在原 terminal 输入 `approve 页面编号 clara`。第二个独立 Edge/Chrome profile
对其编号批准 devon。没有成员身份下拉框；多个 InPrivate 窗口可能共享 Cookie。

核对 3/2 总数、共享任务、分页、类型筛选、只读详情和空日期；切换双语、系统/浅/深色、
390/320 宽度。未支持页面必须显示“未连接”。刷新只读取现有 session；注销仅影响本
浏览器。terminal 输入 quit 或 Ctrl+C，等待旧任务清除。重启是全新临时 DB，不恢复旧
session；不执行运行数据库的 Alembic/register/OAuth，不接受 DB URL 或任意 fixture 参数。

原离线入口仍独立：

```powershell
Start-Process (Resolve-Path '.\prototypes\h0-workbench\index.html').Path
```

Windows Chrome/Edge Cookie、真实字体/缩放和退出清理仍需人工验收；禁止端口转发。

## 验证、截图与复审

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_i3_workbench.py tests/test_i2_local_session.py tests/test_household_tasks.py tests/test_i1_read_readiness.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

实际浏览器验证需本机已有获准 Playwright/Chrome，不安装/下载浏览器或模型：

```powershell
$env:I3_TEST_PYTHON = (Resolve-Path '.\.venv\Scripts\python.exe').Path
$env:I3_CHROMIUM = 'C:\Program Files\Google\Chrome\Application\chrome.exe'
# NODE_PATH 仅指向本机已有 Playwright 的 node_modules（如非项目本地安装）。
node .\tests\browser\i3-workbench.js --synthetic-only
```

pytest 自有临时 SQLite / PostgreSQL schema 覆盖授权人口、隐藏字段、跨家庭 session、
查询/头/方法/尺寸、JSON 白名单、当前撤销、数据库故障与源/任务独立性。另覆盖运行
时限、并发单次领取和真实进程关闭清理。完整双数据库实际计数/日志见 PR，不推断历史
CI。实际浏览器保持 CSP、真实 Cookie 和真实 SQL；故障/坏响应是受控合成注入。
焦点回归使用真实五秒计时，连续跨过至少两轮复验，检查导航、语言/外观选择器及
详情关闭按钮的 DOM 身份和键盘焦点；另验证自动故障与撤权清除已打开的详情。
不读取真实数据、Holdout、提供方或 AI，不削弱原有 CAS/UNKNOWN/迁移/离线回归。

| 真实连接截图 | 链接 |
| --- | --- |
| Clara 浅色桌面首页 | [截图](screenshots/i3/home-clara-light-desktop.png) |
| Clara 浅色桌面家庭待办（同页三项） | [截图](screenshots/i3/tasks-clara-light-desktop.png) |
| Devon 浅色 390px | [截图](screenshots/i3/home-devon-light-390.png) |
| Devon 英文深色 320px | [截图](screenshots/i3/home-devon-dark-en-320.png) |
| 桌面只读详情 | [截图](screenshots/i3/task-readonly-detail-desktop.png) |

同一 browser test 加 --screenshots 可重现；只显示已授权虚构投影，不显示 Cookie 或
私人来源。这些不是 Windows/生产认证证明。

## I4 后续建议

分别设计 Accept/Edit：服务端当前能力、resource/rights/plan revision、精确证据绑定、
独立确认、actor/request 幂等、UNKNOWN 安全对账，不能直接显示本轮隐藏的按钮。
负责人候选也要授权投影，不能按邮箱所有者推断。
个人稍后处理/归档/重新打开需新持久化契约与每成员并发语义；现有 T1 defer 仍 unresolved，
archive/reopen 未实现，不得照搬离线 UX1 模拟为已保存。任务共享、私人来源与外部执行
同意独立，R0–R3 不变，Alternative B standing consent 继续禁用。

请 ChatGPT/Muse 检查：Cookie 到 T1 是否全程当前授权？字段/错误/计数是否排除私人来源？
坏/晚到响应是否不能恢复旧任务？I2 默认是否仍 session-only？未支持功能是否明确且无
内存写入替代？PR 保持 OPEN/UNMERGED，等待双重审查及 Windows 人工验收。
