# I4a — 安全的虚构待确认接受 / Confirmed Pending acceptance

基准 main `6029a5175d83719fd53784c4e9b61746c11ad931`（I3 #87 已合并）。
本阶段连接真实 SQL、SessionService 和 T1，但**数据全部是虚构的，认证仍是终端批准的
测试会话**。不是生产登录或真实家庭数据接入。没有提供方、AI、任务提取、邮件/日历
写入、编辑、删除、归档、自动批准或外部活动执行；原 file:// 原型不变。

参考：[I1](stage-i1-safe-read-connection.md)、[I2](stage-i2-local-session-boundary.md)、
[I3](stage-i3-readonly-task-workbench.md)、[T1](v0-1-durable-household-tasks.md)、
[G3b](v0-1-fictional-read-api.md)、[安全架构](security.md)。

## 审查结论与复用

T1 已有当前权限过滤的 `pending()`、`tasks()`、显式 `apply(confirm=True)`、CAS、
不可覆盖 actor/request 事件及 fresh-connection `verify_outcome()`。G3b 是进程内
read-only ASGI，不是浏览器写入接口，也没有接受能力。I2 提供受控同源 Cookie 边界，
I3 提供中性 Tasks GET。I4a 不把这些未实现的能力冒充已有接口。

新增 T1 内部 `prepare_acceptance()`：同一 household transaction 验证当前来源与
Pending 权限，读取已批准的 recipient plan，准备不可变 Command。原接受校验提取为
`_accept_plan()`，预览与真正 ACCEPT 共用，不建立第二个权限引擎。预览不创建任务、
决定或 domain event，可能更新既有 session activity。确认时原 T1 再次验证全部条件。
没有 schema/migration、生产授权或身份模型变更。

I4a 有独立 runner，复用 I3 的同一家庭界面、样式、主题和只读 Tasks API；只在可信
I4a HTML 中加载一个窄 acceptance 模块。默认 I2 仍 session-only，默认 I3 仍 read-only。
I2 仅增加默认拒绝的 POST 扩展接缝；其原路由、Cookie 和 CSRF 校验保持。没有第二套
任务状态：浏览器只保留当前投影、未确认预览和本次请求结果，不保存任何家庭数据。

## 数据流与信任边界

```text
--synthetic-only → I2 自有一次性 SQLite → 新编虚构来源/提案/独立计划
→ 原 I2 终端批准身份 → HttpOnly session Cookie
→ GET Pending → T1 当前 session/member/source/特定 Pending 权限 → 最小投影
→ 用户请求预览 → T1 prepare_acceptance → 服务端绑定完整 Command
→ 浏览器只收到中性预览 + 随机确认编号
→ 用户明确“确认接受” → 原 T1 apply(confirm=True)
→ CAS/证据/计划复验 → 同一任务 + 当前批准的 task grants + append-only actor event
→ COMMITTED/REPLAY → 重新 GET T1 Tasks；不在浏览器追加任务
→ UNKNOWN/中断 → 显式只读对账；不自动重发写入
```

来源 observation、security、Pending read/publication、recipient plan 和独立 task
visibility 都由已有服务分别检查。有效 session、邮件所有者或浏览器显示的成员名不
授予这些权限；两位成年人没有默认超管。浏览器不能提交 household/person、recipients、
plan revision、assignee、日期、风险、证据、版本或任意 request ID。当前这个最小切片
由服务端固定选择全部当前批准的 1–2 位收件人：两位共同负责，单人则由本人负责。
日期仅使用确实存在的 supported_date，并在预览中明确呈现。没有自由编辑或扩大授权。

完整资源/权限 revision、generation/fingerprint/definition、recipient plan revisions、
assignment/date 与随机 request ID 留在服务端 Command。短期确认编号绑定精确 session
verifier；它不是认证凭据，跨成员或同成员另一 session 的编号无效。每次提交都重新
验证 Cookie 与 SQL 权限，预览不是权限租约。来源或版本变化、A→B→A 都不能继承旧接受。
任务的中性共享权限与私人来源独立，接受不能共享来源内容。

## API：版本化显式白名单

仅 I4a 新增下表；I2 四个 session POST 和 I3 Tasks GET 不变。客户端仍使用相对同源
路径，无 CORS、URL 身份、bearer 输入、外部资源或通用 ORM/dataclass 序列化。

| 方法 / 路径 | 请求 | 响应核心字段 |
| --- | --- | --- |
| GET `/api/pending` | 同 I3 的 limit/offset/固定 step 有界查询；UI 请求 12 | `i4a-pending-page-v1`, synthetic_only, pagination, pending:{items,total,has_more} |
| POST `/api/pending/preview` | 精确 `{id}` | `i4a-acceptance-preview-v1`, synthetic_only, receipt,id,revision,step,assignee,approved_date |
| POST `/api/pending/accept` | 精确 `{receipt,confirm:true}` | `i4a-acceptance-result-v1`, synthetic_only,outcome,receipt |
| POST `/api/pending/outcome` | 精确 `{receipt}`，只读 | 同 result schema，只检查该精确请求，不重放写入 |
| POST `/api/pending/recover` | 精确 `{}`，只读 | 同 result schema，核对本 session 最近预览/意图；不要求浏览器存储编号 |

Pending item 只含 `id,revision,step,supported_date,can_accept`；不传来源、原始证据、
fingerprint、其他成员的 annotation、recipient 计划、个人 metadata 或 history。
null step 显示“需要更多信息”；无支持/安全未知或高风险不提供确认接受。普通推广、
信息通知在原 T1 SQL Pending 查询中排除，而不是前端过滤。Home Pending 数字暂保留
“—”；Pending 页面显示服务端授权 total，不从任务页推断全局待确认数量。

GET 与 I3 相同的有界查询、empty body、Fetch Metadata/custom header/Accept 检查。
POST 要求精确绑定端口 Host、Origin、same-origin Fetch Metadata、自定义
X-Samas-Intent、application/json、1–256 bytes 声明并实际读取的 ASCII JSON body。
拒绝 query、路径别名、重复/未知 key、非布尔确认、传输/内容编码及客户端身份/代理头。
响应上限 16 KiB、规范 ASCII JSON、严格 keys/枚举/类型/日期/分页/重复验证，no-store。
请求/权限/数据库错误仍统一内容为空的 400，不返回内部异常。浏览器将任何接受请求的
超时、断开、错误 HTTP 或坏 JSON 保守地视为 UNKNOWN，而不是声称没有提交。

## 确认编号、幂等与 UNKNOWN

- 编号由 `secrets` 产生，预览有效 120 秒，用原 I2 monotonic clock；完整命令不交给客户端。
- 每 session 最多保留 16 项，最多 8 次 session 启动，防止无界分配；另一个成员的编号
  人口不影响本人的上限。过期未提交预览可清理；已提交项在该 session 的本地有效期内
  保留，以便读取精确 ledger。关闭服务清空内存并删除自有虚构 DB。
- 同一 session 只有一个可提交的预览；新预览使旧的未提交编号失效。对账也会先关闭
  对应编号的写入通道，再查 ledger。即使原 HTTP 请求延迟到达，也只能核对、不能在
  verified absence 后执行写入。页面刷新后的 recovery 关闭所有未执行编号，并核对
  最新预览，不能把较早任务的成功冒充新预览的结果。
- 在调用 apply 前记录已尝试；相同编号后续提交**只调用 verify_outcome**，绝不再次执行
  apply，即使上一次是 UNKNOWN。相同意图验证已提交可返回 COMMITTED-replay；改变意图
  不能覆盖原 ledger。多个不同确认编号对同一 Pending 仍由 SQL CAS/唯一约束保证单任务。
- COMMITTED 是有据的提交；NOT_APPLIED-stale/unavailable/changed-intent 是原 T1 的明确
  不生效结果；generic database/transaction/ACK/response failure 不能被改称 NOT_APPLIED。
- 对账使用 T1 新物理连接、同一 authoritative primary、当前 session/operation 权限和
  精确 actor/request/intent。已提交才报告成功，可信缺席才报告 verified absence；
  不可用/撤权/不一致仍 UNKNOWN。recovery 在 UNKNOWN 时不返回确认编号或私人结果。
- 同一浏览器最近意图仍 UNKNOWN 时，保守阻止建立替代接受意图；已授权读取仍可用。
  这是窄实验的单意图工作流限制，不是新增家庭权限规则。需核实后由人发起新的预览和
  确认，不自动换 request ID/rebase。权限撤销导致无法对账时不能越权恢复。
- 页面刷新可通过同一 Cookie 的“核对最近一次接受”读回结果。session 丢失/过期、
  进程退出或新 profile 不恢复该能力；不能把另一个 session/公开编号当身份。

不保存 browser localStorage/sessionStorage、不写任务缓存、不返回 session secret。
打开、取消、Escape、切页、语言/主题切换都不接受任务。注销/重新配对或已验证成员
变化会清除旧的客户端请求上下文；旧异步响应不能在另一成员会话中恢复详情或反馈。提交发出后关闭窗口不等于撤回；
迟到响应不构成外部活动执行。成功后只从后端重读 Tasks，未核实则清除旧详情并显示
明确未知结果；自动轮询从不调用 ACCEPT。

## 事务与仍未解决的边界

原 T1 锁序与 CAS 不变：SQLite BEGIN IMMEDIATE；PostgreSQL READ COMMITTED household
row lock；当前 session/member/binding → exact Pending/right → actor request → evidence/
plan validation → task/grants/CAS/event → commit。I2 进程锁只保护本地配对、lease 和确认
编号，不取代 SQL 并发约束。测试还用独立 adapter 锁及真实并发 SQL 证明单任务结果。

ACK 丢失与网络中断测试是受控合成故障，不证明任意真实网络分区/主从切换。不能追回
已发送字节；读取到发送、撤权到浏览器发现仍有竞态，沿用 I2/I3 五秒轮询/请求超时。
没有生产锁时限、跨进程 receipt 存储、认证、部署或响应缓存方案。HTTP loopback 不是
TLS，Secure Cookie 的 loopback 支持依赖浏览器，Cookie 不按端口隔离。只运行一个实验，
使用可信独立 profile，不运行不可信本地服务；不得降低 Cookie/CSP 或开放 LAN 兼容。

## Windows PowerShell：一次复制启动

从仓库根目录、已有 Python 3.12 项目环境：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.lock
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
if ($LASTEXITCODE -ne 0) { throw 'Editable installation failed.' }
.\.venv\Scripts\python.exe -u .\prototypes\i4a-workbench\serve_acceptance.py --synthetic-only
```

不运行真实 DB 的 Alembic/register/OAuth，不自动发现 DATABASE_URL 或运行 SQLite。
打开打印 URL，发起请求，在原终端核对编号后输入 `approve 页面编号 clara`。另一个
独立 Chrome/Edge profile 批准 devon，不能用同一 Cookie 的窗口冒充两个身份。

1. Clara 初始 Tasks=3、Devon=2；Pending 中均有新的学校建议、未决问题和风险项。
   Devon 另有私人到访建议，Clara 看不到。旧 I3 未接受建议仅 Clara 可见。
2. 查看学校预览，核对中性内容、共同负责、2036-03-14；取消/Escape 后 Tasks 不变。
3. 明确“确认接受”；共同学校任务只创建一次，Tasks 重新读取后 Clara=4、Devon=3。
   重复点击不能复制任务。风险与未决问题保持可找回，不能确认接受。
4. Devon 可接受其私人到访：只给 Devon 新任务，Clara 的任务和来源权限不变化。
5. 提交中断时不要再点接受；恢复服务可用后点击“核对最近一次接受”。刷新页面也可
   在原 session 的 Pending 页面找到这个入口（核对最新预览；不会把旧任务结果冒充新请求）。无法核实仍 UNKNOWN，不能说已保存或没保存。
6. 检查双语、深浅色、320/390、键盘取消与只读 Tasks。terminal 输入 quit/Ctrl+C 关闭，
   页面应清旧内容。重启是新临时 DB，不恢复历史；Windows 实测仍是合并前人工门槛。

## 验证与独立复审

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_i4a_workbench.py tests/test_household_tasks.py tests/test_i2_local_session.py tests/test_i3_workbench.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
git diff --check
# 已有获准 Playwright/Chrome；不安装模型、下载浏览器或读取真实数据。
$env:I4A_TEST_PYTHON = (Resolve-Path '.\.venv\Scripts\python.exe').Path
$env:I4A_CHROMIUM = 'C:\Program Files\Google\Chrome\Application\chrome.exe'
node .\tests\browser\i4a-acceptance.js --synthetic-only
```

新增测试只用新编案例和 pytest 自有 SQLite/PostgreSQL schema；原 T1 migration、幂等、
CAS、UNKNOWN 和 I3 焦点/撤权回归保持。具体最终计数与工作流结果在 PR 报告，不借用
旧 HEAD 的 CI。I4a 运行路径与新增案例不读取真实家庭数据、Holdout、运行数据库、OAuth/keyring，
不调用任何 AI。

ChatGPT/Muse 请独立检查：客户端是否能伪造计划/成员？确认是否独立且一次？预览与
当前证据/权限是否精确绑定？未知提交是否只能对账？刷新/撤权会否恢复旧详情？
原 I2/I3 是否仍默认拒绝写入？session/receipt 私密性、有限资源与临时清理是否真实？

| 实际虚构连接截图 | 链接 |
| --- | --- |
| Clara 桌面 Pending | [截图](screenshots/i4a/pending-clara-desktop.png) |
| 独立确认预览 | [截图](screenshots/i4a/acceptance-preview-desktop.png) |
| 接受后实际 SQL 待办 | [截图](screenshots/i4a/accepted-tasks-clara-desktop.png) |
| 英文深色 320px | [截图](screenshots/i4a/pending-dark-en-320.png) |

同一浏览器测试加 `--screenshots` 可重新捕获。Windows 字体、缩放、Cookie 与实际操作
仍需人工验收；截图不是生产认证或真实提供方操作证明。

## I4b 后续建议

单独设计服务端授权的编辑预览/确认、允许的负责人候选、任务/权限 revision、精确
actor/request ledger 与 UNKNOWN 对账；不能将本轮固定 recipient 计划改为任意客户端
授权。个人稍后处理/归档/重新打开仍需真正持久化的 per-member 状态、并发版本和
重新授权契约，T1 当前不具备完整 UX1 archive/reopen。先评审这些命令再开放按钮。
生产 OIDC/MFA/TLS、可撤销权限、数据库备份/角色/audit 保护和端到端交付仍是独立前置
门槛。R0–R3、禁用的 Alternative B 与真实数据不得进入任何 AI 的边界均保持不变。
