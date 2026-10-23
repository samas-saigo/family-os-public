# 模型对照实验题集 · 待审草稿 rev1（未冻结）

依据：`docs/email-model-artifact-control-v1-plan.md` 第 4 节
（commit `aec2b1b9cc0a673ce2fc63a205ded5bfa187423c`）＋ 有限合同。
本轮为集中修订 rev1：依据 ChatGPT 首审意见与 Claude 独立 gold 复核意见，
对 9 条评估题（题面或 rationale）与 2 条 smoke 题做限定范围修改；
ID、组别、顺序、全部预定配额保持不变；未修改实验方案、prompt、schema、
解析器、评分器或成功门槛；未运行模型，未读取旧题或历史预测。
状态：**待审草稿，未冻结**。未获得复核通过前，不冻结、不实现、不运行；
不得运行推理，不得依据模型输出改题。

文件：

| 文件 | 说明 | CRLF→LF 规范化后 SHA256 |
|---|---|---|
| `eval-set-draft-2026-10-22-rev1.json` | 24 条评估输入（固定顺序 eval-01…eval-24） | `eff0dd5e56013cd068a675395a9d52dcaa1e4f13f2b09399d147f25a03cf18c0` |
| `smoke-set-draft-2026-10-22-rev1.json` | 2 条独立 smoke 输入（smoke-01、smoke-02） | `33c7432d09eb2829abfb69b75db784a9c7cd3357b0ac8ff3922319c4ad355e0a` |

生成脚本 `build_drafts.py` / `build_drafts_rev1.py` 保留在工作区，
未作为交付附件；如需可另行提供。

## 哈希规范（统一）

以二进制读取文件，仅做 `CRLF → LF` 规范化，再对规范化字节流计算 SHA256。
残留的孤立 `CR` 不做静默转换——脚本对此显式失败，而非悄悄改写。
复现命令：

```bash
python3 -c "
import hashlib, sys
raw = open('eval-set-draft-2026-10-22-rev1.json','rb').read()
norm = raw.replace(b'\r\n', b'\n')
assert b'\r' not in norm, 'lone CR present'
print(hashlib.sha256(norm).hexdigest())"
```

- 评估集 rev1：`eff0dd5e56013cd068a675395a9d52dcaa1e4f13f2b09399d147f25a03cf18c0`
  （首个十六进制位为 `e`，偶数）
- smoke 集 rev1：`33c7432d09eb2829abfb69b75db784a9c7cd3357b0ac8ff3922319c4ad355e0a`

按第 4 节规则，最终运行顺序**只依据修订后评估文件哈希确定**：
本草稿首位为偶数 → 若冻结为此内容，顺序为 **A→B**。
该顺序是哈希的自然结果，未为挑选 A/B 顺序调整文件内容。
注意：草稿哈希不具备冻结效力，正式冻结时须重新计算并记录。

输入结构：每条 `input` 仅含 6 个字段
（`notice_kind`、`provider`、`record_type`、`schema`、`subject`、`synthetic_only`）；
`id`、`group`、`variant`、`gold`、`rationale` 置于输入之外。
全部输入的排序键（键排序紧凑 UTF-8 JSON）均 ≤2048 字节，
`subject` 均 ≤360 字符，不含控制字符、URL、HTML、联系地址、凭据或令牌。

---

## 一、作者独立性声明（保留）

1. **未参与候选提示词设计。** 本人（Hanabi）没有设计、撰写或修改过任何
   候选提示词。曾审阅过方案文档本身（公开 PR #2 的 8B-vs-4B 设计计划、
   私有 PR #115 的提示词哈希核验），审阅方案不等于设计提示词。
2. **历史题目接触记录（本题集不宣称为完全盲测）：**
   - 见过：第 4 节的配额结构与类别定义（16 清晰 / 8 歧义、状态分布
     8/3/4/1、日期 3/2/1/1/1、7 动作 / 4 状态、歧义类别清单）。
   - 未见过：候选 prompt 的具体内容（仅核验过其 SHA 与字节数）、
     旧 36/37 例的任何题面文本、Holdout30 的任何内容、任何历史预测输出。
   - 因此：作者知晓“考什么、考多少”，但未接触任何旧题文本或答案；
     **本题集为非完全盲测**，特此记录。
3. **创作与修订过程隔离：** 仅依据第 4 节、有限合同及两位审阅者的复核意见
   修订；未查看候选 prompt、历史预测或旧题集；未读取 Holdout30；
   未复制或改写旧 36/37 例；未使用真实邮件；未用被测模型生成或筛选题目。

## 二、“证据不足”操作定义（rev1 新增）

“证据不足”类 abstain 仅适用于**题面未对任何动作/状态作出可判定声称**
的情形，例如纯话题标题（eval-15、eval-24 修订后即属此类）。
**没有待办动作本身不构成证据不足**：题面若含有明确的状态断言
（如“材料已收到、正在审核中”“指南已发布”），即使不产生待办动作，
也须按其明确声称标注为 informational 等对应状态，不得以“无待办”
为由弃答。rev1 将 eval-15、eval-24 改为只有话题、没有明确状态断言的
标题，正是为了消除把明确信息通知误作弃答的情形。

## 三、校验责任区分

- **作者的程序化校验**（`build_drafts_rev1.py` 内断言，全部通过）：
  输入合法性（字符/字节/字段）、24/2 数量与分组配额、状态分布、
  outstanding 双步骤 4 种组合、日期逐字出现/真实日历/年份范围/绑定规则、
  7 动作与 4 状态覆盖、informational 有/无步骤兼有、歧义题 strict 空 abstain、
  ID 唯一、题面互不重复、顺序固定。这是作者自查，不是对审阅者工作的替代。
- **两位审阅者的验证**：ChatGPT 首审与 Claude 独立 gold 复核是审阅者
  实际执行的验证，其验证记录以各自报告为准；本轮 9＋2 项修订即依据
  他们的复核意见作出。作者未代述其验证细节，未将其结论冒充为自己的校验。

## 四、逐ID变更表（rev1）

| ID | 变更 | gold 是否变化 |
|---|---|---|
| eval-02 | 题面/gold不变；rationale补充：“重新安排缴费”为联系动作的目的短语，不构成另一个独立付款要求 | 否 |
| eval-05 | 题面：健康讲座 → 牙科复诊预约（明确的预约式到访，不扩大 attend_visit 定义）；取消步骤与 event_date 保留 | 否 |
| eval-06 | 题面去掉“上次取消的体检”背景事实，改为纯疑问“请问是否需要帮您预约体检？” | 否（仍空 abstain） |
| eval-12 | 题面去掉“尚未收到纸质账单”背景事实，改为纯疑问“请问12月的水电费账单是否已经寄出？” | 否（仍空 abstain） |
| eval-15 | 题面改为纯话题标题“2027年秋季入学申请须知”，无明确状态断言 | 否（仍空 abstain，类别保持证据不足） |
| eval-16 | 题面：“保单续保也待办理”→“续保申请表也待提交”；renew_membership 改为 return_form，消除范围争议；截止日从句“完成缴费”明确绑定缴费动作 | 是（动作替换；仍为两个不同未完成动作＋due） |
| eval-18 | 题面补充“您当前的缴费义务尚待核实，请等待进一步通知”，明确当前义务不可判定 | 否（仍空 abstain，类别保持否定/撤回） |
| eval-19 | 题面直接陈述退款“申请”动作“已于2027-01-20提交成功”，不再用“款项到账”推导 | 否（动作/日期绑定不变） |
| eval-24 | 题面改为纯话题标题“社区服务指南（2027年版）”，无明确状态断言 | 否（仍空 abstain，类别保持证据不足） |
| smoke-01 | 场景改为宽带服务；动作为 invoice_payment＋contact_biller（语义明确、不同）；截止日从句“完成宽带费用缴纳”明确只针对缴费动作 | 是（动作替换；仍多步骤＋due） |
| smoke-02 | 题面改为纯疑问“请问社区文艺汇演的报名什么时候开始？”，真实信息不足；不再用明确活动预告充当歧义 | 否（仍空 abstain） |
| 组名（仅报告用） | g2“体检预约/健康讲座”→“医疗预约”；s1“车位管理”→“宽带服务”；s2“社区活动预告”→“社区活动咨询” | — |
| 其余 15 条评估题 | 保持原样 | — |

连带检查结论：eval-16 去掉 renew_membership 后，该动作仍由 eval-07（未完成）与
eval-08（完成）覆盖；其余动作/状态覆盖不受影响。除上表外无必须连带修改之处，
未扩大重写范围。

## 五、配额核对表（评估集 24 条，rev1 复核）

| 配额项 | 要求 | 实际 | 通过 |
|---|---|---|---|
| 场景组 | 8 组 ×（2 清晰＋1 歧义） | g1…g8，每组 2 清晰＋1 歧义 | ✓ |
| 清晰/歧义 | 16 / 8 | 16 / 8 | ✓ |
| 清晰状态 | 8 outstanding / 3 completion / 4 informational / 1 promotional | 8 / 3 / 4 / 1 | ✓ |
| outstanding 双步骤 | 恰 4 条：完成＋未完成、失败＋补救、取消＋补救、两个不同未完成动作 | eval-14、eval-02、eval-04、eval-16 | ✓ |
| outstanding 单步骤 | 4 条 | eval-01、eval-07、eval-10、eval-13 | ✓ |
| 日期（8 条清晰各 1 个） | due 3 / reported_completion 2 / event 1 / available 1 / offer_expiry 1 | eval-01·13·16 / eval-11·19 / eval-05 / eval-22 / eval-17 | ✓ |
| 动作覆盖 | 全部 7 种 | invoice_payment、contact_biller、renew_membership、attend_visit、request_refund、reschedule_visit、return_form | ✓ |
| 步骤状态覆盖 | 全部 4 种 | reported_outstanding / completed / failed / cancelled | ✓ |
| informational | 有步骤与无步骤兼有 | 有步骤 eval-05·20，无步骤 eval-22·23 | ✓ |
| 歧义 8 条 | 均为严格空证据 abstain（steps、dates 全空）；类别：疑问×2、可能性×2、冲突×1、否定/撤回×1、证据不足×2 | eval-06·12 / eval-09·21 / eval-03 / eval-18 / eval-15·24 | ✓ |
| 歧义输入合法性 | 不靠无效 JSON / 非法日期 / 非法字段制造歧义；每条弃答依据见各题 rationale 与第二节操作定义 | 全部输入通过合法性断言 | ✓ |
| notice_kind | 非弃答 promotional→promotional，其余非弃答→service | eval-17 为 promotional，其余非弃答为 service | ✓ |
| 日期绑定 | due→outstanding 动作；reported_completion→completed 动作；其余日期 action 为 null；日期逐字 ISO、真实日历、2015–2035 | 全部断言通过 | ✓ |

### smoke（2 条，不计入 24 例配额）

| 题 | 要求 | 实际 |
|---|---|---|
| smoke-01 | 清晰多步骤＋due 日期；两动作语义明确、不同；日期从句明确只针对其中一个 | invoice_payment＋contact_biller；due 2027-02-28 绑定 invoice_payment；题面与评估集独立 |
| smoke-02 | 真正存在疑问/可能性/信息不足的主题；合法空弃答 | 纯疑问句，strict abstain |

## 六、后续步骤（非本次交付）

1. 独立审阅者复核 rev1 的每条 gold 与歧义定义（第 4 节要求“在生成前检查”）。
2. 复核通过后正式冻结：输入、gold、配额、唯一 ID、组别、固定顺序的
   LF 哈希及独立审阅记录；此后不得改题。
3. 再冻结实现/配置/请求合同与独立报告命名空间，方可进入 smoke/full 执行。
