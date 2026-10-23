# 模型对照实验题集 · 待审草稿 rev2（未冻结）

依据：`docs/email-model-artifact-control-v1-plan.md` 第 4 节
（commit `aec2b1b9cc0a673ce2fc63a205ded5bfa187423c`）＋ 有限合同。
本轮为单点修订 rev2：仅修改 smoke-01，
将“联系宽带客服”由条件建议改为无条件、独立的明确要求。
其他题目、gold、ID、组别、顺序均不动；
未修改实验方案、prompt、schema、解析器、评分器或成功门槛；
未运行模型，未读取旧题或历史预测，未提交 PR。
状态：**待审草稿，未冻结**。未获得复核通过前，不冻结、不实现、不运行；
不得运行推理，不得依据模型输出改题。

文件：

| 文件 | 说明 | CRLF→LF 规范化后 SHA256 |
|---|---|---|
| `eval-set-draft-2026-10-22-rev1.json` | 24 条评估输入；**本轮未改写，逐字节与 rev1 一致** | `eff0dd5e56013cd068a675395a9d52dcaa1e4f13f2b09399d147f25a03cf18c0` |
| `smoke-set-draft-2026-10-22-rev2.json` | 2 条独立 smoke 输入（smoke-01 修订、smoke-02 不变） | `a08efb52b85df1e71cd616444047f8042eed271186d164cab7206d3750020e18` |

完整背景（独立性声明、接触记录、“证据不足”操作定义、
作者程序化校验与审阅者验证的区分、rev1 逐ID变更表与配额核对表）
见 `DRAFT-README-rev1.md`，本轮未改变其中任何结论。
生成脚本 `build_drafts_rev2.py` 保留在工作区，未作为交付附件。

## 哈希规范（统一，与 rev1 一致）

以二进制读取文件，仅做 `CRLF → LF` 规范化，再对规范化字节流计算 SHA256。
残留的孤立 `CR` 不做静默转换——脚本对此显式失败，而非悄悄改写。
复现命令：

```bash
python3 -c "
import hashlib
raw = open('smoke-set-draft-2026-10-22-rev2.json','rb').read()
norm = raw.replace(b'\r\n', b'\n')
assert b'\r' not in norm, 'lone CR present'
print(hashlib.sha256(norm).hexdigest())"
```

- smoke 集 rev2：`a08efb52b85df1e71cd616444047f8042eed271186d164cab7206d3750020e18`
- 评估集 rev1（未改写，复核前后一致）：
  `eff0dd5e56013cd068a675395a9d52dcaa1e4f13f2b09399d147f25a03cf18c0`

按第 4 节规则，运行顺序只依据**评估**文件哈希确定：
评估文件逐字节不变，首位 `e`（偶数）→ 顺序仍为 **A→B**，保持不变。
smoke 文件哈希不参与顺序决定。

## 本轮变更记录（仅 smoke-01）

| ID | 变更 | gold 是否变化 |
|---|---|---|
| smoke-01 | 题面：“如有疑问请联系宽带客服”→“请联系宽带客服确认账单明细”。联系账单方现为无条件、独立的明确要求，不再是条件建议；保留 invoice_payment＋contact_biller 两个不同的未完成步骤；截止日从句“完成宽带费用缴纳”仍明确只针对缴费动作，绑定 invoice_payment；场景（宽带服务）与评估集题面独立 | 否（步骤/日期/绑定均不变，仅题面措辞与 rationale） |
| smoke-02 | 不变 | — |
| 评估集 24 条 | 不变（文件未改写，哈希复核一致） | — |

阻塞原因回顾：rev1 的 smoke-01 中“如有疑问请联系宽带客服”是条件建议，
不能标为当前明确的 contact_biller / reported_outstanding；
修订后该从句为无条件的独立要求，标注依据成立。

## 独立性重申

作者仍未参与候选提示词设计；本题集仍为非完全盲测
（知晓配额结构，未接触旧题文本/答案/历史预测/Holdout30/候选 prompt 内容）；
详见 rev1 README 第一节。本轮修订仅依据复核意见改写单个题面，
未引入任何外部信息源。

## 后续步骤（非本次交付）

1. 独立审阅者复核 rev2 smoke-01 的 gold 与标注依据。
2. 复核通过后正式冻结：输入、gold、配额、唯一 ID、组别、固定顺序的
   LF 哈希及独立审阅记录；此后不得改题。
3. 再冻结实现/配置/请求合同与独立报告命名空间，方可进入 smoke/full 执行。
