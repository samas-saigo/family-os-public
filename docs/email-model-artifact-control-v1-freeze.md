# email-model-artifact-control-v1：题集冻结记录

本阶段只冻结输入/gold，不包含实现或运行授权。公开 main 已由 GitHub API 与独立
checkout 核对为 `aec2b1b9cc0a673ce2fc63a205ded5bfa187423c`，与用户给定起点一致。
研究问题、门槛、预算与停止规则仍以
[原预注册](email-model-artifact-control-v1-plan.md)为准，不修改原方案文件。

## 精确文件与身份

目录为 `fixtures/email-model-artifact-control-v1/`：

| 文件 | 完整 LF SHA256 |
| --- | --- |
| eval-set-draft-2026-10-22-rev1.json | eff0dd5e56013cd068a675395a9d52dcaa1e4f13f2b09399d147f25a03cf18c0 |
| smoke-set-draft-2026-10-22-rev2.json | a08efb52b85df1e71cd616444047f8042eed271186d164cab7206d3750020e18 |

附件本身已经是 LF。逐字节复制，不重新序列化，不修改内部 DRAFT/status/version/
basis/rationale，历史文件名也不改。用户本次明确确认这两个精确文件的标注审查
通过并授权冻结；本外部记录是当前冻结状态，内部 DRAFT 是保留的历史标记。
不存在 eval rev2，不创建、不读取该文件。未来 loader 仅从上述两个固定路径读取。
Windows 若检出 CRLF，只在内存将 CRLF 转 LF 后核对哈希；孤立 CR 拒绝，不回写。
本目录 `.gitattributes` 固定两个 JSON 的 LF checkout。

同时原样保留 [README rev1](../fixtures/email-model-artifact-control-v1/DRAFT-README-rev1.md)
和 [README rev2](../fixtures/email-model-artifact-control-v1/DRAFT-README-rev2.md)，作为作者
声明/接触记录/历史修订的来源资料。其中“待审/后续步骤”描述的是草稿时点，不是
本次执行指令。生成脚本未提供；未推断或重建它们。

## ID、顺序和配额

- eval 固定顺序 `eval-01` 至 `eval-24`；每连续三条为 g1 至 g8，依次 clear、clear、
  ambiguous。16 清晰/8 歧义；清晰 state：outstanding 8、completion 3、informational 4、
  promotional 1。全部歧义为严格空 steps/dates 的 abstain。
- outstanding 分母 8；双步骤恰为 eval-02（失败+补救）、04（取消+补救）、
  14（完成+未完成）、16（两个不同未完成动作）。
- 日期分母 8，每条至多一个：due 01/13/16；reported_completion 11/19；event 05；
  available 22；offer_expiry 17。逐字完整 ISO，真实日历 2015–2035，原合同绑定。
- 全部 7 种 action、4 种 step status；informational 有步骤 05/20、无步骤 22/23。
- smoke 固定 `smoke-01`（s1、clear、多步骤+due）、`smoke-02`（s2、ambiguous、空弃答）。
  与 eval 不重叠，不并入其 24 例分母。

作者早期 eval 草稿哈希首位 `7` 对应 B→A（该旧文件/完整哈希未提供，本次不声称
独立复算）。标注修订后本次最终 eval rev1 首位为 `e`，即偶数，按原方案自然得到
**A→B**，smoke/full 均同序。smoke rev2 哈希不决定顺序。未为选顺序改文件；这一
过程依据作者记录及用户提供的 Claude 结论，本次只独立复算最终文件。没有 eval rev2。

## “证据不足”操作定义（README rev1 §2 原文）

“证据不足”类 abstain 仅适用于**题面未对任何动作/状态作出可判定声称**
的情形，例如纯话题标题（eval-15、eval-24 修订后即属此类）。
**没有待办动作本身不构成证据不足**：题面若含有明确的状态断言
（如“材料已收到、正在审核中”“指南已发布”），即使不产生待办动作，
也须按其明确声称标注为 informational 等对应状态，不得以“无待办”
为由弃答。rev1 将 eval-15、eval-24 改为只有话题、没有明确状态断言的
标题，正是为了消除把明确信息通知误作弃答的情形。

## 审查来源与实际限制

1. **作者 Hanabi 自述**：未设计候选 prompt；知晓配额/合同并审过方案及 prompt 哈希，
   未见 prompt 文本、旧36/37题、Holdout30 或历史预测；不使用真实邮件/被测模型造题。
   这是接触记录和作者自查，不能独立证明未接触历史材料；本题集不宣称完全盲测。
   rev1 的 9 个 eval 定点修订及两个 smoke 修订表保留于原 README。
2. **ChatGPT 先前首审**：附件只载作者对首审意见的记录，没有另附完整首审报告，
   本次不虚构该首审的逐项执行证据或声称重新取得其签字。当前实现代理对26条题面/
   gold逐条阅读，对照原 plan §4 和原严格 parser 核验输入、gold/日期绑定、最终哈希、
   顺序和配额；语义复核未发现阻塞。后续测试将固化这些机械检查。实现代理可见
   冻结合同及研究上下文，不是独立盲测作者，也不能证明作者自述。
3. **Claude 独立 gold 复核**：用户本轮提供的结论为11项定点全部接受：eval-02/05/
   06/12/15/24/16/18/19，smoke-01/02，无剩余标注阻塞，同意冻结精确文件。
   报告称已复算最终哈希及顺序、核验26条合法性/日期/绑定/重复与配额。smoke-01
   的最终“请联系宽带客服确认账单明细”为无条件独立要求，解决 rev1 条件建议问题。
   eval-16 的“待提交”为原合同允许的状态声称；eval-15/24 依赖上面的操作定义。
   **限制**：Claude未读plan §4原文，只对照README配额；未看prompt/旧题/历史预测；
   未得到smoke rev1，不能逐字节证明修改范围；关于所谓eval rev2的“字节相同”表述
   只能视为对最终eval rev1哈希的确认，本次没有该文件。其结论是用户提供的审查记录，
   不是本代理独立执行Claude审查。该结论不授权推理、不预测哪个模型胜出。

适用范围为新创作的中文合成标题、有限 action/state 和完整 ISO 日期；不是旧英文
规则覆盖证明、真实邮件准确率、完全盲测或上线依据。两条证据不足样本同型且少，
8个相关场景组仍是小样本开发筛选。原 parser/scorer 不改，不借中文修改 prompt。

## 继续边界

用户返回的 inventory（非本代理实测）称 Python3.12.10、Ollama0.40.6、RTX2060 Max-Q
6144MiB，A digest匹配；B目标tag及alias均未安装，尚无8B适配/速度或chat OFF/JSON
兼容证据。本次新授权允许题集冻结、实现和离线/Mock验证，**没有解除真实执行阻塞**。
不下载/改tag/升级/查询Ollama；后续需重新核验软件、硬件与两模型身份，审查固定公开
执行commit/tree、干净目录、配置/报告身份和Restricted交互stdin流程，再分别授权
smoke/full。不提供当前可运行真实实验的命令，不自动进入下一阶段。
