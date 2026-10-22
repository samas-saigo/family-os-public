# 冻结解释器的新合成措辞挑战 v1

## 预登记计划（运行前冻结，后续不改）

基线 main：`33c2e33ad1345483a0d09bc2a895593e88c8fe28`（PR #104 合并）。
开始前 fetch 确认 main 没有新增提交。本实验不修改解释器、规则、旧 evaluator、
原有 fixture/gold/pins 或产品接口。先独立提交并推送本计划与新 fixture，核实远端
SHA 后，才实现 evaluator 并首次调用解释器。冻结提交身份将在下方实施记录中追加。

### 身份

- 解释器：`src/family_os/_synthetic_email_evidence.py`。
- 解释器文件 LF SHA256：`44e391f3748799c8552703cee92d77fd84166a23e04006f9c3876262c2b0d025`。
- 版本：`synthetic-email-evidence-e1-065517d552adb8de`。
- 规则指纹：`065517d552adb8dec3fe4ee88ef32158ae8d4b79d90cafaa9c322fbd29a1eb4b`。
- 新 fixture：`fixtures/synthetic-email-wording-challenge-v1.json`。
- Fixture LF SHA256：`067b041f142ce9892509f7024ff5d94c6a4a34be2fdd59d4d2e91a408a44b019`。
- 输入保持 `synthetic-email-metadata-v1`；只用既有 action/status/date 类型。
- 文件身份仅在内存将 CRLF 转 LF 后核对，支持 Windows checkout，不改写磁盘文件。

### 样本与标注

12 个固定场景组，每组 2 条清晰自然改写和 1 条歧义/问句/冲突，共 **36** 条。
明确固定分母：**24 清晰、12 歧义、12 组**。其中 12 条清晰标题含明示未履行步骤，
8 条含具名完成声称，16 条含一个显式日期；这些子集可能重叠，不得相加成独立样本。
场景涵盖付款日期、自动付款完成/失败及联系账单方补救、账单通知、续费待办/完成、
预约取消后的退款/改约、表格完成、付款完成但表格未交、促销日期及预约通知。

两条清晰改写的参考证据相同，来自标题的自然语言含义，不按解释器语法标注。
没有匹配旧句式不构成 gold abstain；清晰 gold 不包含解释器的 reason/rule ID。
歧义案例只期待 abstain，不补出行动、责任人或日期。参考 evidence 只是标题中的
文字声称，不证明实际家庭义务、付款成功、预约完成或安全。无需/未知日期不补全。
新样本人工编写，没有复制旧案例；Legacy37、Development60、Holdout30、Calendar
案例均不作为编写、调参或评测输入。作者接触过原有限语法契约，因此这是
**实现冻结后的新合成措辞挑战，不是盲测、独立作者评估或统计独立样本**。
组内高度相关；支持低覆盖结论，但不能外推真实邮件准确率。

### 评分契约与分母

先验证输入、执行、结构/来源身份；结构验证绝不根据 gold 再运行或修正解释器。
传给解释器的只有原 schema 投影，不传 case ID、组、variant 或 reference。

- 所有所选案例 36、清晰 24、歧义 12 均固定保留，按执行 status 分层。
  输入拒绝、异常、无效输出各自计数；不能计为 abstain 或从分母删除。
- 清晰 **完整匹配**：实际 state、具名 `(action,status)` 集合、日期
  `(role,value,action)` 集合与 reference 完全一致。不要求 reason 相同。
- 清晰 **部分匹配**：合法非 abstain、非完整匹配，且至少保留一个正确步骤或日期。
  state 相同但具体证据全部错误不算部分匹配。另报清晰非 abstain 完全不匹配。
- 清晰 **abstain** 仅统计真正合法的 abstain。完整/部分/abstain/非 abstain 不匹配/
  输入拒绝/异常/无效输出构成清晰分母的互斥覆盖。部分匹配不等于安全或正确。
- 明示未履行步骤遗漏：报告受影响案例数及缺失步骤数，以 12 个有该证据的清晰
  案例为案例分母。abstain、拒绝、异常、无效输出全部视为未保留对应步骤。
- 无依据步骤：任何 actual `(action,status)` 不在 reference 中；分别报告所有多余
  步骤、无依据 outstanding 与完成声称的案例数及步骤数。歧义 gold 无具体步骤。
- 歧义具体化越界：合法输出不为 abstain；即使只错误给出 information/promotion，
  没有步骤也计入。歧义 abstain 另报，分母始终 12。
- 日期遗漏：预期日期三元组未保留，包括 abstain/失败。编造日期值：actual 日期值不在
  reference。角色/作用对象错误：值相同但 role/action 不匹配。各按案例数与日期数
  报告；遗漏与错误日期可重叠。日期遗漏案例分母 16；actual 越界按所选 36 分母。
- 错误清除风险代理：合法的 completion/information/promotion 漏掉 reference outstanding。
  **安全 abstain 只算覆盖不足/步骤遗漏，绝不称为错误完成、错误清除或实际清除了任务。**
- 各组独立报告 selected=3、clear=2、ambiguous=1、上述指标和两条改写均完整匹配
  的组数（分母 12）。不合并旧实验分母，不把 36 当独立随机抽样或计算置信区间。
- 零分母比率为 null。禁止用标签或重试修复输出来计成功；标签发现问题只记录问题，
  不在冻结后改标签重跑。故障注入仅用于测试计数器，不计入正式实验结果。

### 运行与输出边界

新增独立手动 evaluator，严格固定新 fixture 路径，无任意路径、网络、模型或 DB 入口。
不导入旧 evaluator/loader。数据读取仅限该新 fixture；允许读取固定解释器文件核对
代码 hash（不是另一个数据集）。先检查全部身份/结构，再调用解释器。
新输出目录仅限 Git 忽略的 `.local/email-wording-challenge/<随机ID>/report.json`。
报告只留案例 ID、有限组/variant、reference/actual 枚举证据、诊断与聚合及版本身份；
不保存标题、sender、正文、URL、凭据或输入 fingerprint。即使没有明文，fingerprint
也是可被字典枚举的无密钥 hash，不是匿名化或加密，绝不能用于真实数据。
先序列化，独占临时文件，完整写入/flush/fsync/关闭后同目录原子替换发布；失败清理
自己的临时文件及空运行目录，不覆盖旧报告。删除本身失败可残留未发布临时文件，
不得宣称成功。不是断电持久性、恶意本机并发防护或生产数据授权。

CLI 只打印简短中文分母、覆盖/错误计数、组级结果和本地报告路径，不打印案例正文。
后续实现不接入 Pending/Task/产品流程，不产生任何家庭状态或外部写入。

### 预定验证

固定 fixture 与解释器身份、输入/字段严格检查、无 gold/ID/组进入解释器；
注入错误步骤/完成/日期/歧义具体化及部分匹配；拒绝/异常/无效输出完整分母；
实际 CLI 文件访问 allowlist（含整个调用链）；原子发布、重复运行隔离、半写/发布失败
不报成功与清理；中文摘要/安全错误。新入口不运行旧数据或 Calendar 数据。
既有仓库完整测试仍照常运行（它们已有的数据集完整性测试不是本实验输入），执行
SQLite/PostgreSQL16 CI、pip check、git diff --check。无 GPU/Ollama/真实数据依赖。

## 实施记录（冻结后追加）

待远端冻结提交核实后填写，不修改以上预登记计划或样本。

### 已核实冻结与实现顺序

预登记提交：`80741385760c87d6c7b0dc1f0d514d8b1be96051`。
`git push -u origin feat/frozen-email-wording-challenge` 后以 `git ls-remote` 核实
远端同一 SHA，才编写/运行 evaluator。首次运行没有使用旧 evaluator 或旧 fixture。
后续实现提交将在最终验证记录中列明。冻结后没有改样本、reference、解释器或规则；
未发现需改标注的问题。如后续发现，必须作为版本问题报告而非就地改标签。

### 实际新措辞覆盖结果

| 项目 | 结果 | 分母/含义 |
| --- | ---: | --- |
| 所选 / 清晰 / 歧义 | 36 / 24 / 12 | 固定不缩减 |
| 合法输出 | 36 | 所选 36 |
| 清晰完整匹配 | 0/24 | state + 具名步骤 + 日期全部匹配 |
| 清晰部分匹配 | 0/24 | 至少保留一个正确具体证据，且非完整 |
| 清晰 abstain | 24/24 | 全部 reason=unsupported |
| 歧义 abstain / 越界 | 12/12 / 0/12 | 11 questioned、1 unsupported |
| 明示未履行步骤遗漏 | 12/12 | 12 个步骤；全部因 abstain 未保留 |
| 日期遗漏 | 16/16 | 16 个日期三元组；全部因 abstain 未保留 |
| 无依据步骤 / 完成声称 | 0 / 0 | 所选 36 的错误案例数 |
| 编造日期 / 角色或对象误绑定 | 0 / 0 | 所选 36 的错误案例数 |
| 错误清除风险代理 | 0 | abstain 不是错误完成或清除 |
| 输入拒绝 / 异常 / 无效输出 | 0 / 0 / 0 | 不从分母移除 |
| 两改写均完整匹配 / 均 abstain 的组 | 0/12 / 12/12 | 相关场景组，不是独立样本 |

| 场景组 | 清晰 abstain | 歧义 abstain | 未履行步骤遗漏案例 | 日期遗漏案例 |
| --- | ---: | ---: | ---: | ---: |
| payment_due | 2/2 | 1/1 | 2 | 2 |
| autopay_complete | 2/2 | 1/1 | 0 | 2 |
| autopay_remedy | 2/2 | 1/1 | 2 | 0 |
| bill_notice | 2/2 | 1/1 | 0 | 0 |
| renewal_due | 2/2 | 1/1 | 2 | 2 |
| renewal_complete | 2/2 | 1/1 | 0 | 2 |
| cancel_refund | 2/2 | 1/1 | 2 | 2 |
| cancel_reschedule | 2/2 | 1/1 | 2 | 2 |
| form_complete | 2/2 | 1/1 | 0 | 0 |
| payment_plus_form | 2/2 | 1/1 | 2 | 0 |
| promotion_expiry | 2/2 | 1/1 | 0 | 2 |
| visit_notice | 2/2 | 1/1 | 0 | 2 |

结论：冻结解释器对这批自然改写没有保留具体证据，完整句式语法的覆盖限制非常明显。
这不是“36 条全对”：歧义上安全 abstain 与清晰案例上完全丢失可表示的文字证据必须
分开看。没有错误具体化也不能证明通用安全、真实世界准确率或产品就绪。
`unsupported` 是实际规则轨迹的有限原因，不是在推测模型内部推理；本实验无模型。
现有解释器不理解一般英文，不能把其 abstain 用作没有义务的证明。这里只测覆盖，
没有新增规则、AI、任务路由、Pending 创建或人工审核系统，也不提出自动执行策略。

### Windows PowerShell 离线验收

从已审查分支根目录运行；沿用仓库 Python 3.12 `.venv`，不需额外依赖/服务：

```powershell
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [Console]::OutputEncoding
$env:PYTHONIOENCODING = 'utf-8'
$summary = & .\.venv\Scripts\python.exe -m experiments.email_wording_challenge --synthetic-only
$code = $LASTEXITCODE
$summary | Out-Host
if ($code -ne 0) { throw '措辞挑战失败；不要使用部分报告。' }
$summary -join [Environment]::NewLine | Set-Clipboard
```

预期显示固定 36/24/12、清晰 0 完整/0 部分/24 abstain、未履行遗漏 12/12、
日期遗漏 16、无依据/越界/失败计数 0。连续运行两次应生成不同目录，原报告不变。
详细诊断是本地 Git 忽略文件，CLI 不打印标题。无任意输入路径、旧数据集或模型参数。
若缺少环境，按 README 准备 `.venv` / `requirements-dev.lock`；安装依赖是单独的
包仓库访问准备步骤，不是本实验运行的一部分。绝不导入真实数据或 fingerprint。
Windows 原生执行仍待产品所有者验收；本 PR 不声称已在 AMD 主机运行。

### 验证与边界

新测试覆盖 frozen hash/version/rule identity、36/24/12 和组级分母、gold/ID/组隔离，
测试专用参考输出控制（不计入实验结果）、部分证据/遗漏/多余步骤/完成声称/日期错误/
歧义具体化注入、投影拒绝/异常/无效输出、错误 provenance、CLI 全调用链文件 allowlist、
symlink/reparse/多硬链接/过大输入、CRLF、无源文本/输入 hash 的最小报告、完整原子发布、
重复运行、半写/flush/fsync/close/replace/中断失败清理、错误不报成功和无网络/模型。

完整仓库 CI 依然执行原有数据集完整性回归；没有为新 evaluator 调用这些 loader，
没有进行任何 Holdout 手动评估或模型推理。只新增隔离实验文件/测试/文档及 gitignore。

实现提交：`dca01b3c1595e83d04b22584d451b2f4635563a1`（位于冻结提交之后）。
专项验证：新挑战测试 63 项 + 原邮件实验测试 210 项，共 **273 passed in 0.66s**。
CLI smoke 产生上述实际结果，pip check 通过，git diff --check 通过。
最终 HEAD 的完整 SQLite/PostgreSQL16 CI 数量、日志链接及审核门槛记录在 PR Validation
区；不是以实现提交或旧 PR 的 CI 代替最终 HEAD。Windows 操作由所有者随后执行。

## Windows 原生文件身份兼容性增量

原生用户诊断确认 Python：
`3.12.10 (tags/v3.12.10:0cc8128, Apr 8 2025, 12:21:36) [MSC v.1943 64 bit (AMD64)]`。
没有根据错误堆栈猜测字段；先推送元数据诊断，再取得两文件的实际逐字段结果。
诊断不打印文件原文、凭据、绝对用户目录；设备/文件 ID 只在本机诊断中输出，不复制到本文。

| 字段 | 解释器 .py：路径 lstat vs 句柄 fstat | 新 fixture .json：路径 lstat vs 句柄 fstat |
| --- | --- | --- |
| st_dev | 相同 | 相同 |
| st_ino | 相同 | 相同 |
| st_mode | 33206 / 33206 | 33206 / 33206 |
| st_nlink | 1 / 1 | 1 / 1 |
| st_size | 15634 / 15634 | 22835 / 22835 |
| st_mtime_ns | 相同 | 相同 |
| st_ctime_ns | 1792541681696931700 / 1792541681697930500 | 1792541681638152000 / 1792541681639155900 |
| 同 API 读取前后 | lstat 稳定，fstat 稳定 | lstat 稳定，fstat 稳定 |
| LF hash | 匹配冻结值 | 匹配冻结值 |

差异是 ctime 的跨 API 语义，不是文件 ID、大小错误或 hash 失败，不是凭约 1ms 差异
推断时间舍入误差。CPython 3.12.10 的
[`win32_xstat`](https://github.com/python/cpython/blob/v3.12.10/Modules/posixmodule.c#L2142)
把 birthtime 复制到 ctime，保留路径 stat/lstat 的历史语义；
[`_Py_attribute_data_to_stat`](https://github.com/python/cpython/blob/v3.12.10/Python/fileutils.c#L1117)
及 [`_Py_fstat_noraise`](https://github.com/python/cpython/blob/v3.12.10/Python/fileutils.c#L1233)
的句柄路径使用 ChangeTime，未做同样覆盖。不能将这两个 ctime 当作相同字段含义。
首次 Windows CI 的 Python 3.12.0 / 3.12.10 两文件七字段恰好全相同，说明普通新建
checkout 可能让 birthtime/ChangeTime 重合，不能据此否认用户现场。

### 最小修复及保证

只修改新 evaluator 的文件身份比较，不改解释器/规则/fixture/reference/pins/指标：

1. 跨 API 仍精确比较 dev、ino、mode、nlink、size、mtime_ns；不舍入、不加容差。
2. Windows ctime 不跨 API 等同比较，但 **lstat 前后七字段全部相同**，且
   **fstat 前后七字段全部相同**，包括各自的 ctime。没有全部忽略 ctime。
3. 非 Windows 继续要求跨 API 的七字段全部相同。
4. 固定路径白名单、父目录/文件 symlink/reparse/硬链接/非普通检查、大小上限、
   打开句柄与路径 ID 绑定、读取稳定性及 LF hash pins 保持；hash 不是路径安全替代。
5. 不增加真实数据/授权承诺，仍假设可信 checkout；不声称抵御有目录写权限的恶意
   本机进程或已经交付的数据撤回。这是兼容修复，不是新的安全策略或生产入口。

旧 `experiments/synthetic_email_evidence.py` 的 `identity` 和 `read_fixture` 存在相同的
lstat/fstat 七字段直接比较，因而有同类兼容风险。这是代码检查证据，不是本轮运行
旧数据集得到的结论；旧 evaluator 未改动，应另行评审其修复范围。

### 原生验证与用户复验

`windows-wording` 是范围受限的 Windows Python **3.12.0 / 3.12.10** CI matrix：
仅诊断这两个固定文件、运行新实验专项测试，以及通过真实 CLI 子进程连续运行两次，
核对结果相同、目录不同、第一份报告字节不变、无临时文件。原 sqlite/postgres jobs
和 required-check 名称保持不变，不在 Windows 跑旧数据集、Ollama 或数据库服务。

新增原生测试在临时的冻结合成文件副本上以 Windows SetFileTime 设置独立 creation time，
强制产生路径 birthtime 与句柄 ChangeTime 的差异，再对 .py/.json 分别真实读取核验。
不会改原文件内容或 gold。Linux 上这两项 Windows 专属测试不执行，其余断言照常运行；
不能用 CRLF 或 mock 测试代替 Windows CI。另有六个保留字段逐项拒绝、两个 API ctime
各自变化必须拒绝、打开前同内容文件替换/读取中变化等故障注入。
最终 HEAD 的 Windows 与完整 SQLite/PostgreSQL16 实际数量/日志在 PR Validation 区。

用户的临时验收 checkout 可能没有本地 feature 分支，且不一定有 `.venv`。可使用
已有 Python Launcher 从仓库中执行以下整块，不强制覆盖本地修改：

```powershell
& {
    [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
    $OutputEncoding = [Console]::OutputEncoding
    $env:PYTHONIOENCODING = 'utf-8'
    git fetch origin feat/frozen-email-wording-challenge
    if ($LASTEXITCODE -ne 0) { throw 'fetch 失败' }
    git switch --detach FETCH_HEAD
    if ($LASTEXITCODE -ne 0) { throw '切换失败，请保留本地修改' }
    Set-Location (git rev-parse --show-toplevel)
    py -3.12 -m experiments.diagnose_wording_stats --synthetic-only
    if ($LASTEXITCODE -ne 0) { throw '诊断失败' }
    $summary = py -3.12 -m experiments.email_wording_challenge --synthetic-only
    if ($LASTEXITCODE -ne 0) { throw '措辞挑战失败；不要使用部分报告' }
    $summary | Out-Host
}
```

也可以把 `py -3.12` 换成此前已验证的 Python 3.12 命令；不要求重建环境、升级驱动或
运行模型。取得修复后应再次按上节 UTF-8/剪贴板命令连跑两次；实验数字应保持不变。
CI 原生验证不代替用户笔记本的修复后复验。新 HEAD 待 ChatGPT、Hanabi 增量复审，
PR 保持 OPEN / UNMERGED。

原生 Windows 首轮另发现两项测试准备问题：CRLF 测试须先归一 LF 再生成 CRLF，
避免在 CRLF checkout 上生成 CRCRLF；源码 AST 检查须明确 UTF-8，不能使用系统
CP1252 解码。这两处只修测试准备，不改固定文件、pins 或安全断言。最终验证须
包括这些修正，不能以首轮 81 项成功隐去两项失败。
