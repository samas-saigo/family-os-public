# 独立 launch 门控：仅本地草案，真实执行关闭

## 起点、职责与未改变的合同

本轮由开发Codex实现，ChatGPT负责架构/独立首审，Hanabi负责二审，重要专项可由
Claude复核；Lisa决策、合并及真实运行。本文件不是独立首审结论。已完整阅读Lisa
粘贴的产品宪章及附件 `chatgpt-handoff-review-history-1.md`；宪章不写入或修改。
产品仍是智能家庭行动系统；本功能只属于合成研究执行准备，不接来源账户、建议/
Pending/Task或外部行动，不改变任何产品行为或权限。

GitHub API核对main/新本地checkout均为
`d95c515eeda0533ec82c239ecf83c7f1b9d94020`，tree为
`63af6c9da9a9623f5605de8d05fa1d1fe4ac337c`，与Lisa给定起点一致。没有重复PR4实现。
PR4审查HEAD为 `0f995bc33954a3faaf5d1b8677f8dceaae2ecec6`，输入冻结为
`29ad25c947827c115a6e8d3ef72315186556deb7`。

[原plan](email-model-artifact-control-v1-plan.md)、题集/gold/顺序、prompt/schema、
parser/scorer、生成设置、120/600秒及单请求预算、原联合门槛均不改。
配置精确字节及LF SHA仍为
`c2e41c00cc7559f9deaf1588e5c9f615eddf12438606679d1b615bccf5c9c55f`；
**`execution_freeze:null` 保持原样**。runner因增加入口门控而有新文件hash，未来必须
重新固定，不能再用PR4 runner hash。旧冻结模块和CI工作流均不修改。

## 四个不同操作

| 操作 | 本草案行为 | 是否授权生成 |
| --- | --- | --- |
| 默认离线检查 | 读现有公开pin/新fixture，有限JSON；无网络、无claim | 否 |
| 只读环境核验 | 公共入口当前关闭；测试在Mock中验证固定5次元数据请求 | 否 |
| 阶段准备 | 离线核对release/阶段记录、Git/文件/解释器证据和指定前序报告 | 否，结果恒为execution_authorized:false |
| 真实执行 | null门控及未安装的独立authority双重阻塞；没有签发permit/dispatch代码 | 否 |

`prepare_stage`的ready_for_review只表示所提供记录内部一致，**不证明Lisa签字、
来源可信或软件/硬件已经在此进程亲验**。`decider:Lisa`、任意SHA、非null对象、
环境变量、CLI参数、环境检查成功或四份smoke有效都不是运行许可。当前CLI不接受
真实运行开关；没有可从准备结果晋升的许可对象。

本草案加强runner公共Transport.request及collect默认真实路径；直接调用identity/
residency/request，或把生产Transport伪称Mock注入，也会在HTTPConnection前阻塞。
测试改用显式MockTransport重用原传输bytecode及内存HTTP，未给生产类增加Mock绕过
参数。内部纯函数/测试依赖注入不是安全沙箱，不能约束主动替换Python代码的本机人。
冻结历史runner的独立入口不在本次改动范围，不得借它们运行当前候选。

## 未来外部批准记录合同（当前不签发）

以下是严格内容合同，不是批准记录样本或真实启动指令。外部记录必须由Lisa经
独立审查明确接受；其原始规范JSON字节的SHA锚点须从**另一份获准交接**取得，不能
从待验文件自身、环境变量或同一段未受信代码取“预期SHA”。当前尚无此信任入口。
本实现拒绝多余字段，未知/缺失/重复/冲突均阻塞；不改tag/digest做替代。

release（schema `email-launch-release-v1`）包含：

- 明确experiment，完整40位公开commit/tree，不在仓库文件中硬编码包含自身的commit。
- 四项LF SHA256 pin：config、runner、独立Python launcher、非Python Windows门控块。
  路径在代码固定，记录只能提供完整64位hash；CRLF只在内存转LF，孤立CR拒绝。
- 解释器的经核验Windows绝对路径、Python `[3,12,10]`/win32，以及Ollama0.40.6。
  不搜索/切换解释器，不安装、不使用当前失效的 `py -3.12`。个人绝对路径只留在
  外部本地批准资料，不写Git、有限输出或错误信息。
- A/B精确tag/digest、gguf、family、4.2B/8.2B、Q4_K_M及completion/thinking能力。
  不把alias替代目标，不补偿prompt或生成参数。
- 默认RTX2060 Max-Q/6144MiB、经重新核验的driver和RAM总量。未知RAM不能用历史
  32GB补齐；host证据必须匹配外部release。空闲显存/RAM是动态观察，不证明可运行。
- 固定报告命名空间 `.local/email-model-artifact-control-v1`。

阶段decision（schema `email-launch-stage-v1`）包含：

- 对应release的规范JSON SHA、独立decision_id、明确Lisa的单阶段批准决定；这些
  内容仍须外部信任核验，字符串本身不认证Lisa身份。
- experiment、mode、arm、report_namespace；phase_authorization必须与mode精确一致。
  full必须另有明确full决定，不能复用smoke批准。
- 该阶段**全部**指定前序收据，固定顺序，每项含mode/arm、32位UUID与原始报告SHA；
  重复UUID拒绝，不扫描目录寻找“最好”或“最新”结果。

规范记录SHA定义为排序键/紧凑UTF-8 JSON（无额外终端换行）。未来Windows在启动
Python前须独立核对原始记录字节锚点并严格拒绝重复JSON键；不能把PowerShell的
宽松反序列化或转换后重新序列化当作原始SHA验证。实际外部批准交付与防重放的信任
流程仍需ChatGPT/Lisa另审；本草案不增加签名服务、密钥系统或未经授权的“批准者”。

## Windows：任何Python之前的检查

[不可执行真实实验的模板](email-artifact-launch-windows-template.txt)只包含非Python
的本地Git和LF SHA检查函数，末尾无条件throw，**不存在Python或模型dispatch**。
按交互stdin设计，不执行.ps1、不改ExecutionPolicy；不依赖Python来验证Python前置
条件。未来获准块必须按以下顺序实现并接受原生测试：

1. 先验证独立外部release/decision与批准锚点、精确阶段；不让未验记录决定任意路径。
2. 核对完整HEAD/tree、输入冻结祖先、干净checkout及四个固定文件LF hash，拒绝
   reparse point/超限/孤立CR。检查均成功前不启动任何Python，包括版本探针。
3. 使用批准的绝对解释器，不能用PATH或py launcher自动切换；启动前再次核对
   checkout/pin。以后采用隔离stdin bootstrap，避免用户site/未知包优先于当前公开源码。
4. Python再次核验实际sys.executable、version/platform、pin与前序报告；外部宿主
   硬件证据必须新鲜可信。然后才可能由后续获批authority授予单次阶段能力。
5. 完整打印有限结果、报告UUID/SHA与错误码，再自动复制；复制失败不重跑，保留
   完整显示。recover单独选择原UUID+SHA，只读且不查环境模型。

本轮没有实现可运行的bootstrap、批准锚点安装或真正的authority issuer。模板函数
已经落地，可静态审查；**未在PowerShell5.1/7或Restricted下执行/解析验证**。
本地可信Git/文件核验不构成对恶意同权限进程的独立证明，也不消除所有文件替换竞争。

## 阶段/claim与只读核验的边界

仍为smoke A → smoke B → full A → full B；每个阶段单独手动选择，Lisa分别授权
smoke和full。阶段准备只读前序文件，不消耗claim、不查询模型。

未来真实阶段须先核对离线前置和批准，再**独占claim，之后才进行任何本阶段模型
metadata请求**；随后在原总预算内核验元数据并只运行所选阶段。claim失败不得查询
模型；失败、中断、超时、保存/readback失败均保留占用，不清除、不自动重试、不换
checkout/命名空间规避。已有collect的claim/save/recover流程及原永久身份污染语义
不改。纯只读环境核验是另一个明确操作，不会自动创建阶段或升级为执行。

新MetadataTransport只允许numeric-loopback `127.0.0.1:11434`：GET version/tags/ps，
POST show只接受两精确tag与verbose=false。复用已审直接HTTP：无代理/重定向/重试，
每次≤5秒、五次操作总窗口≤25秒，响应≤65536字节、header≤8192；严格JSON解析。
独立只读核验的25秒不是实验的额外预算：若未来在阶段内使用，必须传入在claim前
已经开始的原stage_deadline，取两者较早值，禁止核验后重置120/600秒。
拒绝chat/generate、任意URL/模型/额外request字段。只返回有限身份/驻留数值，丢弃
show模板/system/license、未知原始值与异常文本；失败resident_count为null，不是0。
已知A/B驻留可以记录，不因驻留而卸载、也不假定GPU适配；未知/冲突驻留身份阻塞。
一次环境核验失败后不再尝试恢复；实验中任何身份失败仍永久去归属。

## 本轮证据、限制与后续启用

实际本地：Linux Python3.12.14、pytest9.1.1；仅针对本改动的两个测试文件，
`PYTHONPATH=src:. /workspace/family-os/.venv/bin/python -m pytest -q tests/test_email_artifact_launch.py tests/test_email_artifact_control.py`
为 **106 passed**（67项新门控用例、39项PR4相关Mock回归）。其中使用已有隔离测试
临时目录验证claim、中断、重复阶段、保存失败、恢复与跨报告；没有执行完整套件。
网络由autouse socket拒绝，HTTP/阶段Git/host均为显式Fake；另有一项临时本地Git测试，
验证只忽略固定实验目录，使claim/报告保留而不污染下一阶段clean门控，其他未知路径
仍显示为dirty。只读wire测试仅模拟通过
门控后的边界，未改变磁盘配置中的null。A/B请求仍仅model不同。

早期零网络探针曾在本开发checkout留下一个offline_mock claim和attempted=0、身份
不可信的Mock报告；已保留，没有清除占用。测试现已改为临时隔离目录，不能把该
开发记录当作真实阶段证据，也不能据此重跑/清claim或规避未来批准的工作区门控。
原.gitignore遗漏这个新namespace，本轮仅增加该目录规则，不扩大其他忽略或CI白名单。

静态检查：Windows模板无Python调用/策略变更、必须停止；源码/合同pin与diff检查。
这些不是Windows原生验收，也不是模型质量、速度、OFF/JSON、显存/预算或硬件证明。

2026-10-23的最新真实环境信息来自**用户提供的ChatGPT只读核验摘要**，不是本开发
代理亲验：A/B身份均匹配、Ollama0.40.6、无驻留、RTX2060 Max-Q当时空闲4627MiB、
driver610.91；已核验绝对Python3.12.10/win32，但py launcher失效；工具shell7.6.5/
RemoteSigned不能代表日常5.1/Restricted；当前RAM仍未知。它取代PR4说明中的旧B缺失
快照，但不改写冻结历史。没有据此查询本机或解除运行阻塞。

交ChatGPT独立审查本地diff；本轮不提交/推送/开PR、不触发CI或发外部评论。后续还须
审查并批准authority/外部锚点交付和Windows bootstrap，完成原生离线测试、Lisa允许
发布并手动合并，再固定最终外部commit/tree及新config/runner/launcher/门控块hash，
重新核验软硬件、补齐RAM与资源条件；之后才可另行请求Lisa授权smoke，再审full。
任何“代码已审/已合并/metadata匹配”均不替代上述许可。当前真实入口继续关闭。
