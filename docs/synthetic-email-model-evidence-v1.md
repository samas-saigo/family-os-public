# 合成邮件语义证据抽取对照实验 v1

## 冻结计划（先提交、推送，核实远端后再实现 runner）

基线 main：`69f5f9b05a1a258b53e8810544e6246ab9ec5c30`，核实时没有新增提交。
唯一配置：`experiments/configs/synthetic-email-model-evidence-v1.json`，包含完整 prompt、
严格 JSON schema、唯一模型身份、参数、预算、smoke 顺序及计分/发布契约。

- 配置 LF SHA256：`c4e774ce7a8a81b2bb80f77588126cd515fe3dd0496eecb09836b3330729d17f`
- Prompt UTF-8 SHA256：`4f691eb278ac8158b4a72ee3b602bb86bbe8af04fa0829cd45346657cb059bda`
- Schema canonical JSON SHA256：`58dfeb2d4a0b6172b0ebba91f18dd1b4e1c0fb1a4178a78ca1bb4924f6a5f3a4`
- 唯一输入 LF SHA256：`067b041f142ce9892509f7024ff5d94c6a4a34be2fdd59d4d2e91a408a44b019`
- 冻结解释器 LF SHA256：`44e391f3748799c8552703cee92d77fd84166a23e04006f9c3876262c2b0d025`
- 原计分函数所在模块 LF SHA256：`7be67835c559a4d9e0fd6b92af03fe01357504adc72cb35fcd57afbc0d08afbd`

唯一候选 `qwen3.5:4b-q4_K_M`，digest
`d8b0f5e9760cd1682034f292d7ef72ec46f432149be0df7574bf2d6e92e38c04`，
qwen35 / 4.2B / Q4_K_M。不会下载、升级、换 tag 或回退。operator 的默认环境是
Windows Python 3.12.10 / Ollama 0.40.6 / RTX 2060 Max-Q；开发/CI 不执行推理。

首轮 `temperature=0, seed=0, num_ctx=4096, num_predict=512, stream=false, think=false`。
每条独立串行请求，没有历史或返回 context；连接 5 秒、单请求 60 秒、整次 600 秒。
最多两个具名步骤、一个完整日期，JSON 不含解释性文字；512-token 输出预算可表达该
有界结构，但运行时仍可能截断，必须记录失败，不扩大预算、不修复或截取 JSON。

## 测量契约

仅使用已冻结 wording 36 条：24 清晰、12 歧义、12 个相关场景组。
Smoke 固定 WC01-1、WC02-1、WC03-1、WC10-1、WC11-1、WC10-3；是同一语料的
6 条子集（5 清晰、1 歧义、5 个组），不扩大样本数。Full 单独显式运行。
不读取 PR #104 的 75 条、Legacy37、Development60、Holdout30 或 Calendar 案例。

原 `email_wording_challenge.summarize` 不变，分别用于同一选择集的冻结规则/模型：
完整、部分、abstain；未履行步骤遗漏；无依据步骤/完成声称；歧义具体化；日期遗漏、
编造、角色或对象误绑定；按组统计。Full 保留 36/24/12、未履行步骤案例 12、日期案例
16 等原分母。失败/未尝试仍在分母；原 scorer 的 invalid_output 桶仅用于语义核算，
另记录细分失败码，绝不把它们算成合法 abstain。新增正确证据和新增错误与同案例规则
对照，不采用知道参考答案后选赢家的混合策略。部分匹配不是安全认证。

模型类型独立于规则 Evidence，不携带伪造 rule ID。可信适配器固定：无行动权限、
仅文字声称、独立安全/授权判断及人工确认必需。完成只针对同名步骤，促销日期不成为
付款截止；失败/取消不自动产生补救。跨字段约束在适配器执行，结构合法不等于语义正确。

只连接数字回环 127.0.0.1:11434，无代理/重定向/重试，精确限制 version/tags/show/ps
与 chat。发送前验证固定输入身份、安全投影；gold、ID、group、variant 不发给模型。
Inventory 仅元数据。Smoke/Full 的第一个已选择案例也是结构输出/think 控制的实际
观察，不额外增加探针或自动升级 Full。show 必须声明 completion/thinking；每次 chat
都发送 schema 和 think:false。非空独立 thinking/内联推理、工具调用或协议/预算越界
不得剥离后计成功。版本号、能力声明和合法回复均不能证明模型内部无思考或解码器
确实强制了 schema；不兼容时停止，绝不删 think 或换模型绕过。

开始、每次生成前及结束/中止时核对唯一 tag/digest/有限详情。结束无法核实身份时，
不发布模型归属的指标或比较结论。仅为观察到的安装身份，不是实际权重使用的密码学证明。
部分运行必须标记 partial；仅当所有选中案例均尝试且最终身份可验证，才发布同选择集的
完整对照。普通模型 JSON/结构错误如实记录后继续；身份、传输和资源边界失败停止后续请求。
元数据/生成均受同一运行时限；时限耗尽导致结束身份不能验证时不猜测。

报告只存有限结构预测/参考、枚举失败码、遥测及实验身份。无标题、sender、输入
fingerprint、prompt、原始响应或 thinking。缺失遥测 null，驻留字节不是 GPU 利用率。
采用独有目录、临时文件完整写入并 fsync 后原子替换；失败清理，不覆盖旧报告。
仅本地 Git 忽略目录。不与产品/任务/权限/数据库接线。

这是开发者和审查者已见过的相关合成案例，不是盲测、独立作者评估或真实邮件准确率。
提交时间与远端 SHA 是可核实的开发顺序记录，不证明外部预登记或统计独立性。
冻结后配置/样本/参考/规则不修改；问题写入限制，配置调整另建实验身份。

## 后续实现与验收计划

独立模块和 Mock HTTP 测试；冻结后补记远端 SHA、实现 SHA 及实际 CI。
覆盖真实 CLI 链、唯一输入与参考隔离、严格 JSON/交叉约束、身份变化、协议/超时/预算、
分母/评分故障注入、原子发布中途失败。保留原两份专项、Windows 及 SQLite/PG16 CI。
人工推理只在 PR 审核并合并后由 operator 自行启动；Codex/CI 不运行 Ollama。

## 冻结顺序与实际实现

配置冻结提交：`ffe329ce55bd7a148d0b849503299cdd818e138a`。
该提交只含上述配置和计划，已推送并用 `git ls-remote` 核实远端 SHA 后才编写 runner。
后续实现 SHA/完整 CI 链接记录于 PR，避免通过事后修改配置来美化结果。
此顺序是可核查的作者开发记录，不是可信第三方见证的预登记。

新增 `experiments.email_model_evidence`，只复用 wording 的固定加载/安全字段类型和
原计分函数；不导入旧 PR #104/Legacy 模型 transport，不扩大其许可。独立 ModelEvidence
不构造规则 Evidence，不伪造 rule ID。运行时还核对原 scorer 文件 hash。
模型传输再次核实配置和完整固定输入，synthetic_only=true 本身不构成数据来源证明。

单个请求使用标准库 HTTPConnection 直接连接数字 loopback，绕过环境代理。
每次 socket receive（包括 HTTP 头解析）均受单请求/整次绝对剩余时限约束，防止缓慢
分段响应不断重置预算。所有连接 finally 关闭；无重定向、重试、模型下载、保活/卸载请求。
若 OS 本身挂起或驱动不调度线程，不声称获得实时系统级截止保证。

版本、tag/digest、family/规模/量化和 completion/thinking 声明只是预检；第一个已选择
案例的合法结构回复是有限运行观察。报告明确 structured_reply_observed，不能因此证明
运行时忽略 schema 的可能性不存在。普通无效 JSON/结构、空回答、截断均保留为失败；
非空 thinking、工具调用、预算越界、身份或传输错误停止后续请求，不修复后计成功。
身份检查一旦失败就锁定不可信状态，结束时即使恢复也不重新发布模型归属结论。

Full 固定计分分母保留全部 36/24/12。失败及未尝试映射到原 scorer 的 invalid_output
做语义核算，同时 status_counts/逐例 status 保留不同错误码；这不是改变原计分定义。
partial 也不缩减分母，完整比较为 null；结束身份未知时 model_metrics/by_group/comparison
均为 null，逐例预测仅是无法归属的有限诊断。rule_metrics 不冒充模型结果。

报告含固定配置 hash（不是逐输入 fingerprint）、有限结构预测/参考、ID/组/状态、
有限 telemetry 和驻留 size/size_vram/context_length。没有原始 prompt/响应/thinking。
计数/持续时间缺失时为 null；驻留内存不是 GPU 使用率，也不证明独占 GPU。
模型 claims/日期仍仅是标题声称，不是现实完成事实或已授予的 Task/Pending 权限。
本地目录 `.local/email-model-evidence/` 已 Git 忽略，不默认上传报告。

## operator 的 Windows 操作（仅审核、合并后手动执行）

在已安装项目依赖的仓库根目录，用现有 Python 3.12.10 环境；不安装/下载模型：

```powershell
& {
    [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
    $OutputEncoding = [Console]::OutputEncoding
    $env:PYTHONIOENCODING = 'utf-8'
    py -3.12 -m experiments.email_model_evidence --synthetic-only inventory
    if ($LASTEXITCODE -ne 0) { throw '预检失败，停止；不要换模型或删除 think 参数' }
}
```

确认预检报告身份/能力及现有 Ollama 状态后，再单独运行固定 smoke：

```powershell
py -3.12 -m experiments.email_model_evidence --synthetic-only smoke
if ($LASTEXITCODE -ne 0) { throw 'Smoke 部分完成或失败；检查本地报告，不自动重试' }
```

检查 smoke 协议/schema/预算和身份。语义错误也保留，不选案例重跑。
只有 operator 明确决定后，单独运行全部 36 条：

```powershell
py -3.12 -m experiments.email_model_evidence --synthetic-only full
if ($LASTEXITCODE -ne 0) { throw 'Full 部分完成或失败；不要当成完整对照' }
```

各命令不会自动串到下一模式。退出码 0=所选模式传输完整完成（**不代表语义正确**），
2=已发布明确 partial 诊断，1=启动/配置/发布等失败，不能使用部分文件。
不提供 host/model/路径/prompt/stdin 等输入选项。首次 Ctrl+C 不触发领域写入或模型重试；
结束身份核查后尽可能发布 interrupted/partial 本地诊断。若再次中断则不发布报告。

预计时间只能按预算界限说明：smoke 六次生成各至多 60 秒，另有受限元数据检查；
full 整次上限 600 秒，可能无法完成 36 条而保留 not_attempted。实际 token/s 与耗时
必须由 operator 在 RTX 2060 Max-Q 上测量；Codex 未运行模型，不给出未经测量的速度。
不要根据该笔记本结果自动换 AMD 主机、卸载其他模型或扩大预算。

## 自动验证与限制

所有新增测试只用 Mock HTTP/Mock socket，不启动 Ollama、监听服务器或推理。
专项：`py -3.12 -m pytest -q tests/test_email_model_evidence.py tests/test_email_wording_challenge.py tests/test_synthetic_email_evidence.py`。
真实 CLI 解析/模块入口、固定文件访问、gold 隔离、schema/语义错误注入、身份变化与恢复、
有限故障码、绝对超时、三种 HTTP 响应 framing、原子发布和写入中途失败均有覆盖。
Windows 3.12.0 / 3.12.10 专项纳入新测试，原两份邮件真实 CLI 双次检查保持原样。
SQLite/PostgreSQL16 仍跑全套；新增实验测试无 GPU/Ollama 依赖。
实际 HEAD/测试数/skips/CI 日志见 PR。原有规则/fixture/reference/pins 与评分定义不变。

不能从已见过、组内相关的合成标题推出真实家庭邮件准确率。未获得任何模型实测结果，
不能因 qwen3.5 较新就预设它胜过冻结规则。后续调参必须另起版本并保留本轮结果。
仅本地研究，没有生产选择、邮件/账户读取、Pending/Task、AI 工作流或外部执行接入。
PR OPEN / UNMERGED，待 ChatGPT、独立审查员及 operator 验收；只有 operator 决定合并。

原生 Windows Python3.12.0 的初轮 Mock CI 暴露浮点相减得到
`60.00000000000003` 的边界；socket timeout 现明确取配置 60 秒上限与剩余时限的最小值。
新增固定时钟回归保留严格 <=60 断言，没有加容差、增加预算或修改冻结参数。

8 KiB 响应头上限在标准库逐行解析时提前执行（包含状态行/临时响应）；
不是解析完任意大头部后才检查。Mock socket 的百万字节头部测试验证及早停止，
最多一个有界 BufferedReader 预读缓冲，不会把整段头部读入。原绝对接收时限不变。

## PR #107 回复身份归属修复

审查基准 `57c013749686938ba4fc45dc97c02e4904ccfdc4` 上，Mock 独立复现：首次或
第二次 chat 回复错误模型名后，生成已停止，但 protocol_error 没有触发身份锁定，
结束元数据正常时仍发布模型指标。现在将回复身份检查独立为 identity_unverified，
优先于 done/额外字段等普通协议检查；缺失、类型不合法、不匹配或不可解析的 chat
身份都使整次运行永久失去归属。正常结束元数据检查不能恢复这一归属。

此时保持 partial、所有所选分母及 not_attempted，identity_verified_at_end=false，
observed_identity/model_metrics/by_group/comparison 均为 null。此前有限预测保留为
无法归属的诊断，逐例 valid 只表示当时结构验证成功，不能冒充可信模型结果。
具有正确模型身份的 done=false 等普通协议错误仍按原契约停止，保留可验证的
已有模型归属。内层模型 content 的 JSON/结构失败也保持原计数语义。

新增回归覆盖首条及先正常后身份失败、正常最终元数据不能复权、身份与普通协议
错误同时出现、缺失/不合法/不可解析的回复身份，以及实际 Mock CLI 不再输出或
发布模型指标。全部仅 Mock；冻结配置、模型、prompt/schema、预算、fixture/reference、
规则与原 scorer 不变。最终 HEAD 和 Windows/Linux 全套结果记录于 PR。
