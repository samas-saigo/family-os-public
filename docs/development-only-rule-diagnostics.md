# Development-only 规则引擎诊断

## 范围与运行

这是独立离线实验入口 `experiments/development_rule_diagnostics.py`，内部契约
`development-rule-diagnostics-v1`；不是生产部署版本，也不接入 T1/I9。
仅运行现有 metadata rules，不运行 Ollama、模型、网络、账户、数据库或任务操作。
不修改样本、标注、提示词、规则、冻结 manifest 或原来的完整数据集验证器。

Windows PowerShell：在本仓库根目录、已安装锁定开发依赖的 Python 3.12 环境运行：

```powershell
$env:PYTHONIOENCODING = 'utf-8'
$summary = & .\.venv\Scripts\python.exe -m experiments.development_rule_diagnostics --synthetic-only
$code = $LASTEXITCODE
$summary | Out-Host
if ($code -ne 0) { throw 'Development 诊断失败；不要使用部分结果。' }
$summary -join [Environment]::NewLine | Set-Clipboard
```

未创建环境时，先在已审核的本地 checkout 执行：

```powershell
py -3.12 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r requirements-dev.lock
& .\.venv\Scripts\python.exe -m pip install --no-deps -e .
```

安装依赖是单独的准备步骤，可能访问包仓库；诊断命令本身完全离线，不下载模型。
无需启动 Ollama、服务器或数据库。输出目录固定为
`.local/development-rule-diagnostics/<随机运行ID>/report.json`，Git 忽略且不覆盖旧结果。
屏幕/剪贴板仅显示中文汇总与相对路径；详细文件仅有固定 ID、有限标签、分组、
预测和状态，不含 subject、sender、正文、rationale、证据引用或投影原文。
报告是本地数据，不默认提交 GitHub。运行 ID 不扩大独立样本数量。

## 固定输入与文件访问边界

入口只加载：

- `fixtures/action-evaluation-v1/development.json`
- `fixtures/action-evaluation-v1/rubric.json`
- `fixtures/action-evaluation-v1/manifest.json`
- `config/classification.yaml`
- `config/metadata-classifier.yaml`

没有可选 split、任意文件路径、模型或网络参数。三个 JSON 通过固定文件名白名单、
有界 UTF-8/严格 JSON（重复 key、非有限数值拒绝）读取。链接、非普通文件、
多硬链接和 Windows reparse point 拒绝；检查父目录及打开文件身份。
这是受信任本地 checkout 下的离线工具，不声称抵御拥有 checkout 写权限的恶意
本机进程在检查与读取之间并发替换路径。不要在不受信任/可被其他用户修改的目录运行。

直接导入 `action_evaluation` 的纯数据类型、投影、标签校验及规则解析函数；模块导入
不加载数据。**不调用** `load_dataset()`、`validate_dataset()`、`validate_cases()`、
`manifest_for()`、原 `report()`，也不导入模型运行入口。
新入口不打开、不遍历、不读取 Holdout 案例或标签。

冻结 manifest 的 canonical SHA-256 必须匹配既有
`f676baa523a8c7a9b187e8139be8e556244a09009ef674b7830a3729b831634f`。
在此身份下逐项核对 rubric、taxonomy、投影 schema/engine、Development annotated/input
hashes、60 个唯一 ID、20/20/20 标签和投影 digest
`b3fac7d7c286a0a2c1f7ba013825a3bbc19e1cbf2dd0faefd0a8500f3cabe6f0`。
canonical hash 允许无意义的 JSON 空白、行尾和案例顺序变化，不允许字段或内容变化。
冻结 annotated hash 同时锁定完整 schema、所有标注和输入；另行执行当前投影与标签
校验，重复投影、超过 1024 bytes 的投影或任一案例失败均整批拒绝，不跳过。

重新验证 Development 内部 16 个 triad：每组三条、三种 action 各一、同一 cue、
relevance/domain 一致，仅声明的一个可见字段变化，并核对三个 cue 值不同。
其他 12 条为独立案例。

manifest 中的 Holdout **hash/count 元数据**仍属于已冻结身份，不是 Holdout 内容。
本入口**无法重新验证**当前跨 split 重复/近重复、Holdout 当前文件完整性或原始 37 条
与当前两 split 的内容关系；只信任原先经审核的冻结记录。报告明确标记
`holdout_content_read=false`、`cross_split_content_revalidated=false`。
原有完整数据集验证与既有离线 CI 完整性测试保持不变；它们不是本入口的依赖，
不能将既有 CI 的全数据完整性验证描述为新诊断入口也读取了 Holdout，或反之。

## 评分与诊断

每条输入独立交给原规则分析器，按原 `validate_output()` 校验。标注、rationale、
rubric 答案不进入规则输入；不修改预测以改善得分。

- 明确标签准确率：required + not_required，固定 **40** 条，action 精确匹配。
- required：固定 **20** 条，识别、未识别分开；未识别进一步分为 not_required、
  uncertain、无效/拒绝/内部异常，三部分之和等于未识别数。
- not_required → required：错误升级，不代表创建了 Task。
- 相关事项 → irrelevant：仅在人类 relevance=relevant 的记录上统计。
- human-uncertain：固定 **20** 条，分别报告三个预测分布，以及被错误确定化为
  required/not_required 的数量。这不是证实哪些真实义务存在。
- `valid`、`rejected`（规则抛出 AnalysisError）、`invalid_output`、`rule_error` 独立计数。
  失败保留在所选分母中，不伪造 uncertain，也不默认为正确。
- 合法 uncertain 为 action abstention；domain 未分类另计。unknown domain 不自动
  等于坏输出；任何预测 uncertain 都不代表已经建立 Pending。
- provider、scenario、temporal 分组均有同样的分母/状态/矩阵，子组无分母的比率为 null。
- triad 报告全部正确数、三个预测是否不同、是否完全不变，以及 48 个 cue 变化配对的
  预测变化/两端正确数，按 subject 与 raw_metadata.status 分组。
  **变化敏感性不等于正确性**；无效输出不计入有效配对，零有效配对率为 null。

## 实际离线观察与限制

当前未修改的规则在冻结 Development 上：有效输出 **60/60**，均为 uncertain；
明确 action 正确 **0/40**；required 识别 **0/20**、未识别 **20/20**（均 → uncertain）；
错误升级 0、相关事项错误 irrelevant 0；human-uncertain 确定化 0/20；
triad 全对 0/16，全部 16 个 triad 的预测不随 cue 改变。
这说明当前词法规则在该模板集上的 action 区分能力不足，**不证明真实家庭邮件的准确率**。
没有运行 AI，也不能据此推断未来 AI 与规则是否互补。
Development 是已知、可诊断的数据；以后用其标签调整规则，不能再把同一批数据上的改善
宣称为独立质量提升。原 37 条的 6/14 分母不适用于这组 20/40 的 Development 数据。

## 测试与验收

专项测试覆盖固定身份、逐字段缺失/变化、额外字段、重复 ID、数量/标签/triad/
投影漂移、严格 JSON、路径/链接拒绝、规则异常、有效 abstention、诊断分母与 triad
敏感性、确定性和本地输出。文件访问测试同时拦截 builtins.open、io.open、os.open，
仅允许五个输入文件；依赖意外读取其他文件（包括 Holdout）会在打开前失败。
完整加载/验证入口均替换为立即失败的陷阱；网络及子进程也被禁止。

```powershell
& .\.venv\Scripts\python.exe -m pytest -q tests/test_development_rule_diagnostics.py
```

Windows 人工验收：执行上述剪贴板命令，确认 60/40/20/16 分母、无 Ollama 要求、
汇总可直接粘贴；检查本地 JSON 没有案例原文。再次执行应产生独立结果文件，而诊断
内容相同。篡改输入需在测试副本中验证拒绝，**不得修改冻结仓库样本**。
最终 HEAD 的专项、SQLite、PostgreSQL CI 数量与链接记录在 PR 描述。

## 后续 Development AI 适配器（仅设计，本 PR 不实现）

需另行审核、独立版本的 Development-only runner，复用本入口的固定加载边界和
已批准 metadata 投影；模型传输函数只能接收投影，不能接收 SyntheticCase、expected、
rationale、rubric、evidence_refs 或文件路径。固定 prompt/schema、模型 digest、显式
think、预算、seed 与参数；逐案例新上下文，输出严格校验。评分器在推理完成后才按
固定 ID 连接人类标签；模型无文件访问和工具能力。增加捕获实际请求的泄漏测试与
Mock 传输测试后，再由所有者在 AMD 主机单独授权运行。不得把新适配器暗接原完整
loader，不能以此授权 Holdout、生产模型选择或实际家庭任务处理。
