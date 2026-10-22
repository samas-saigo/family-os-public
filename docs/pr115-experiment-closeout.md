# 私有 PR115 实验结果登记：stop_candidate

登记日期：2026-10-22（America/Los_Angeles）。候选：
`synthetic-email-atomic-assembly-v1`，原子抽取 → 确定性装配。

**停止该候选。** 完整 full36 未通过冻结的联合开发门槛；保留失败结果，
不重跑，不在同一36例上改提示词、schema、装配器或门槛。
通过代码审查和 CI 不等于模型效果通过；停止仅针对该候选。

## 来源与核验边界

来源：**用户提供，ChatGPT离线核验**的 PR115 收尾交接摘要。
该摘要说明：ChatGPT 离线解析用户提供的两份完整 Windows 输出，按冻结编码规则
重算内嵌 report 的 SHA256，与发布哈希一致，并核对配置、源文件 pins、输入顺序/
参考答案、运行条件、每案一次请求及 full 联合门槛。
本次文档作者只读取该交接摘要及有限仓库文件，未取得原始输出或报告正文，未自行
运行模型、重算报告哈希、访问用户电脑或独立读取其磁盘报告。哈希一致不构成对
本地运行环境的独立取证；运行身份和计数来自历史报告及上述核验摘要。

这是**私有 PR115 的历史运行**，不是公开快照的测量。公开库当前没有 PR115 实现，
本登记不构成公开执行授权。旧私有文件、门槛、报告及 recover 身份保持冻结，
旧报告恢复仍使用原始私有执行身份。参见 [公开发布边界](../PUBLICATION_PRIVACY.md)
及 [有限迁移准备清单](pr115-public-migration-inventory.md)。

## 历史冻结身份和报告哈希

以下身份来自交接摘要；提交号仅作历史引用，不引入其 Git 对象或历史。

| 项目 | 私有历史身份 |
| --- | --- |
| 原 PR | samas-saigo/family-os PR115（私有归档） |
| 审查 HEAD | `9862c941c9b0f9444f61518d780918e308bdfb63` |
| 合并提交（交接时私有 main） | `6dd8e8198285d0549b52e70161e02cc3147ff742` |
| 预注册提交 | `60e5b31e580c917618b53fe4a857a20b37671095` |
| 冻结执行 commit | `eb7d4d14f73ca0dad69a22723a8627b285d84cfe` |
| 冻结执行 tree | `c81c56b1cf3a0775aca1c426f9d085fe1c993cce` |
| 配置 LF SHA256 | `fc10ca1e901fb902c7f2848c0f56b9944c65da14baf13ece0ebd0b7cec948198` |
| 实现 LF SHA256 | `9930259a64598c98a824dc5846d032395a75dbedcbba504a622cd22b1fc9af72` |
| smoke report_sha256 | `d4a613462d1a66fea01b5d00683714cdf1732ed2b81d4078b87237992b826451` |
| full report_sha256 | `c0f84617f7625dae53b93ca48d10aeafb6aa78155b9012b12166ddf5a8182e9e` |

模型：`qwen3.5:4b-q4_K_M`；digest
`d8b0f5e9760cd1682034f292d7ef72ec46f432149be0df7574bf2d6e92e38c04`。
Ollama0.40.6、Python3.12.10；think=false、temperature=0、seed=0、ctx4096、predict512。
两次均 complete、identity_verified_at_end=true，workflow/experiment/process exit code
均0，报告均 published_readback、read_verified。执行成功与候选通过是不同结论。

## 独立分母结果


| 指标 | smoke | full |
| --- | ---: | ---: |
| 执行例数 | 6/6 | 36/36 |
| 清晰/歧义 | 5/1 | 24/12 |
| 结构有效/拒绝 | 3/3 | 22/14 |
| 清晰完整/部分正确 | 1/0 | 4/1 |
| 清晰错误弃答 | 2 | 10 |
| 清晰结构拒绝 | 2 | 9 |
| 歧义正确弃答 | 0/1 | 7/12 |
| 歧义结构拒绝 | 1/1 | 5/12 |
| 待办遗漏 | 2/3 | 10/12 |
| 日期遗漏 | 3/4 | 11/16 |
| 歧义越界 | 0/1 | 0/12 |
| 五项有害case计数器 | 全0 | 全0 |
| 耗时（秒） | 19.094 | 38.968 |

smoke与full分别报告，不合并分母，也不视为独立泛化样本。smoke门槛not_evaluable；full门槛eligible=true、stop_candidate。

## full 联合门槛

| 冻结指标 | 本次 | 门槛 | 结果 |
| --- | ---: | ---: | --- |
| `clear_full_min` | 4 | ≥12 | 未通过 |
| `missed_date_cases_max` | 11 | ≤8 | 未通过 |
| `ambiguous_abstain_min` | 7 | ≥11 | 未通过 |
| `ambiguous_overreach_max` | 0 | ≤1 | 通过 |
| `missed_outstanding_cases_max` | 10 | ≤3 | 未通过 |
| `unsupported_step_cases_max` | 0 | ≤0 | 通过 |
| `unsupported_completion_cases_max` | 0 | ≤0 | 通过 |
| `invented_date_cases_max` | 0 | ≤0 | 通过 |
| `misbound_date_cases_max` | 0 | ≤0 | 通过 |
| `false_clearance_proxy_cases_max` | 0 | ≤0 | 通过 |

## 拒绝与结论限制

full14例拒绝：explicit_contradiction10、date_state_index3、date_not_in_subject1。
五项有害 case 计数器为 unsupported_step_cases、unsupported_completion_cases、
invented_date_cases、misbound_date_cases、false_clearance_proxy_cases，均为0。
它们只描述最终接受输出，不说明模型从未生成坏内容；例如不存在于主题的日期已被
装配阶段拦截。结构拒绝不是正确弃答；有效结构不是语义正确。

结果只表明本次冻结的模型/提示词/表示/装配组合未达到其开发门槛，不证明4B容量
上限，也不否定全部拆分抽取方法。这些是已见、相关的合成开发案例，不是盲测或
真实邮件准确率，不作为上线标准；不使用旧 Holdout30，不赋予 Task/Pending 或行动权限。

## 本次文档变更范围

只登记结果并准备迁移，不移植实现、不修改任何私有冻结文件，不携带私有 Git
历史，不保存原始附件、完整运行输出或用户路径，不下载/切换模型、不重新推理、
不调参。未来模型或硬件变更须另立并审查预注册方案，不从现有36例生成调参方案。
交给 ChatGPT 首轮审查，再交 Hanabi；本 PR 不合并。
