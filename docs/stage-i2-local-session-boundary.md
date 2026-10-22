# I2 — 本地安全会话与同源服务 / Local fictional session lab

Contract: `i2-loopback-fictional-session-v1`. Based on merged I1 PR #85;
main `0c9b4d5285ac41af45163efb31a42d8c911e62d1`.
This identifies an internal contract, not a deployed authentication version.

## 实际交付与范围

新增一个显式启动的、短期虚构数据浏览器会话测试环境。它不是另一个家庭后台，
不是生产登录，不是家庭工作台已接通的声明。只测试启动、终端批准、当前会话检查、
取消与注销。**没有 T1 任务、Pending、来源、邮箱或安全审核数据 API。**
原有 H1/UX1/外观模式、file:// 演示及 `connect-src 'none'` 均不变。

沿用 [I1 能力审查](stage-i1-safe-read-connection.md)、
[G2a](v0-1-durable-household-authorization.md)、
[G2b2](v0-1-session-service-boundary.md)、
[G3a](v0-1-oidc-login-foundation.md)、[G3b](v0-1-fictional-read-api.md) 与
[T1](v0-1-durable-household-tasks.md)。不部署 G3b，也不改变任何既有服务语义。

## 信任边界与数据流

```text
明确 --synthetic-only
  → 新建自有临时 SQLite + 显式连接上的迁移（跳过 env.py）
  → 固定虚构 Willow 家庭、Clara/Devon 两位平等成员及 identity bindings
  → Waitress 仅监听 127.0.0.1 的 OS 分配端口
  → 同源固定静态页面 POST /api/start
  → 随机 HttpOnly 配对 Cookie + 无授权能力的公开请求编号
  → 启动终端核对编号，逐次明确批准固定虚构成员
  → 新生成签名断言 → 同一 OfflineIdentityVerifier 签名/nonce/profile 验证
  → 原有 SessionService.establish（当前 binding/member、真实 SQL、actor audit）
  → 当前浏览器凭精确配对 Cookie 领取一次 Secure/HttpOnly 会话 Cookie
  → POST /api/session 每次 SessionService.resolve，重新检查当前持久化状态
  → POST /api/logout 原有 SessionService.logout + CAS / UNKNOWN 语义
```

终端是**可信虚构配置操作者**，不是已验证的家庭用户身份或生产认证。浏览器没有
成员选择器、身份 URL 参数、token 输入、静态 bearer 或 proof 输入。公开请求编号
仅帮助人在终端核对当前浏览器，单凭编号不能领取 Cookie，也不能从 HTTP 批准身份。
批准时生成的密钥、断言和 bearer 不输出；姓名只能来自终端批准的两个固定虚构成员。
两成员使用同一个家庭数据库，各自独立会话，不获得默认 superuser。

不从会话调用 `harness_context()`，不复制权限引擎。I2 不配置任何来源/任务/操作授权；
有效 session 仅证明当前虚构 binding/member 可用，不意味着源访问、安全 reviewer、
reconciliation、任务发布/编辑或 R2/R3 权限。生产 OIDC、MFA、邀请与恢复仍未实现。
此处的本地签名断言是明确批准的测试机制，不是把 G3a 离线流程升级成公开登录。

## 服务与请求契约

使用固定开发依赖 Waitress 3.0.2（可选依赖 `local-session-demo`，lock 精确固定），
而非临时目录服务器或手写 HTTP parser。没有选择生产框架。不能将此 runner 迁移到
生产或开放到 LAN。启动没有 host、port、DB URL、任意 fixture 或身份参数。

| 资源 | 允许行为 |
| --- | --- |
| `GET /`、`/app.js`、`/style.css` | 仅固定三份本地资源；无目录、仓库、Python、H1 fixtures 或 DB 暴露 |
| `POST /api/start` | 空 JSON `{}`；无现存 I2 Cookie；创建待批准浏览器配对 |
| `POST /api/session` | 精确配对 Cookie 领取一次会话，或现有会话 Cookie 检查当前 session |
| `POST /api/cancel` | 仅对应配对 Cookie；取消领取，移除其本地 lease，不声称数据库注销成功 |
| `POST /api/logout` | 仅当前 session；先 resolve 取得当前 revision，再原有 logout；独立于 peer session |

API 都要求精确 `Origin: http://127.0.0.1:实际端口`、
`Sec-Fetch-Site: same-origin`、`X-Samas-Intent: local-session`、
`Content-Type: application/json`、Content-Length 2 和精确 `{}`。
Origin/Fetch Metadata 为浏览器控制的边界，常量自定义头通过禁止 CORS 的预检提供额外
CSRF 防线，不是假装秘密 CSRF token。跨站/同站不同 origin、null/missing Origin、
普通表单、预检、query、client Authorization、代理头、内容编码和未知路由拒绝。

所有请求必须来自字面 `127.0.0.1`，Host 必须精确匹配绑定端口；localhost、其他 IP、
DNS 别名、伪造/合并 Host 均不接受。无代理信任，不提供转发/隧道配置。服务只接受
本机连接；防火墙、浏览器/OS 管理员和恶意反向代理不在此实验的隔离能力内。
不要转发端口，不要放到云开发预览或公共托管。

所有 API 输出只含固定 state、公开请求编号或当前虚构 member，无秘密、session ID、
hash、binding、来源或权限清单。应用拒绝统一为 400 `local_session_unavailable`，
没有身份存在性/驱动详情。Waitress 自身的 HTTP 语法/资源拒绝可能为 400/413/431；
UI 都按失败处理，不依赖这些状态猜测授权。注销 UNKNOWN 是明确的 `state: unknown`，
绝不显示“已注销”。不开放自动对账、blind retry 或 bearer 恢复接口。

响应统一 no-store/no-cache、nosniff、no-referrer、DENY framing、same-origin CORP/COOP。
CSP 仅当前三份资源与 `connect-src 'self'`，无 inline script/style、CDN、CORS、
外部图像/追踪、URL 获取或生产 API。浏览器只请求固定相对路径，禁止重定向；
不加载 H1 的浏览器权限模型作为服务端授权。

## Cookie、时限与失败

两个 `__Host-` Cookie：配对秘密与最终 opaque session bearer，均为
`Secure; HttpOnly; SameSite=Strict; Path=/`，无 Domain、无 JS 可读副本、无 localStorage/
sessionStorage。配对 hash 索引只存在进程内；session bearer 仅存 G2b2 原有 SHA-256
verifier 于 SQL。为一次领取，批准后 bearer 暂存在 repr 隐藏的内存配对对象内。
取消、过期、失败或退出丢弃本地领取能力。已经提交但未领取的 session 可能成为孤儿；
不声称回滚或恢复其秘密，整个自有临时数据库会在服务退出时删除。

重要限制：使用 **HTTP 字面 loopback，不是 TLS**。当前实际 Chromium 验证了该地址的
Secure Cookie 例外及 HttpOnly/SameSite；没有添加 insecure-origin flags、忽略证书错误
或关闭 CSP。没有这个浏览器支持就无法领取会话，**不得降低 Secure 或 HttpOnly 回退**。
Edge/Chrome Windows、Firefox、Safari 等尚需对应环境验证，不宣称跨浏览器都已通过。
生产必须正常 HTTPS 和真实登录审查，不能沿用 loopback 例外。

Cookie **不按端口隔离**。只运行一个 I2，并且不要同时运行不可信的本机 web 服务；
同机恶意进程、浏览器扩展、DevTools 操作者、窃取/复制 bearer 或同源脚本失陷不受此
测试机制防护。拥有相同 bearer 的人就是同一 bearer 持有者；不能声称能识别盗用。
真实两人身份必须由未来的真实认证建立，不能将终端批准用于生产。

- 配对 120 秒，单次领取；整个运行最多 8 次 start，阻止无限状态分配。
- 浏览器 session 额外本地 lease 为 600 秒；服务最多运行 1800 秒。这不是修改 G2b2
  原有 DB 绝对/idle 策略，而是实验 runner 的更短使用上限；两者任一失效就拒绝。
- 时限用 monotonic；回退或过期拒绝。SQL session 时钟仍由原服务控制。
- 两个 worker、8 个连接、8 KiB 请求头、256 bytes 请求体、5 秒闲置 channel timeout；
  浏览器请求 5 秒超时。不是生产限流或任意 DB 操作硬超时保证。
- 单进程锁仅保护配对/lease 对象，不替代 SQL CAS、当前成员/绑定或 audit。
- 接口错误不返回旧 active body，已知注销 UNKNOWN 也丢弃本地 lease 并清 Cookie；
  不能据此断言数据库肯定未提交/肯定撤销。真实提交后丢失 ACK 的注入测试保留 UNKNOWN。
- 页面每两秒重新检查状态；每次请求先清除旧显示，失败不显示旧成员，不填 H1 数据。
  pagehide 清显示，BFCache 恢复重新检查。断网/撤销到发现存在轮询间隔和请求超时，
  不声称能追回已发送信息或解决最终读取到响应交付的竞态。

quit、EOF、Ctrl+C 或运行时限关闭 listener、worker 和本服务 socket map，随后释放 engine
并删除自有 TemporaryDirectory。异常只显示通用错误；不打印 Cookie、请求、原始异常或
数据库 URL。强杀/断电不能保证清理临时目录；它只含新建虚构数据，绝不搜索/清理其他 DB。
程序不读取 DATABASE_URL、TEST_DATABASE_URL、运行 SQLite、keyring 或任何真实账户。

## Windows PowerShell：启动、配对、关闭

从仓库根目录、已有 Python 3.12 项目环境执行一次：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.lock
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
.\.venv\Scripts\python.exe -u .\prototypes\i2-local-session\local_session.py --synthetic-only
```

无需 Alembic 命令、DATABASE_URL、OAuth、管理员权限或导入证书。不要启动/迁移真实 DB。

1. 浏览器打开终端显示的 `http://127.0.0.1:随机端口/`，不是 file://。
2. 点击“发起测试会话请求”，核对页面的公开请求编号。
3. 在仍运行的原 PowerShell 终端输入 `pending`，再输入
   `approve 页面请求编号 clara`。这是人为批准虚构身份，不是输入真实令牌。
4. 浏览器显示 Clara。使用另一个真正独立的浏览器 profile（例如 Edge 与 Chrome），
   对其新编号输入 `approve 页面请求编号 devon`。多个 InPrivate 窗口可能共用 Cookie，
   不算两份独立身份。
5. 注销 Clara，Devon 仍可检查自己的会话。尝试取消配对，确认不再可以领取。
6. 终端输入 `quit` 回车关闭，或 Ctrl+C/EOF。页面随后显示不可用，不回填离线成员。
   新一轮测试重新运行同一启动命令，得到全新 DB/密钥/端口；旧 Cookie 不恢复身份。

原 file:// 离线界面按原方式打开，互不连接。不要把测试页面宣传为已接入家庭账号。

## 验证与 I3 接口边界

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_i2_local_session.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

测试采用 pytest 自有临时 SQLite / PostgreSQL 独有 schema（CI PostgreSQL 16）；
launcher 自身始终只建自有临时 SQLite。新建固定 fiction，不读取冻结 Development/Holdout。
专项覆盖 Host/Origin/CSRF、真实 HTTP loopback、路径白名单、独立成员会话、盗用式身份
参数拒绝、当前持久化撤销、绝对/idle/本地过期、并发批准、取消、上限、UNKNOWN、
提交后 ACK 丢失、日志/DB/输出秘密检查、无外联和临时资源清理。

独立实际浏览器检查（需已有 Playwright/Chromium，不安装/下载浏览器）：

```powershell
# 使用本机已安装且获准的 Playwright 模块与 Chromium 路径。
$env:I2_TEST_PYTHON = (Resolve-Path '.\.venv\Scripts\python.exe').Path
$env:I2_CHROMIUM = 'C:\Program Files\Google\Chrome\Application\chrome.exe'
# NODE_PATH 由本机已安装 Playwright 所在 node_modules 设置；不要复制云环境路径。
node .\tests\browser\i2-sessions.js --synthetic-only
```

Linux Chromium 实际检查使用正常 CSP 和真实 Cookie，包含两个独立 context、
跨来源预检/简单 POST、注销隔离、JS 无法读/覆盖秘密、无浏览器存储、320/390 宽度及
服务退出后的清显示。Windows 真实浏览器仍是人工门槛。实际测试数与双数据库工作流
链接在 PR 描述，不将这些实验解释成生产认证证明。

I3 仍需单独评审：在同一受控本地 origin 增加只读 Tasks GET，映射当前 Cookie 到
原有 `TaskService.tasks()`，显式序列化 TaskView/Page，每次在服务端重新授权，且
不把客户端 member 当身份。详情/history 若加入也必须独立权限验证。现有 Samas UI
需要明确连接模式，服务错误不能 fallback；仍不开放 Accept/Edit、Pending archive/
reopen 或邮箱操作。写入以后另行绑定能力、确认、revision、精确请求幂等与 UNKNOWN
对账。R0–R3 不变，Alternative B standing consent 继续禁用。

审查重点：终端与浏览器边界是否明确；Cookie 是否真正 HttpOnly/Secure；是否仅有
当前会话检查而没有隐含权限；配对、失败和 UNKNOWN 是否会重复建立/泄露会话；
服务是否仅访问自有临时数据库；浏览器/本机攻击与 TLS 的限制是否诚实。
PR 保持 OPEN/UNMERGED，等待 ChatGPT、Muse 和 Windows 人工验收。

后续 [I3 只读连接](stage-i3-readonly-task-workbench.md)在独立明确模式下复用这些边界；
默认 I2 启动命令仍然只有会话测试，不开放任务数据。
