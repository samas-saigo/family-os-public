# PR115 公开迁移准备：有限文件差异与 pin 依赖

本清单仅供后续审查，不实施迁移或授权执行。候选已按
[历史结果登记](pr115-experiment-closeout.md)停止。

## 比较身份与方法

- 公开基线 main：`520ac231be98d2adea3209438293381b30f5104d`。
- 公开根 tree：`8468aab86139b3a92b0ef06f54bda4f599ca31f3`。
- 私有审查快照：`9862c941c9b0f9444f61518d780918e308bdfb63`。
- 私有执行/报告身份见结果登记；公开基线是隐私清理后的 PR114 快照。

本次在独立公开 checkout 核对 origin/main；有限只读比较上述私有快照的六个文件及
其明确的 pin 依赖与公开基线。哈希为原始字节仅将 CRLF 规范化为 LF 后的 SHA256。
未读取原始模型输出、本地报告或 Holdout30，未开展全历史安全审计。
以下哈希是源码/配置比较结果，和用户报告哈希的证据来源不同。

## 六个文件：公开基线 → 私有 PR115 审查快照

A 表示公开基线中不存在，M 表示已有文件需有限修改。本次均不导入。

| 文件 | 差异 | 后续需要审查/适配 |
| --- | --- | --- |
| `.github/workflows/tests.yml` | M | 已有工作流；仅追加原子候选测试文件至 Windows 共享测试步骤，以及5行候选 PowerShell 文档解析检查。保持公开工作流其他内容和 CI 路由。 |
| `docs/synthetic-email-atomic-assembly-v1.md` | A | 私有预注册、合同、转换器证据、运行身份及旧 Windows 入口。未来只导入审查后的文档内容，清理个人标签/路径；历史块不变成公开可执行入口。 |
| `experiments/configs/synthetic-email-atomic-assembly-v1.json` | A | 完整候选配置，含12个 source_pins。公开副本须绑定公开依赖字节，并区分历史身份和未来公开身份；不覆盖私有冻结配置或旧门槛。 |
| `experiments/email_atomic_assembly.py` | A | 219行验证/装配及复用封装；依赖公开 PR114→113→112→110/109/108/107 链。重新绑定 SOURCE_PINS、CONFIG_SHA，并审查 FREEZE/LOCAL/报告身份和恢复隔离。 |
| `experiments/schema_support/atomic-v1.gbnf` | A | 1577字节静态转换器证据；不是模型输出。核对固定转换器版本、schema 对应关系及 LF 哈希，不据此授权推理。 |
| `tests/test_email_atomic_assembly.py` | A | 503行离线/Mock与 Windows 原生回归。审查冻结身份/源码哈希、schema/grammar pin和文档路径断言；保持禁真实网络和全部已有回归。 |

私有六文件 LF 哈希（历史比较定位，不是公开执行 pins）：

| 文件 | 私有 LF SHA256 |
| --- | --- |
| `.github/workflows/tests.yml` | `57e1dfd8e388fc661fa7255a239827314a74f073c84dee91ec4e2b9965154194` |
| `docs/synthetic-email-atomic-assembly-v1.md` | `c3c5c9038ed7add36440368bab3e5886defc9c61d4691af39a184d4937912222` |
| `experiments/configs/synthetic-email-atomic-assembly-v1.json` | `fc10ca1e901fb902c7f2848c0f56b9944c65da14baf13ece0ebd0b7cec948198` |
| `experiments/email_atomic_assembly.py` | `9930259a64598c98a824dc5846d032395a75dbedcbba504a622cd22b1fc9af72` |
| `experiments/schema_support/atomic-v1.gbnf` | `988e7b1594e53d4bcfd141ac3dc7fcfdcd0e61f61f2f7d82faa989bfc051076a` |
| `tests/test_email_atomic_assembly.py` | `63656a4f3f4ff566ea293a49c67ee110d309bfa4460c7d597cf33d16710ec28a` |

## 直接 SOURCE_PINS：12项

六项字节相同，六项因公开隐私清理及后续 pin 传播而不同。不能将旧字面量原封不动
导入；也不能放宽校验来绕过差异。以下仅记录，没有写入或更新任何实现/config。

### 需要重新绑定的六项

| 依赖文件 | 私有 LF SHA256 | 当前公开 LF SHA256 |
| --- | --- | --- |
| `experiments/email_structure_diagnostic.py` | `d0655cef13bafa1fb496a879d87592d104ed6d523d2108f68495579defe436f5` | `5eee3bd0cb33727b900da0bb35f049f0553a70686f929169e2a28796437e79b3` |
| `experiments/configs/synthetic-email-structure-diagnostic-v1.json` | `3d28de6beff0f193bb3dbbb4f7ccf3de5727f2c5faa47f5f348109d5e29f3bb8` | `3e756cd1112e27a9acb6a00dc93c6b665eeda0196f0de7aedf701e6ea27c6741` |
| `experiments/email_relational_schema.py` | `97e54a9bc39b46c45f7d8b973803843168553d78cbf32252ceb4e8f7ba2eccb6` | `6598a3c384ed0a1e4d7dbf0466ba87606afb9ee01af6813ba5cf3e32c0479e84` |
| `experiments/configs/synthetic-email-relational-schema-v1.json` | `0f6492ebaa67294de1f1c976df8d7387e8229a6fe94dfc46f6824673a82fa5e0` | `872432337d83a89330fd31d235bd1e6ded541d90f2e801ea21def6cc5793f4b2` |
| `experiments/email_semantic_prompt.py` | `956637ede6f4272e8b4ead1899ed05a09fa7044f1d8365f899c57b3168e1aa9b` | `643d827b6b278561c5911943ac581f03ddb3aa79dd88861b50e353a3009a2cfa` |
| `experiments/configs/synthetic-email-semantic-prompt-v1.json` | `146746b2bf9820608d686685307b47f52f24e9381d7c97d25e1dc3d9f623af6b` | `e95e846ae78f186f8a7f6f624f5a6fe48a2321f501461bbb3b4c5209344a2006` |

### 保持相同的六项（私有/公开共用此 LF SHA256）

| 依赖文件 | LF SHA256 |
| --- | --- |
| `experiments/single_email_compat.py` | `124d71d0cbb2120bd60921d341d45df64582023701c45ce4e90724dd622dd3b3` |
| `experiments/configs/single-email-runtime-diagnostic-v2.json` | `461b7e83eb51798aa261446c440c20a0908963b40fd4902bd14cd61ac1332aa7` |
| `experiments/single_email_diagnostic.py` | `b5451e7b0c971602d234b0c137a0eb8f9e96b90fb9a666bdb643707c26f95ca3` |
| `experiments/email_model_evidence.py` | `b0b1dc39f974af8c6f3c74cefeee4950663e83f8bc7bacff006a9c05aa035fd8` |
| `experiments/email_model_compat.py` | `5406859b660fa5a7c2c75b1e96d8511d697678cae0e8b9a012e75f00911a730e` |
| `experiments/configs/synthetic-email-model-evidence-v2.json` | `3088c54578456f242846164b8b121c3311f49d536c3f41789ff3dde04dc11042` |

### 间接固定输入与校验链

setup 顺序为 PR114 semantic_prompt → PR113 relational_schema → PR110 model_compat，
同时核对 PR112 structure_diagnostic；PR110 再进入 PR109 single_email_compat →
PR108 single_email_diagnostic → PR107 model_evidence → 固定 wording loader。
原子候选通过父模块常量继承 pins、复用函数字节码和 CLI；因此父文件任何变化都需要
核对调用者的字面量、config.source_pins、CONFIG_SHA 和报告身份，不能只改最外层。
公开基线的这条 setup 链已离线通过36例加载与 pin 验证，没有调用 run/传输/模型。

以下额外依赖在两边相同；它们不属于上面12个直接 SOURCE_PINS：

| 依赖文件 | 私有/公开 LF SHA256 |
| --- | --- |
| `experiments/configs/single-email-runtime-diagnostic-v1.json` | `fced8bb829337db363ba3bb738beac4034df66bb662468f23420817fe2b80544` |
| `experiments/configs/synthetic-email-model-evidence-v1.json` | `c4e774ce7a8a81b2bb80f77588126cd515fe3dd0496eecb09836b3330729d17f` |
| `fixtures/synthetic-email-wording-challenge-v1.json` | `067b041f142ce9892509f7024ff5d94c6a4a34be2fdd59d4d2e91a408a44b019` |
| `src/family_os/_synthetic_email_evidence.py` | `44e391f3748799c8552703cee92d77fd84166a23e04006f9c3876262c2b0d025` |
| `experiments/email_wording_challenge.py` | `7be67835c559a4d9e0fd6b92af03fe01357504adc72cb35fcd57afbc0d08afbd` |

离线转换器证据还依赖既有 `experiments/schema_support/convert.cpp` 及其文档所列的
Ollama `2476d5ead197abe04629651028f83d48dc75d2b2` / llama.cpp
`620d2225cc436ab0b001e3200e590e3b286ef9ab` 固定来源；本次不下载或重编译转换器。

## 未来适配边界（本次不执行）

1. 从届时公开 main 新建独立分支，仅导入审查过的文件改动，保留公开隐私处理。
   不 cherry-pick/merge 私有分支，不加入私有 remote、提交对象、历史、作者元数据、
   Actions 日志或原始附件。此次公开分支只新增两篇文档，父提交为公开根快照。
2. 先验证既有公开 pin 链；为未来公开副本重新计算上述依赖、候选 config 及模块哈希，
   同步其相互引用及测试断言。新哈希不同于私有历史，不可重写旧报告归属，也不可
   用“迁移”恢复已停止候选或重新冻结旧私有实验。任何新执行需单独授权和预注册。
3. 历史 private freeze/commit/tree 仅作档案引用；不得直接用作公开 checkout 门控。
   旧 recover 只使用私有原始身份。未来若获准提供公开入口，需独立审查公开运行/
   报告命名空间、commit/tree/干净目录门控及恢复隔离，不能覆盖旧报告。
4. 不复制旧 Windows 命令为公开执行入口，也不能仅替换 clone URL。本次文档无
   PowerShell/Python 可执行块。未来入口如另获授权，应保留 Restricted 交互 stdin、
   精确 Python3.12.10、完整打印/自动复制及只读 recover，禁止改变执行策略。
5. 工作流差异只作为迁移清单。未来若移植，保留现有测试、取消机制、失败完整回退，
   核对新增 native 测试/文档解析；不扩大路由白名单。模型、digest、生成/时间预算、
   严格最终 parser、scorer、fixture 和门槛均不在本次变更范围。

## 本次检查与交接

检查结果登记中的两份报告哈希、全部10项门槛和 stop_candidate 与用户交接一致；
这不表示本次重新核验了报告正文。限定六文件/依赖的 LF 哈希比较、公开父级 setup、
文档链接/差异及 outgoing 提交隐私检查在本地执行；正常 CI 状态记录于 PR 描述。
没有为本次文档登记新增测试框架、移植实现、下载模型、推理或手动重跑历史 CI。

提交 author/committer 均使用 `Samas Maintainer` 和
`337128921+samas-saigo@users.noreply.github.com`；检查新增 diff 与提交信息不含
真实姓名、个人邮箱、本地用户名/绝对路径、凭据或原始输出。
一次集中推送，交给 ChatGPT 首审，再交 Hanabi；保持 PR 打开、不合并。
