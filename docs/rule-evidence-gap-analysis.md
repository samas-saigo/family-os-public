# 规则引擎行动证据缺口诊断

独立实验 `experiments/rule_evidence_gap.py`，契约 `rule-evidence-gap-v1`。
基线 main：`fb5f610f32badf452c6697e39d5f1b14fffda21f`。这是固定合成数据的只读诊断，
不是规则优化、AI 推理、生产分类能力或真实世界准确率评估。

## 结论与证据分级

### 已通过匹配轨迹证实

| 诊断 | Development 60 | 原始 37（34 条可投影） |
| --- | ---: | ---: |
| 明确标签 action 正确 | 0/40 | 12/14 |
| required 识别 | 0/20 | 4/6 |
| action `no_evidence` | 58 | 17 |
| action `weak_only` | 2 | 3 |
| action `conflict` | 0 | 2 |
| action `strong_unanimous` | 0 | 12 |
| 所有维度都没有规则匹配（含 veto 前也没有） | 58 | 10 |
| 有非 action 命中，但没有 action 候选 | 0 | 2 |
| 有规则实际被 veto 的案例 | 0 | 5 |
| 输入满足至少一个 caution 条件的案例 | 27 | 5 |
| 投影前后轨迹/输出变化 | 0/60 | 0/34 |

状态统计的分母是有效轨迹数，不包含拒绝/异常；评分分母独立固定为 40/20 和 14/6。
旧集三条安全投影拒绝案例不进入匹配器、不产生 fallback 预测；它们均为 human-uncertain，
因此拒绝不会删减 14/6 分母。状态不应与旧工具对全 37 条直接运行规则的状态分布混用。

1. **主要缺口是固定词法覆盖，而非本次阈值或安全 veto。** Development 的全部 20 条
   required 都没有规则命中；其余 38 条也没有命中。两条仅命中 `weak_attention`，均为
   human-uncertain。所有强规则在其 provider/record_type 合格范围内，
   `subject_phrases_any` 均未通过。当前规则要求有一致强证据才能作明确行动判断；
   已匹配的两条弱证据不会成为 required。没有通过降阈值可恢复的强规则命中。
2. **caution 存在不等于规则被 veto。** Development 27 条存在现有 caution 条件，
   但没有规则满足其全部谓词而进入 veto 列表。不能把零识别归因于这些安全条件。
   旧集有 5 条实际 veto 案例，逐规则次数可能重叠，不能累加成案例数。
3. **旧集的较好表现与确实命中已有短语相对应。** 12 条明确标签正确案例均有
   `strong_unanimous` 行动证据；20 条 Development required 则全部没有行动候选。
   旧集两个 required 漏判为 `synthetic-27`、`synthetic-28`，也都未匹配任何规则，
   不是弱证据或 veto。旧集还能触发非 action 规则及相反行动候选冲突；不能把
   `matched_rule_ids` 非空当成 action 已有足够证据。
4. **Calendar 存在叠加的条件缺口。** Development 12 条 Calendar 输入对
   `vet_appointment` 都满足 provider/record_type，但 12 条短语条件失败、12 条
   token 合取失败；另有 9 条 `metadata_equals` 失败、3 条 `metadata_present` 失败。
   `start.dateTime` 缺失 3 条、`status` 缺失 3 条。失败可以同时发生，不能相加为
   独立漏判数，也不能声称补齐其中一个字段就会触发整条规则。
5. **投影没有改变当前匹配器可见证据的实际效果。** 60+34 个通过安全投影的输入，
   投影前后均使用原 `diagnose()` 及原谓词匹配器核对，完整输出、命中、强/弱命中、
   veto、状态和谓词失败记录一致。这仅排除了这些固定案例中“现有规则证据被投影
   丢失”的解释；不证明 metadata 足以确认现实世界的义务。

Development 场景：付款 9、预约 11、营销 2 条均为 `no_evidence`；续费 6 条
`no_evidence` + 1 条 `weak_only`；历史场景 1 条各为 `no_evidence`/`weak_only`。
按 temporal 标注的 historical 则有 3 条（2 no_evidence、1 weak_only）；**scenario
与 temporal 不等同**。其余 provider/scenario/temporal/真实 action 标签的完整分组
及各规则命中、强弱、veto、明确标签错误/required 漏判关联均保存在本地 JSON。
旧 37 条没有 scenario 标注，使用 `unannotated`，不按标题或正确答案补造；temporal
仅从原 recent/historical tags 映射，未标明时为 unknown，不做系统时钟推断。

### 反事实三元组

16 个 Development triad、48 个配对中：

- 实际接受的规则命中集合变化：2 对；dimension states 变化：2 对。
- 实际 veto 集合变化：0 对；完整逐谓词失败记录变化：8 对。
- action 输出变化：0 对；两端都正确：0 对；三条全部正确：0/16。

每组保存固定案例 ID、cue 字段和各变化次数，不保存输入原文。
这证明“行动输出不变”不意味着所有内部词法轨迹都不变；**命中变化不等于分类正确**。
invalid/rejected 轨迹不参与有效配对，单独保留覆盖范围；零有效分母的比率为 null。

### 有支持但尚未证实的假设

- 有限短语与合取条件可能难以覆盖更广泛的表达。轨迹已证实本组覆盖缺口，但没有
  证明某个新同义词、语法解析器或扩大规则表会提高独立数据质量。不能推断旧集的
  构建意图、作弊或真实分布代表性。
- 显式事件状态、否定/完成措辞、日期类型的结构化抽取可能有帮助；尚未实现、未测收益。
  不能把重写/删除 caution 或把弱匹配升级为 required 当作已验证方案。
- AI 也许能提供新的信号，但本次无 AI 结果。旧 37 条互补性结果不能外推到 Development，
  更不能据此声称 AI 能补救本次 20 个 required。

### metadata-only 无法判断

缺失的消息正文、未批准来源事实、家庭关系/实际责任、真实付款或预约状态是否能消除
歧义，无法从这些元数据轨迹证明。标题/事项日期不证明截止日期，也不授权创建 Task。
需要家庭信息的 human-uncertain 不因诊断被确定化；预测 uncertain 不代表已有 Pending。
不得通过读取真实邮件、扩大 provider scope 或调用模型去填补本 PR 的证据边界。

## 实现和信任边界

- Development 复用 PR #102 的 `load_development()`：固定 manifest、60 条、20/20/20、
  annotated/input hashes、投影 digest 和 16 个 triad。绝不调用旧完整 dataset loader。
- 对照仅额外读取 `fixtures/metadata-reasoning.synthetic.json`，LF 规范化后 SHA-256 固定为
  `529f81a7adb293ecf89297996ea62237a65a931b8fead1f3f92a2ebea1ac2047`；保留全部 37 个 ID。
  原 `synthetic-url`、`synthetic-oversize`、`synthetic-wrong-shape` 仍安全拒绝。
- 两份配置用 PR #100 已记录的 LF hashes 固定；记录当前规则/策略 fingerprint。
  不修改分类器、配置、评分、标注、冻结文件、T1/I9 或权限。
- 直接调用 `MetadataRulesAnalyzer.diagnose()`，校验输出、固定状态、规则 ID、强规则
  子集及维度候选一致性。为解释合取失败，用原 `_matches()` 一次检查一个既有谓词；
  不重写匹配语义，不把临时单谓词 Rule 用作分类器，也不改变任何预测。
- trace 错误为 `diagnosis_rejected` 或 `diagnosis_invalid`，投影错误为
  `projection_rejected`；输出为 null，分母不缩减，不能变成正确或合法 abstention。
- 报告只有固定 ID、规则 ID、枚举、字段名、布尔、计数及版本/hash，没有案例标题、
  sender、正文、原始字段值、rationale、fake_response 或自由格式模型推理。
- 新路径六个固定输入：Development/rubric/manifest、两份配置、旧 37 fixture。
  拒绝链接/reparse/非普通/多硬链接/过大文件；不接受路径或 split 参数。
  在受信任本地 checkout 运行，不声称防御有写权限的恶意进程并发替换路径。
- 不打开 Holdout。manifest 中既有 Holdout hash/count 元数据只用于冻结身份；不重新
  验证当前 Holdout 内容、跨 split 近重复或跨集独立性。旧完整验证器与既有 CI 完整性
  测试保持原样，不能把它们视作本入口的依赖或新的 Holdout 研究授权。

## Windows PowerShell

在本 PR checkout 根目录、已按锁文件准备的 Python 3.12 `.venv` 中整段复制：

```powershell
$env:PYTHONIOENCODING = 'utf-8'
$summary = & .\.venv\Scripts\python.exe -m experiments.rule_evidence_gap --synthetic-only
$code = $LASTEXITCODE
$summary | Out-Host
if ($code -ne 0) { throw '证据缺口诊断失败；不要使用部分结果。' }
$summary -join [Environment]::NewLine | Set-Clipboard
```

无需 Ollama/GPU/数据库/网络。环境准备见
[Development-only 说明](development-only-rule-diagnostics.md)。
结果写入 Git 忽略的 `.local/rule-evidence-gap/<随机运行ID>/report.json`，不覆盖旧运行。
验收：确认独立 0/40、12/14 与 20/6 分母、58/2 Development 状态、3 条旧集拒绝；
重复运行诊断内容应相同（输出目录不同），文件无案例原文，摘要已在剪贴板。
Windows 实际运行仍待产品所有者验收，本 PR 不声称已验证其主机。

专项：`python -m pytest -q tests/test_rule_evidence_gap.py tests/test_development_rule_diagnostics.py`。
测试拦截 builtins.open、io.open、os.open，仅允许六个固定输入；旧完整加载器和网络/
子进程为立即失败陷阱。覆盖冻结身份、原分母、所有已支持行动状态、伪造/错误诊断、
逐规则次数、Calendar 条件、triad 变化不等于正确、投影拒绝与输出隐私。
最终 HEAD 的实际测试数及完整 SQLite/PostgreSQL CI 链接记录于 PR 描述。

## 后续研究（仅方向，最多三项）

1. **受控确定性证据抽取。** 单独版本研究词法覆盖、否定/完成状态、事件状态合取，
   不直接扩大强规则。风险是把营销或已履行事项误升为义务；变更前人工审核每条规则
   和反例，在另行批准的验证协议下评测，不把 Development 调试收益当独立提升。
2. **日期与上下文证据契约。** 先定义可验证字段及缺失时的 abstain，区分 all-day/
   dateTime、事项日期与 deadline；需要新增数据权限时独立审批。风险是凭空补出义务
   或截止日期，必须由人工核实，不自动生成或完成任务。
3. **独立 synthetic-only AI 影子实验。** 另行审查投影输入、模型 digest、prompt、显式
   Thinking 和预算，禁止标签/rubric/rationale 进入输入。风险为幻觉、注入和错误确定化；
   仅比较保守建议，人工审核后才可进入既有明确确认流程，不自动建 Task，不执行 Holdout。
