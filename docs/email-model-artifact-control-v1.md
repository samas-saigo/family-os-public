# email-model-artifact-control-v1：公开离线实现

本PR实现[已合并方案](email-model-artifact-control-v1-plan.md)，研究设计、联合门槛、预算
和停止规则不变。只准备文件/实现/Mock验证，不是运行授权。PR115仍为stop_candidate，
没有移植原子装配，也不读取旧36/37例、Holdout或历史报告。没有Ollama查询/推理。

## 冻结身份与复用边界

- 起点公开main `aec2b1b9cc0a673ce2fc63a205ded5bfa187423c`，API及新checkout一致。
- 独立题集冻结提交：`29ad25c947827c115a6e8d3ef72315186556deb7`，先于本实现。
  [外部冻结记录](email-model-artifact-control-v1-freeze.md)记录两个精确JSON、作者/审阅
  来源、限制、中文输入范围、ID/配额与B→A自然变为A→B的过程。两个JSON字节不改。
- 两份原README也原样保留；SHA256分别为
  `a16b1af196ce48a86473759cc257b6d44541b87dcd84dcba2ec3c5c7e81fd408`（rev1）、
  `6bfde105686119f5fb89ddab40551ff55dbca6b22164eda681301ca440c82cd2`（rev2）。
- [新配置](../experiments/configs/email-model-artifact-control-v1.json) LF SHA256：
  `c2e41c00cc7559f9deaf1588e5c9f615eddf12438606679d1b615bccf5c9c55f`。
  配置包含两制品pin、题集pin、原模块/PR114配置/plan的完整source pins、原门槛、
  独立报告目录及 `execution_freeze:null`。这个null是有意的真实执行阻塞。
- PR114配置/2081字节prompt/schema/generation按原哈希加载；只拿其合同，不调用
  任何旧setup/selector/run。原parser、scorer和旧模块全不改；额外检查实际导入位置
  必须位于当前公开checkout，避免误用其他已安装包。

[最小封装](../experiments/email_artifact_control.py)显式构造每例独立client。PR109
单次请求传输函数以同一bytecode、独立globals复用；唯一身份适配是精确所选tag。
PR109响应验证器同样隔离身份绑定，内部严格parser不变；PR112有限结构注释仍仅
用于解释拒绝。没有改旧模块globals、重置计数器或静默把B标成A。A/B应用请求
只有model不同；模板/tokenizer差异仍属于模型制品变量，不作纯参数量因果结论。

## Loader、阶段、计分与保存

Loader只读本次两个固定fixture；验证LF哈希、无孤立CR、输入合同、gold经原parser
接受、日期逐字/日历/绑定、精确ID/顺序/分组/状态/日期/双步骤配额和跨文件不重题。
只有input的6字段进入user消息；ID、group、variant、gold、rationale、DRAFT状态、
历史上下文均不发送。题集哈希鉴别冻结文件，不给每条输入生成/保存指纹。

四个阶段为smoke A、smoke B、full A、full B，分别手动启动。后续阶段须显式提供
之前阶段的run UUID与原始报告SHA，不扫描目录挑选结果。要求相同执行commit/tree、
完整可信前阶段；进入full前四份smoke响应均须结构/协议通过，不用smoke语义分数
挑模型。每阶段先独占创建固定claim，再进行任何模型元数据请求；失败也保留claim，
不重试、不恢复生成、不自动启动下一阶段。claim是本checkout的防重复门控，不是
跨主机安全锁，不授权另建checkout重跑。recover仅只读原报告。

smoke每组120秒、full每组600秒，包括加载/元数据/校验；connect≤5秒、metadata≤5秒、
chat≤60秒。每例最多一次chat；请求16384/响应65536/content8192字节。截断、thinking、
协议/身份异常、超时/OOM/传输异常等停止；full普通JSON/结构拒绝和refused保留分母，
smoke任何拒绝即停止。超时不能证明服务器已停止，禁止自动转下一组。

保留原scorer全部分母及分组指标。拒绝/失败/未尝试均不计正确弃答。身份观察中断、
异常或不匹配永久污染，后来成功不可恢复归属；model_metrics/by_group为null。
未知telemetry保留null与absent/unavailable状态，未知指标不以0代替。

五项有害条件只约束B；A仍完整报告。仅两个可信完整full可比较，核对24/16/8/8/8
分母及预算；同时逐项检查清晰≥12、W−L≥4、弃答≥7且不低于A、歧义越界≤1且不高于A、
未完成遗漏≤2且不高于A、日期遗漏≤2且不高于A及B五项有害计数为0。列W/L及分组退化。
完整且未达门槛为stop_candidate；不完整/未知为not_evaluable；全部通过只为
provisional_signal。Mock比较标记offline_mock，不是实测信号。

**零有害计数仅是原scorer对获验证最终预测的观察计数**，不表示被拒绝的原文没有
错误；报告另列unobserved_predictions及此范围。没有保存/事后分析被拒绝内容。
不用结构通过数代替语义门槛，不改题/提示词/模型/预算继续优化该26条。

只允许有限最终预测、固定ID、阶段/状态/结构原因、验证后的数值telemetry、有限字段
presence计数及身份进入报告。不存题面、prompt、回复、thinking、被拒绝预测、原文
证据或任意异常文本。记录起止驻留字节；CPU/offload实测缺失保持null，驻留比例不
冒充利用率。报告有严格字段校验及重算指标，≤524288字节，复用已审UUID、临时文件、
fsync/原子替换及受限regular-file读取；同目录readback核对SHA与canonical字节。
保存失败保留内存结果、有限错误码及claim，不再执行模型；恢复隔离于
`.local/email-model-artifact-control-v1/<UUID>/report.json`。

## 本地离线验证与Windows说明

本地环境为Linux Python3.12.14、pytest9.1.1，不冒充用户Python3.12.10/Windows实测。
仅新测试使用内存HTTP Mock，显式禁止真实socket及旧selector/setup。39项通过，覆盖
冻结/gold、实际请求差分/大小/字段隔离、原parser/validator差分、原scorer、身份污染、
元数据/异常/超时/截断、分母/隐私、一次请求、四阶段前置、原子保存失败和只读恢复、
门槛等号/越界及五项有害计数。另29项既有CI证据/选路unittest通过，CI配置未修改。
52个A/B请求的离线序列化大小7177–7271字节；内容UTF-8字节+1024 framing+512 output
的保守context上界最大3882≤4096。这沿用原token假设，不是精确tokenizer/template实测。
未下载tokenizer/模型，未本地重复完整测试套件或历史基线。

Windows保留已审的**交互式stdin**流程，不写/执行.ps1，不改变Restricted执行策略。
本次只提供以下离线合同检查（不查询模型、不写报告），在已安装公共checkout环境中
粘贴；打印全部JSON并复制。原生PowerShell5.1/7的最终真实启动块仍属后续冻结/验证，
不声称此PR已在用户笔记本执行。

```powershell
$artifactCheck = @'
import socket
def deny(*args, **kwargs):
    raise RuntimeError('network_forbidden_in_offline_check')
socket.create_connection = deny
socket.socket.connect = deny
from experiments.email_artifact_control import main
raise SystemExit(main(['check']))
'@ | py -3.12 -
$artifactCheck
try { Set-Clipboard -Value ($artifactCheck -join "`r`n") -ErrorAction Stop }
catch { 'clipboard_error=copy_failed' }
```

## 后续执行身份冻结，当前仍阻塞

1. ChatGPT首审→Hanabi独立审查→用户手动合并；本PR不合并、不生成。
2. 重新取得并审查软件/硬件及两目标精确tag/digest的只读inventory。先前信息只能称
   **用户返回的inventory**：A匹配、B和alias未安装；6GB适配/速度及chat OFF/JSON未知。
   本实现代理没有独立实测；本次没有查询Ollama或解除安装/运行阻塞。
3. 审查公开执行配置与报告命名空间，单独冻结真实launch启用决定；当前CLI的smoke/
   full固定返回execution_not_frozen_or_authorized，collect默认真实路径也被null阻塞。
   后续启用变更只可处理运行授权/身份门控，不得改变研究设计或根据推理调参。
4. 在启用变更审查完成后，固定外部批准的完整公开commit/tree、此配置SHA、实现LF
   SHA与干净目录。不得在含自身commit的文件里制造自指pin，也不使用私有提交。
   独立审查最终Restricted交互stdin启动块、Python3.12.10、完整结果打印/自动复制及
   只读recover；默认真实collect仍会核验Windows、Python、commit/tree、冻结祖先与
   干净目录。只读恢复不查询模型。
5. 用户另行明确授权两次smoke；四响应兼容后审阅资源证据，再另行授权两次full。
   四阶段不自动衔接；失败按原plan停止，不清claim重跑。本PR不提供真实启动命令。

无真实账户、Holdout、生产接线、Task/Pending/行动权限；没有付费服务/模型CI、路由
白名单或权限改动。只使用正常最终HEAD CI，不手动重跑或建立演示工作流。
