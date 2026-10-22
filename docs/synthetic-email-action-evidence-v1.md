# Synthetic Email Action Evidence v1

## 预注册契约（先于解释器和评估）

基线 `e31e5ad5f8600b495281f068acd4a8dfd02b985d`。只研究全新英文合成标题。
不读取原 37、Development 60、Holdout 30；不修改生产分类器、Phase 2U、Stage A、
T1/I9、授权或数据库。不执行模型、provider、网络、任务或外部操作。

借鉴 Phase 2U 的严格投影、完整标题语法、原始 Unicode 问号检查、具名步骤范围、
证据引用、未知时 abstain 和零行动权限原则；不导入其评估入口，不读取其样本，
不替换或修改 Calendar 解释器。标题中的完成/成功只是**发送者文字声称**，不是
实际交易、付款、预约或任务完成的验证结果。

### 输入

`synthetic-email-metadata-v1`：严格 dict，必需 `synthetic_only=true`、schema、
provider（gmail/outlook）、record_type=message、notice_kind（service/promotional/unknown）；
可选 subject（最多 360 字符），整体最多 2048 UTF-8 bytes。所有字段类型精确，
未知字段一律拒绝，包括 sender、正文、附件、HTML、URL、账户、权限、安全等级及模型输出。
拒绝控制/格式字符、无效 Unicode、HTML 标记、联系地址、凭据及三层百分号解码/NFKC
检查发现的链接。这里的 notice_kind 是预批准虚构输入的**上下文断言**，不是来源信任、
安全结论或真实邮件分类能力。

输入有效不等于标题受支持。先检查原始与 NFKC 字符的 Unicode QUESTION+MARK/
INTERROBANG，随后引用、非 ASCII、否定/冲突、上下文和完整语法。非 ASCII 字母及
兼容字符保守 abstain，不让 Unicode 混淆产生行动证据。仅 ASCII 英文大小写折叠、
普通空格折叠、允许一个句末句号；不删除分号、日期连字符或任意标点来拼接词语。
不做子串、词干、模糊同义词、当前时间、账户事实或通用自然语言推理。

### 输出

不可变结构记录：state（explicit_outstanding / explicit_completion / informational /
promotional / abstain）、最多两个具名步骤及 reported_outstanding / reported_completed /
reported_failed / reported_cancelled 状态、最多一个完整显式 ISO 日期及角色、固定字段引用、
枚举原因、规则 ID、解释器版本/规则 fingerprint 和精确输入 fingerprint。
每个结果固定要求独立安全/授权及人工核实，authority=none。

日期仅接受 2015–2035 的完整有效 ISO 日历日期，不补年份/月日，不比较今天或制造逾期。
due_date 只绑定明示未履行的具名步骤；event_date、available_date、offer_expiry 和
reported_completion_date 各自独立，不能互相转换。失败/取消不自动产生补救步骤；只有
标题明确提出补救时才记录。完成只作用于该标题中的具名步骤，不清除其他步骤或整封邮件。

### 有限语法

以下是完整标题，大小写和普通空格可规范化；DATE 是上述完整日期。
所有非 offer 语法要求 notice_kind=service；unknown 上下文 abstain。
与上下文冲突时 abstain，而不是把服务义务悄悄归为促销。

| 标题形式 | 证据（均非现实世界结论） |
| --- | --- |
| Invoice paid / Invoice unpaid | invoice_payment 报告完成 / 明示未履行 |
| Payment required | invoice_payment 明示未履行 |
| Autopay successful / Autopay failed | invoice_payment 报告完成 / 报告失败（仅观察） |
| Autopay failed; contact billing to arrange payment | payment 报告失败 + contact_biller 明示后续步骤 |
| Bill available | 信息观察，无义务清除 |
| Invoice payment due on DATE / Invoice payment available on DATE | payment 明示步骤及 due_date / 信息及 available_date |
| Membership renewal due on DATE / Membership renewed on DATE | renew_membership 明示步骤及 due_date / 报告完成日期 |
| Visit confirmed for DATE / Visit cancelled for DATE | 信息/event_date；后者记录 attend_visit 报告取消，不清除其他步骤 |
| Visit cancelled; request refund [by DATE] | 取消观察 + request_refund 明示步骤，日期仅约束 refund |
| Visit cancelled; reschedule visit by DATE | 取消观察 + reschedule_visit 明示步骤及其日期 |
| Service form completed / Service form failed | return_form 报告完成 / 报告失败（仅观察） |
| Payment completed; return the service form | payment 报告完成 + return_form 仍明示未履行 |
| Offer available; offer expires on DATE（promotional） | 优惠日期，无任务步骤或 due_date |

已登记冲突：Invoice paid; payment required、Invoice unpaid; payment complete、
Payment completed; payment failed。它们以及不匹配的复合句不能部分匹配或洗掉后续步骤。
完整词 not/no/never/do not 的否定表达 abstain，不把否定义务声称当成全家清除依据。
问号、引用、未知状态、恶意指令式附加句、相似关键词、没有完整语义的日期都 abstain。
无识别结果不能证明没有义务；uncertain/abstain 不代表已创建 Pending。

### 冻结的新样本

`fixtures/synthetic-email-evidence-v1.json`：75 条，59 个有效输入与 16 个输入安全拒绝，
8 个两案例反事实组。全部新编写；语法与正控共同设计，仅作契约/负例安全探针，
不能作为独立泛化测试或真实世界准确率。正确期望不进入解释器。

- fixture LF SHA-256：`d810937cd5e1b2d0e35f6d1b98d6f85dc05a51cf7b83a135fed8a8bd2c188f13`
- contract canonical SHA-256：`cd0c68e4130f3e0c14ee1900688af9aa03f2053d3e7c0b5954a3162cc4e99c63`

先独立提交契约、样本及其预期，再实现/运行解释器；运行期间不修改标签适配结果。
任何规范或样本变更都必须形成另外审核的版本，不能静默更新 pins。

## 实现、评估和实际结果

预注册提交为 `a1199aa`，在该提交之后才编写解释器和执行评估。冻结 fixture 和
contract pins 未因运行结果变更。解释器为
`src/family_os/_synthetic_email_evidence.py`，只依赖标准库，不读文件、不读时钟、不写状态。
`experiments/synthetic_email_evidence.py` 只加载上面的一个新 fixture；不会导入完整数据集
加载器、旧基准/Development/Calendar 评估器或模型适配器。

- 解释器：`synthetic-email-evidence-e1-065517d552adb8de`
- 规则身份：`065517d552adb8dec3fe4ee88ef32158ae8d4b79d90cafaa9c322fbd29a1eb4b`

规则身份记录登记语法、枚举、界限/规范化契约和引擎修订，不是模型权重或真实检测认证。
输入与输出不可变，输出日期与步骤有交叉约束，due_date 必须属于明确未履行步骤。
拒绝输入无 proposal，以固定 `contract_rejected` 异常表示；评估中与解释器异常、输出
无效及合法 abstain 分开计数。无效输出不伪装成合法 uncertainty，不缩减所选分母。
未知/冲突上下文的 abstain 同时引用 subject 与 notice_kind；所有引用仅为字段名。

实际固定探针结果（无模型，无旧基准输入）：

| 指标 | 结果 |
| --- | ---: |
| 总样本 / 预登记有效 / 输入安全拒绝 | 75 / 59 / 16 |
| 输入安全拒绝正确 | 16/16 |
| 支持语法正控精确符合（包含下列四类） | 22/22 |
| 明示未履行步骤 / 完成声称 / 信息观察 / 促销 | 10 / 5 / 6 / 1 |
| 合法 abstain | 37/59 |
| 误提具名义务步骤 | 0 |
| 错误完成或错误清除风险代理 | 0 |
| 漏掉明确未履行步骤 | 0 |
| 编造或错误绑定日期 | 0 |
| 解释器异常 / 无效输出 | 0 / 0 |
| 反事实两端精确符合 / 完整语义变化 | 8/8 / 8/8 |
| 仅 header state 变化 | 7/8 |

8 组是 paid/unpaid、completed/failed、due/available、肯定/否定、service/promotional、
autopay 成功/失败、预约确认/取消及 offer 上下文。预约对 header 均为 informational，
但具名取消观察不同；不能要求所有安全反事实都变成 action。

37 个 abstain 的原因：negated 5、context_conflict 2、conflicting 3、questioned 4、
quoted 3、unsupported 10、unknown_context 1、missing 2、incomplete_date 3、invalid_date 2、
unsupported_unicode 2。当前未出现与冻结预期不符的案例，但未知措辞仍可能漏掉义务；
这不是支持范围外的正确性证明。

指标定义：误提步骤是 actual outstanding 中存在 gold 不支持的具名步骤；错误清除风险
包括无支持的完成声称，或返回 completion/information/promotion 时漏掉 gold 的未履行
步骤。安全 abstain 不算清除，但计入遗漏明确步骤。所有指标只是结构化文字证据探针，
不意味着真的清除了义务或任务。新增测试注入错误义务和仅保留完成部分的输出，验证
这些错误确实能被统计；结构校验并不拿 gold 或重复运行解释器过滤语义错误。
另报各预期 state、family 分层、拒绝/失败覆盖；零分母的比率为 null。
CLI 显示 `semantic_exact`：59 个合法输入中，state、具名步骤、日期角色/值/作用对象
及 reason 全部匹配的案例数（当前为 59/59），并非只统计 22 个支持正控。
新增 `unsupported_overreach_cases`：gold 为 abstain、实际结构合法却给出任意非 abstain
解释的案例数，包括无支持的信息/促销判断，不限于误提义务。输入拒绝和无效输出另报。
`missed_date_cases`：gold 含显式日期但实际未完整保留其角色、值与作用对象的案例数；
abstain、输入拒绝和解释器/输出失败同样计入。日期错误绑定可同时计入遗漏及
`invented_or_misbound_date_cases`；每项按案例计数，不把多个日期扩大成独立样本。
这两个新增计数当前均为 0；测试注入无支持的信息判断、遗漏/误绑定日期、abstain、
异常和无效输出，独立验证这些错误不会被结构检查或覆盖率隐藏。
正控与语法共同设计、样本相关且规模小，精确符合不构成独立准确率、泛化或真实邮箱就绪。

## 未来接口边界（本 PR 不接入）

- **Phase 2U Calendar：** 仍为独立类型、语法和日期含义；共享安全原则，不共享数据集
  或改写 Calendar 解释器。本 PR 不把日期/状态转换成 Calendar 操作。
- **Stage A：** safety、业务分流、human/action authority 继续独立。未来处理源数据前
  必须先验证当前有效访问权；高风险/未知安全状态由原安全边界保守处理。这里的
  notice_kind 和 synthetic_only 不是来源真实性、安全、访问权或数据确实虚构的证明。
  不得把本模块当成认证、phishing 检测或绕过安全 hold 的清除信号。
- **T1：** 任何接线需另行审核、绑定完整来源/观察 generation、当前 evidence/policy/
  grants/session 版本，再使用原人工预览、独立明确接受、CAS、receipt 和 UNKNOWN。
  本模块的输入 hash 不是 T1 Binding；change/revert 可得到相同 hash，绝不能凭此让旧
  接受重新生效。原有已接受任务与私人来源独立授权，不受本结果自动修改。

`Invoice unpaid` 仅表示标题报告某付款步骤尚未履行，不证明责任人、现时应付、债务
真实性或必须立即付款。`Autopay successful` 同样只记录标题声称，不是银行付款确认。
没有输出步骤不是没有义务，informational/promotional 也不是全家 resolution。
不自动建立 Pending/Task，不自动付款、购物、打开链接、完成任务或修改/隔离邮件。

## Windows PowerShell 离线验收

在已审核分支根目录、已按仓库锁文件准备好 Python 3.12 `.venv` 后整段复制：

```powershell
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [Console]::OutputEncoding
$env:PYTHONIOENCODING = 'utf-8'
$summary = & .\.venv\Scripts\python.exe -m experiments.synthetic_email_evidence --synthetic-only
$code = $LASTEXITCODE
$summary | Out-Host
if ($code -ne 0) { throw '合成邮件证据评估失败；不要使用部分结果。' }
$summary -join [Environment]::NewLine | Set-Clipboard
```

不需要启动 Ollama、数据库、浏览器或任何外部服务，也不需要 AMD GPU。环境缺失时，
先用 `py -3.12 -m venv .venv`，再按 `requirements-dev.lock` 安装，并执行
`.\.venv\Scripts\python.exe -m pip install --no-deps -e .`；依赖安装是单独准备步骤，
可能访问包仓库，评估本身完全离线。

详细诊断保存在 Git 忽略的 `.local/synthetic-email-evidence/<随机运行ID>/report.json`，
只有新样本固定 ID、枚举/步骤、显式日期、字段引用、hash 和统计，没有标题、sender 或
模型输出。每次新建，不覆盖旧结果。先完成序列化，再独占创建同目录
`report.json.tmp`，写入、flush、fsync 并关闭成功后以 `os.replace` 原子发布
`report.json`；写入或发布失败时清理本次临时文件和空运行目录，错误不回显输入。
文件系统故障导致删除本身失败时无法保证清理，可能残留未发布的临时文件；CLI 不报成功。
这保证正常文件系统下不发布半写报告，不声称目录 fsync、断电持久性或恶意本机并发防护。
测试覆盖中途写入、flush/fsync、替换失败及中断清理，旧报告保持不变。

**Fingerprint 不是匿名化或加密。** 这里是无密钥 hash；标题取值空间有限时，可以
通过字典枚举候选输入还原或关联 fingerprint。没有明文标题也不等于不存在信息泄露。
本工具及报告仅限新固定合成数据，**不得用于真实邮件、真实家庭数据或这些数据的
fingerprint**；哈希不能把真实数据变成获准的合成数据，也不能代替授权或隐私保护。
从受信任的本地 checkout 运行；文件检查拒绝 symlink/reparse/多硬链接/非普通/过大
输入，但不声称对抗拥有 checkout 写权限的恶意本机进程并发替换路径。
fixture 使用原 LF 内容身份，Windows CRLF checkout 只在内存规范化后校验，不改文件。

Windows 人工验收：确认 59/16 分离、22 正控、37 abstain、8 个成对结果及剪贴板中文；
打开本地 JSON 检查无案例原文，重复运行只新增目录且诊断相同。不要传入真实邮件，
不要启动旧基准、Development 或 Holdout。Windows/AMD 主机未在 Codex 中实测。

## 测试与审查

新专项覆盖 75 个登记案例、Unicode/问号/否定/子串、附加指令、日期不补全及角色隔离、
完成与后续步骤共存、未知/额外字段与权限字段拒绝、不可变输出与伪造结果、固定身份、
精确分母、注入错误的指标敏感性、纯导入无 I/O/执行、实际 CLI 全依赖文件白名单、
独占报告创建、无正文输出及 CRLF 身份。旧 Calendar 纯函数单元测试单独回归，未将其
数据集作为新解释器输入。完整仓库 CI 的旧冻结数据完整性测试保持原样，不属于本
原型的调用路径，不能据此声称新原型评估过那些冻结基准。

```powershell
& .\.venv\Scripts\python.exe -m pytest -q tests/test_synthetic_email_evidence.py tests/test_calendar_action_evidence.py
```

最终 HEAD、专项及完整 SQLite/PostgreSQL 16 CI 实际数量和链接记于 PR 描述。
保持 OPEN / UNMERGED，等待 ChatGPT、Muse 独立审查和产品所有者 Windows 验收。

## PR #105 合并后的 Windows 最小兼容修复

基线 main 核实为 `5360ffb71dd532a2124d01c26691bc4fd7262006`，无更新提交。
本节“旧邮件实验”仅指 PR #104 的 **75 条合成案例**，绝不是 Legacy37。
PR #105 已确认 Windows Python 3.12 的路径 lstat 可将 birthtime 放入 ctime，而句柄
fstat 使用 ChangeTime；参见[原生诊断与 CPython 源码依据](synthetic-email-wording-challenge-v1.md#windows-原生文件身份兼容性增量)。
旧 `read_fixture()` 的七字段跨 API 比较存在同类兼容风险，但此前**未在 operator 的
笔记本上复现旧 evaluator 故障**，不能将 wording 的现场诊断冒充旧实验的用户复现。

本修复独立保留几行比较逻辑，不引入公共模块，不导入 wording evaluator/loader：

- Windows 跨 API 精确比较 dev、ino、mode、nlink、size、mtime_ns，无舍入/时间容差。
- lstat 前后七字段全部比较；fstat 前后七字段全部比较，包含各 API 自己的 ctime。
- 非 Windows 跨 API 也继续比较七字段；Windows 不是整体跳过检查。
- 固定路径、父目录/文件 symlink/reparse/硬链接/非普通文件拒绝、读取上限和 LF hash
  pins 全部保留。Hash 不能替代路径和对象身份检查，身份不符不吞异常。
- 不改解释器、规则、两份冻结 fixture/gold/reference、pins、评分、产品接口或数据库。
  报告发布/清理、字段最小化及可信 checkout 的威胁模型也不变，不扩大安全承诺。

### 原生复现控制与回归

Windows 专属测试仅在临时 PR #104 合成 fixture 副本上调用 SetFileTime，令创建时间
与 ChangeTime 明确不同。测试首先确认只有 ctime 跨接口不同、两种 API 各自稳定，
并证明**原七字段跨 API 谓词拒绝**，然后通过实际 `read_fixture()` 成功读取 75 条。
这是原生 Windows 强制构造的合成兼容复现，不是 operator 笔记本的旧 evaluator 故障复现。
Linux 明确跳过这一项；其余两项 Windows 专属测试属于已有 wording 实验。

额外回归逐项拒绝六个其他跨 API 字段不符、同 API 的 ctime 变化、同内容文件替换和
读取期间变化。原有指标错误注入、发布/清理、执行与文件访问隔离断言全部保留。
测试源码/JSON 文本读取明确 UTF-8；CRLF 准备先归一 LF 再转 CRLF，避免 Windows
checkout 的 CRLF 被重复转换成 CRCRLF。这不是放松 hash 或修改冻结文件。

现有 `windows-wording` 受限 matrix 在 Python **3.12.0 / 3.12.10** 执行两份邮件专项
测试（不访问 Calendar 案例或旧 split），保留 wording 的两个原生测试及真实 CLI
双次检查，追加 PR #104 CLI 两次检查：结果相同、目录不同、第一份报告字节不变、
无临时文件。公共诊断工具仍只允许其原来两个固定文件，未加入 PR #104 fixture 入口。
SQLite/PostgreSQL16 原有完整 jobs、触发器、permissions 和 concurrency 均不变。
完整仓库本来已有的数据集完整性回归不是本实验入口的输入，也不是手动 Holdout 评估。

专项命令（替换 Python 可执行文件为现有环境）：

```powershell
py -3.12 -m pytest -q tests/test_synthetic_email_evidence.py tests/test_email_wording_challenge.py
```

正常旧实验固定结果仍应为：75 所选 / 59 合法 / 16 安全拒绝，semantic_exact 59/59，
支持正控 22/22，abstain 37/59，反事实成对精确符合 8/8，错误指标全部维持 0。
wording 仍为 36 / 24 清晰 / 12 歧义，清晰完整/部分/abstain=0/0/24，未履行步骤遗漏
12/12，日期遗漏 16/16。原契约符合不是邮件真实世界准确率。

### operator 的 Windows 复验

在新 PR 的已审查 checkout 根目录，沿用现有 Python 3.12 环境：

```powershell
& {
    [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
    $OutputEncoding = [Console]::OutputEncoding
    $env:PYTHONIOENCODING = 'utf-8'
    1..2 | ForEach-Object {
        py -3.12 -m experiments.synthetic_email_evidence --synthetic-only
        if ($LASTEXITCODE -ne 0) { throw '旧邮件合成实验失败；不要使用部分报告' }
        py -3.12 -m experiments.email_wording_challenge --synthetic-only
        if ($LASTEXITCODE -ne 0) { throw '措辞挑战失败；不要使用部分报告' }
    }
}
```

每份实验的两次目录应不同，旧报告不变，无 `.tmp` 残留；指标按上述核对。
不需要模型/GPU，不读取账户或真实家庭数据。最终 HEAD、原生 Windows 强制复现/CLI
日志、完整 CI 数量及所有 skips 记录在本兼容修复 PR 的 Validation 区。
PR 保持 OPEN / UNMERGED，待 ChatGPT 审查、Hanabi 独立复审及 operator 笔记本验收；
只有 operator 可以手动合并。
