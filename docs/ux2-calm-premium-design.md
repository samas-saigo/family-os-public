# UX2 — Calm Premium Family Experience

**状态：#90 已合并，产品所有者已选择 A1 Editorial。** 正文保留独立样稿的设计记录；
实际接入见 [Connected Foundation](ux2-connected-ui-foundation.md) 和
[A1 授权首页](ux2-a1-authorized-home.md)，不把样稿数据当成后端数据。原设计基线为 main
`5deda06707ee637baebb35d1a3625fb7d1dd93b5`（已合并 #89）。
入口为 [独立样稿](../prototypes/ux2-design-preview/index.html)，完整产品名
**Samas Family OS**。这是供产品所有者审美评审的作品，不是新的家庭任务系统。

## 设计目标与气质

服务 Clara 和 Devon 两名平等的成年人：先看到要处理的家事，再看到谁负责、
什么仍需决定、哪些日期确有依据。温暖来自暖白材质、适当留白和友好的表达，
而非插画、口号、情绪推断或“AI 替你做完”的叙事。

采用 **Calm Premium**：轻暖中性画布、安静的内容分组、精确的控件边界、少量
森林绿。保留 Samas 文字标识，不重新引入图形 S。没有网络字体、图片、渐变、
玻璃拟态或装饰动画。五个细线图标只用于导航识别，不给每条任务增加装饰。

## 旧界面为什么显得工程化

审查了 [UX1](v0-1-unified-household-ux.md)、H0/H1 HTML 与累计 CSS、
[I4b](stage-i4b-safe-task-editing.md) 及连接样式、实际截图和浏览器资产。
UX1/I4b 已建立可用和保守的交互边界，以下仅是表现问题：

| 现象 | 产品影响 | UX2 提案 |
| --- | --- | --- |
| 工具、演示说明、统计先于实际家事 | 进入应用像在操作调试工具 | 一条全局样稿提示；语言和外观退居唯一、稳定入口；内容优先 |
| 四个等重统计框与任务按钮竞争 | 先看到数量，而非下一步 | A1 使用侧栏数字索引，A2 使用轻量文字索引；完整入口仍可点击，不增加图表 |
| I4b 已有独立操作状态条，但连接页仍突出技术操作入口 | 日常家事与开发测试状态竞争注意力 | 任务使用分组表面；UNKNOWN 保留明确层次，作为次级设计状态单独查看 |
| 原生控件和各种次按钮权重接近 | 操作缺少明确主次 | 主确认、次操作、上下文链接三级；按钮仍有边界和 44px 目标 |
| UX1 已有完整深浅色语义变量；连接页呈现偏冷的中性灰 | 风格更接近工具界面 | 保留语义分色方法，重新设计暖中性画布、表面与强调比例；不是新增主题机制 |
| 同一页面重复解释内部契约 | 家庭成员承担过多认知成本 | 日常用语在前；权限和操作后果放在相关详情/确认中，不删安全含义 |

不批评或改写已通过的授权、CAS、确认和 UNKNOWN 机制。设计中的所有交互均为
本地排版状态，没有移植任何真实业务流程。

## 信息结构与四个核心页面

### 首页

克制的“Clara，你好”欢迎区；下方为待完成、待确认、有日期、待核实四个入口。
左侧优先呈现实际任务与共同待决定的问题，右侧放已有日期和核实建议。
手机先呈现任务，右侧内容顺序下移，不缩成拥挤的桌面双栏。

固定样稿为 3 项任务，其中 2 项待完成；2 项待决定（含 1 项需要更多信息），另有
1 项延期；1 个已接受任务日期和 1 个安全未知状态。它们是虚构排版计数，**不是
实时授权查询**、AI 总结、生产风险数量或用户今天的活动。
日期只使用明确给定的 `2035-06-12`，不写“今天到期”或制造紧急程度。

### 家庭待办

三条中性任务沿用 I4b 已有样例的任务内容、负责人、状态与日期组合，便于比较：
Clara 负责的无日期到访、Devon 负责的学校活动、已完成且共同负责的无日期到访。
日期未知明确写“未设置日期”，完成只指家庭跟踪状态。

未来四个负责人筛选以**禁用的布局样稿**展示；本 PR 不实现其数据查询或权限规则：

| 筛选 | 将来应有的含义 |
| --- | --- |
| 全部 | 当前有权查看的全部任务 |
| 我负责 | 我单独负责 + 共同负责 |
| 对方负责 | 对方单独负责 + 共同负责 |
| 共同负责 | 仅共同负责 |

负责人不是查看权限。分工改变不能把任务从另一位获准成员的共享列表中移除，
也不能给任何人增加私人来源访问权。没有新的 owner-only 任务库或权限引擎。

### 待确认

“待决定”和“稍后处理”是固定样稿分类切换，不是新建延期命令。
需要更多信息的事项留在未解决列表，用文字、琥珀标签和侧边强调区分；
没有充分依据时不提供接受操作。延期不表示完成，也不承诺自动提醒。

下一次学校活动与已经接受的学校任务是不同的虚构案例，确认预览明确给出
`2036-03-14` 与共同负责；未接受事项不进入家庭任务或日程。
本样稿不展示“已审阅”按钮、不将审阅等同接受或安全解除，不实现个人归档。
促销不会出现在首页、任务或待确认；优惠页必须再次主动查询才显示固定样例。

### 详情、确认和未知结果

详情先给出当前负责人、已有日期及状态，负责人选择与操作按钮分开。
默认选中当前负责人；未改选时“调整分工”禁用。三个选项（两名成人或共同）
**仅是排版样例**，不代表新增授权；正式选项仍必须由现有后端提供。

分工、完成、恢复未完成各有独立的修改前/后预览和取消按钮。按钮写“预览效果”，
而非“保存成功”。点击后明确反馈“没有保存修改”，原始固定样稿永远不变。
恢复未完成不是撤回 Pending 接受；完成不证明外部付款、预约或回复。

任务页底部的“更多设计状态”可查看长标题、空状态、UNKNOWN 样稿。
UNKNOWN 用独立状态区表达“不重复提交、核对原请求”，核对界面进一步说明没有
真实请求或回执可核实，既不报告成功，也不重试或替换请求身份。
这些不是对现有 UNKNOWN 恢复机制的实现、复制或修改。

## 设计系统

### 色彩与层次

| 语义 | Light | Dark |
| --- | --- | --- |
| 画布 | `#F8F7F4` | `#202421` |
| 内容表面 | `#FFFFFF` | `#292E2A` |
| 次级表面/禁用底 | `#F0F1EB` | `#333A34` |
| 主文字 | `#252A30` | `#EEEEE8` |
| 辅助文字 | `#64695F` | `#BCBFB5` |
| 强调/主按钮 | `#244D42` | `#C1D6C7` |
| 主按钮文字 | `#FFFFFF` | `#22372C` |
| 轻分隔线 | `#E3E5DD` | `#454D45` |
| 可交互边界 | `#838C80` | `#8D998E` |
| 待核实文字/底色 | `#805719 / #F6F0E3` | `#E3C38C / #3B3429` |
| 风险文字/底色 | `#8D403B / #F8EEEA` | `#E6B6AE / #3A2C2A` |
| 键盘焦点 | `#346F5C` | `#B5D4C0` |

正文/辅助/按钮/风险角色的自动对比检查均要求至少 4.5:1；主文字对画布约 13.5:1，
Light 辅助文字约 5.26:1，Dark 约 8.43:1。控件边界与表面、焦点与画布至少 3:1。
轻分隔线不是控件识别的唯一手段。禁用态使用文字和原生 disabled，不能只凭颜色。
这些是色彩角色检查，不能称为完整 WCAG 或屏幕阅读器认证。

页面内容不使用浮起阴影。只有原生模态弹窗和手机“更多”浮层使用柔和阴影，
目的是区别叠层；任务、数字和风险不会靠阴影争夺注意力。

### 字体、留白与组件

| 维度 | 规范 |
| --- | --- |
| 正文 | Segoe UI / PingFang SC / Microsoft YaHei / Noto Sans CJK SC / system-ui，15px，1.65 行高 |
| 中文主标题 | 桌面 36px / 手机 28px，600 字重；不用英文衬线强套汉字 |
| 英文主标题 | 本机 Georgia / Times New Roman，42 / 32px，400 字重，适当收紧字距 |
| 品牌 | 纯文字 Samas，38 / 30px；桌面附小号 Family OS，手机仅 Samas |
| 区块 / 任务标题 | 20 / 17px；手机 18 / 16px；长标题自然增高 |
| 辅助 / 说明 | 13px；手机任务元信息 12px；主操作字号不缩小塞字 |
| 间距 | 4、8、12、16、20、24、28、32、36、48px；区块大于行内距离 |
| 表面 / 控件 / 弹窗圆角 | 16 / 9 / 20px；手机弹窗 16px |
| 主操作 | 实色强调，仅用于确认样式预览；非上下文全局按钮不放进弹窗 |
| 次操作 | 清晰 1px 边界，44px 最小目标；hover 次级底色，pressed 强调浅底 |
| 上下文链接 | 仍用原生 button、44px 目标、hover 下划线和完整焦点框 |
| 输入/下拉框 | 原生 input/select，同样的边界、焦点、44px 高度与圆角；文本框仅在控件样稿展示，不实现搜索 |
| 分类切换 | 下划线表达当前分类；禁用的未来筛选单独标注，不能冒充已实现过滤 |
| 状态标签 | 简短文字为主，颜色辅助；未知不标“安全”，延期不标完成 |
| 空状态 | 说明为何没有内容，不编造任务，也不无条件要求清除不存在的筛选 |

中文不使用“项待确认”等量词拼接；首页采用短标签与轻量数字索引，详见下方 A1/A2。
英文允许更长标题和按钮自然换行，不以省略号、裁切或极小字体隐藏含义。
没有动画；同时显式尊重 prefers-reduced-motion。焦点框 3px、偏移 3px。

## 导航、主题与操作负担

五个主要入口保持首页、家庭待办、待确认、日程、安全中心。桌面是左侧导航，
手机是含安全区留白的底部导航；“更多”提供优惠、设置及唯一的语言入口。
桌面语言在顶部，手机移动同一个 DOM 控件，不在弹窗复制。
外观只有**设置与隐私 → 外观**一个入口，支持系统/浅/深，系统变化自动更新；
选择仅在标签页内存中，刷新重置。

浏览和导航不改变任何任务。原生 dialog 提供模态键盘边界；取消/Escape 恢复
触发按钮焦点，切页回到主标题和顶部。语言改变取消未完成的视觉草稿。
没有前端成员切换来冒充认证，没有后端连接失败时的样稿数据回退。

## 实际截图与 Before / After

截图是自动浏览器渲染，非生成图片。旧图使用仓库已归档的虚构资产，不代表
最新交互代码；不把历史占位符等已修复问题计作 UX2 的改进。
**任务前后对比**使用相同的三个内容/负责人/状态/日期组合。
首页旧图是 H1 诺拉/朱利安，UX2 使用 Clara/Devon，数量与案例不同，
因此只比较信息层级和视觉，绝不声称相同数据或效率提升。

| 场景 | Before | UX2 After |
| --- | --- | --- |
| 首页桌面 | [UX1](screenshots/ux1-spacing/after-home-desktop.png) | [Light](screenshots/ux2-calm-premium/home-light-1440.png) / [Dark](screenshots/ux2-calm-premium/home-dark-1440.png) |
| 首页手机 | [UX1 390](screenshots/ux1-spacing/after-home-390.png) | [Light 390](screenshots/ux2-calm-premium/home-light-390.png) / [Dark 390](screenshots/ux2-calm-premium/home-dark-390.png) / [320](screenshots/ux2-calm-premium/home-light-320.png) |
| 家庭待办 | [I4b：相同中性内容](screenshots/i4b/tasks-clara-desktop.png) | [Desktop](screenshots/ux2-calm-premium/tasks-light-1440.png) / [390](screenshots/ux2-calm-premium/tasks-light-390.png) / [320](screenshots/ux2-calm-premium/tasks-light-320.png) |
| 待确认 | [UX1](screenshots/ux1-polish/after-pending-390.png) | [Desktop](screenshots/ux2-calm-premium/pending-light-1440.png) / [390](screenshots/ux2-calm-premium/pending-light-390.png) / [320](screenshots/ux2-calm-premium/pending-light-320.png) |
| 任务详情 | [旧 I4b 确认风格](screenshots/i4b/assignment-preview-desktop.png) | [Desktop](screenshots/ux2-calm-premium/detail-zh-light-1440.png) / [390](screenshots/ux2-calm-premium/detail-zh-light-390.png) / [英文 Dark 320](screenshots/ux2-calm-premium/detail-en-dark-320.png) |
| 独立分工确认 | [旧 I4b](screenshots/i4b/reopen-dark-en-320.png) | [390](screenshots/ux2-calm-premium/confirm-light-390.png) / [320](screenshots/ux2-calm-premium/confirm-light-320.png) |
| 进度确认 | — | [完成](screenshots/ux2-calm-premium/complete-dark-320.png) / [恢复未完成](screenshots/ux2-calm-premium/reopen-dark-320.png) |
| 保守状态 | — | [UNKNOWN](screenshots/ux2-calm-premium/unknown-dark-320.png) / [空状态](screenshots/ux2-calm-premium/empty-dark-320.png) |

视觉与键盘自审修正了四个实际问题：窄屏确认按钮断成不自然的汉字行、页面切换后的
残留滚动位置、给所有确认复用一段过长说明、详情切换确认时重绘导致焦点落到 body。
最终稿使用短而明确的按钮、切页回顶、分工/进度对应的后果说明，并在每次模态状态
切换后将焦点放回关闭按钮。首个任务标题在 390/320 的固定导航上方无需滚动可见。
这些是设计检查结果，不是实际家庭可用性研究或生产有效性证明。

## Windows：无需安装的预览

在现有仓库根目录，复制到 PowerShell（不安装软件，不启动后端）：

```powershell
git fetch origin
if ($LASTEXITCODE -ne 0) { throw '获取分支失败，请停止。' }
git switch feat/ux2-calm-premium-design
if ($LASTEXITCODE -ne 0) { throw '切换分支失败，请先保存本地修改，不要重置或覆盖。' }
git pull --ff-only origin feat/ux2-calm-premium-design
if ($LASTEXITCODE -ne 0) { throw '更新分支失败，请停止，不要强制覆盖。' }
$preview = Join-Path (Get-Location) 'prototypes\ux2-design-preview\index.html'
if (-not (Test-Path -LiteralPath $preview)) { throw '请先进入 family-os 仓库根目录，并切换到 UX2 设计分支。' }
Start-Process -FilePath $preview
```

也可双击 index.html；保持同目录 styles.css 和 preview.js 在一起。
获取分支需要 GitHub 连接；文件在本机后，预览本身不需要 Python、Node、账号、
服务器或联网。关闭标签页即可退出；刷新恢复默认。
若组织策略禁止本地文件，不关闭浏览器保护、不上传托管，报告限制等待批准。

建议走查：首页 → 家庭待办 → 当前 Devon 负责人 → 改选 Clara → 取消；再次预览确认，
检查任务仍是 Devon → 完成/恢复未完成样稿 → 待确认/稍后处理 → 设置外观 → 手机宽度。
重点评价审美、信息密度和中文，不将“预览效果”当成真实保存。

## 测试与隔离证据

```powershell
node .\tests\browser\ux2-contract.test.js
.\.venv\Scripts\python.exe -m pytest -q tests/test_ux2_design_preview.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

可选截图重现（需环境已具备 Playwright/Chromium，脚本不安装任何依赖）：
`node tests/browser/ux2-preview.js --synthetic-only --screenshots`。
脚本支持 `UX2_CHROMIUM` 指定已有浏览器二进制。

新增标准库/Node 检查验证深冻结的固定样稿、两语言键完整性、无联网/存储/服务
依赖、严格 CSP、本地资源、颜色对比及必需 PNG 尺寸。实际浏览器检查覆盖两语言、
Light/Dark、1440/390/320、按钮/下拉框完整显示、首项可见、分类、当前负责人、
取消/确认无保存、完成/恢复、长标题、空状态、UNKNOWN、键盘焦点、系统主题更新、
手动覆盖、刷新重置和按需优惠。实际总数和完整数据库 CI 结果记录在 PR。

**测试环境限制必须保留：** 当前 Chromium 的管理员策略拒绝 file://（实测
ERR_BLOCKED_BY_ADMINISTRATOR）。没有禁用策略或绕过 CSP。自动截图/交互使用
测试脚本内只暴露三个固定文件的 127.0.0.1 临时渲染器；其他路径均 404，外部请求
被拦截，不含 API 或数据库。测试结束关闭该渲染器。它仅为截图测试资产，
不作为用户启动方式，也不证明 Windows 本地文件/CSP 行为。Windows Edge/Chrome、
系统字体、真实缩放、读屏器、手机硬件与最终视觉必须由用户验收。

样稿只新增本目录、设计说明、截图与轻量测试，以及必要的 README/roadmap 引用。
H0/H1/I3/I4a/I4b 原型、SQL、Command、授权、Session/Cookie/CSRF、接受、UNKNOWN、
提供方、OAuth 和冻结 Development/Holdout 均未改动、未接入。没有真实家庭数据、
模型调用、AI 内容生成、外部执行或浏览器持久化。静态成员标签不是认证，
样稿字段也不是未来 API 合同；正式实施须重新接入现有后端最小授权投影。

## 产品方向与剩余验收

1. 产品所有者已选定 A1 Editorial 首页方向；A2 保留为比较备选，不等于批准替换正式界面。
2. 工具栏的 Windows 原生字体和下拉框是否自然对齐？两行窄桌面布局是否清楚？
3. 未来负责人筛选仍需先批准后端查询、任务候选/授权边界，不能直接启用禁用按钮。

家庭待办、待确认、详情、深色和手机导航已获所有者认可，本轮保留，不重新设计。

ChatGPT 请独立核对：是否完全独立于现有应用？是否有真实数据/联网/写入/存储路径？
是否将未知设计为安全、预览设计为保存或负责人设计为授权？截图与执行报告是否诚实？
产品所有者须亲自审美和 Windows 验收后，才能另开正式 UI 实施阶段。
本 PR 保持 OPEN、UNMERGED，不自动合并。

## 产品所有者复审：首页 A1（已选定）/ A2（比较备选）

本轮从 PR #90 的 `8ad57e695b274a11c0a48a01fe8051d39a109370` 继续，
只修改独立样稿首页和工具栏。原首页截图 `home-*.png` 保留为该版 UX2 基准；
上方 UX1 对照仍保留。所有者随后选定 A1 方向；没有替换正式 H1/I4b。

首页顶部 **「首页方案对比 · 仅样稿」** 的两个原生按钮可来回比较，键盘可操作，
`aria-pressed` 标识当前项。A1 是产品所有者选定方向和默认项；此选择不授权替换正式应用。
两方案共用冻结 specimens、同一个详情/确认组件和全部原有导航；切换不写数据，
不保存偏好，刷新恢复 A1。主题仍只在设置修改，语言仍只有一个全局入口。

| | A1 · Editorial Home（编辑式） | A2 · Household Hub（家庭中心） |
| --- | --- | --- |
| 信息结构 | 主栏连续展示正式待办，再展示待确认；侧栏安放轻量数量索引、明确日期和安全核实入口 | 以 Clara & Devon 的共同空间为标题；行动区内明确分开「已加入待办」与「还需确认」；辅助区显示缺信息事项、日程与安全入口 |
| 视觉结构 | 无外框的任务行，标题、细分隔线和留白形成编辑节奏；数字为侧栏文本索引，不先占主区 | 一张共享行动表面承载任务和问题；辅助入口使用次级表面；较轻数字索引置于标题下 |
| 优点 | 任务最直接，扫读快，边框少，手机首屏更轻，信息密度更高 | 更明确的共同管理感，行动区域边界清楚；问题不会被误当成正式任务 |
| 代价 | 家庭共同空间感相对含蓄；手机上的日期与安全支持区位于任务之后 | 手机顶部和行动容器更占高度；比 A1 稍有面板感，但没有数字卡片阵列 |
| 推荐 | **所有者已选定 A1**：符合本轮「第一眼看家事而非统计」目标，且少用表面、不增加短任务高度 | 作为真实备选，适合更看重共同处理区域的偏好；继续保留作比较 |

两套均保持 2 项待完成、2 项当前待确认、1 项明确日期、1 项待核实的既有样稿语义。
没有把学校下一次活动建议冒充已经接受的学校活动；没有把缺失日期写成今天到期。
没有促销、AI 总结、情绪推断或新增案例。需要更多信息与稍后处理仍通过原待确认
入口可找回。A2 的行动区域是视觉分组，不是自动接受或新的任务生命周期。

### 本轮真实截图

所有图片由真实 Chromium 渲染；不是示意图，也不是生成式图片。

| 方案 | 桌面 1440 | 手机 390 | 窄屏 320 |
| --- | --- | --- | --- |
| A1 浅色 | [查看](screenshots/ux2-calm-premium/a1-home-light-1440.png) | [查看](screenshots/ux2-calm-premium/a1-home-light-390.png) | [查看](screenshots/ux2-calm-premium/a1-home-light-320.png) |
| A1 深色 | [查看](screenshots/ux2-calm-premium/a1-home-dark-1440.png) | [查看](screenshots/ux2-calm-premium/a1-home-dark-390.png) | [查看](screenshots/ux2-calm-premium/a1-home-dark-320.png) |
| A2 浅色 | [查看](screenshots/ux2-calm-premium/a2-home-light-1440.png) | [查看](screenshots/ux2-calm-premium/a2-home-light-390.png) | [查看](screenshots/ux2-calm-premium/a2-home-light-320.png) |
| A2 深色 | [查看](screenshots/ux2-calm-premium/a2-home-dark-1440.png) | [查看](screenshots/ux2-calm-premium/a2-home-dark-390.png) | [查看](screenshots/ux2-calm-premium/a2-home-dark-320.png) |

另见 [A2 英文深色 320](screenshots/ux2-calm-premium/a2-home-en-dark-320.png)。
同宽度下可直接比较上表与原 `home-*.png` 的数量优先结构。
上方家庭待办、待确认、详情、确认是上轮（7ba7025）重新渲染的基准。
本轮最新整体定位见后文 layout-after 系列，内部设计保持不变。

### 工具栏对齐依据

此前容器虽然 align-items:center，但文字继承不同的行高，select 使用 13px 而
相邻文字 12px，且外层语言容器未形成统一的对齐行。Windows 原生字体和控件
放大了这种差异。本轮统一为 **12px / 20px** 文字度量、**44px** 控件行，
语言容器与其父层明确 flex 居中；select 采用同字体、同高度和对称垂直内边距。
没有 top、translateY、负 margin 等文字位置补丁。

1440/1152 为同一行 Grid（提示 + 控件）；731–1000px 明确变为两行，提示在上、
成员和语言在下。手机保留原「更多」菜单的分行结构，不压缩文字到一行；
菜单内语言标签在 select 上方，保持唯一入口。控件水平间隔为 20px，语言组内 8px。
共享 workspace 现在使用 margin:0 auto，所有页面从顶部开始且仍横向居中。
原首页 margin-block 特例已删除；详见下方统一布局修复。

| 对照 | 修改前 | 修改后 |
| --- | --- | --- |
| 桌面中文 | [1440](screenshots/ux2-calm-premium/toolbar-before-1440.png) | [1440](screenshots/ux2-calm-premium/toolbar-after-1440.png) / [1152](screenshots/ux2-calm-premium/toolbar-after-1152.png) |
| 中等桌面明确换行 | — | [960](screenshots/ux2-calm-premium/toolbar-after-960.png) |
| 手机（修改后展开更多） | [390](screenshots/ux2-calm-premium/toolbar-before-390.png) / [320](screenshots/ux2-calm-premium/toolbar-before-320.png) | [390](screenshots/ux2-calm-premium/toolbar-after-390.png) / [320](screenshots/ux2-calm-premium/toolbar-after-320.png) |
| 英文深色 | — | [1152](screenshots/ux2-calm-premium/toolbar-after-en-dark-1152.png) |

前后整页截图除工具栏外也包含不同首页；请以顶部区域比较对齐，不误认成同一首页。

### 保留页面与实际验收

- Tasks/Pending/详情及确认函数未改，原列表密度、候选和禁用逻辑未改。
- 深色语义 token、全局按钮、弹窗、底部五导航的样式未改。
- 首页内部样式只作用于 .home-design；共享 workspace 的纵向定位已统一修复，其他组件样式不变。
- 上轮 HEAD `7ba7025` 曾对 `8ad57e6` 三资产基准做 **18 组逐像素比较**：Tasks、Pending、详情主体 ×
  浅/深 × 1440/390/320，全部一致（上轮结果）。本轮因有意整页上移改用内部相对几何及
  字体/间距/颜色/边界等计算样式比较；新顶部坐标另由严格的 384 案例矩阵验证。
- 浏览器常规运行 **93 组检查**；带基准比较运行 **111 组**。包括两方案 × 双语 ×
  深浅 × 1440/390/320、首项标题和详情按钮在手机固定导航上方可见、所有四入口、
  无横向滚动、长标题换行、无日期不推断、刷新不保存方案、原空态/UNKNOWN 与确认取消。
- 工具栏双语 × 深浅 × 1440/1152/960/390/320 共 **20 组**：同一行文字/控件垂直
  中心最大差不超过 1px，水平不重叠；两行桌面验证上下不重叠，手机验证菜单边界及控件。
- 自动测试不模拟清空冻结首页数据；空态仍复用原独立空态样稿，不引入新数据生成器。
- Windows 字体和原生 select 的实际观感仍须所有者验证；几何中心一致不等于已完成
  Windows 人工验收。测试环境的 file:// 管理员策略限制保持不变，未绕过浏览器保护。

正常运行命令不变。可在具备现有 Playwright 的环境为 ux2-preview.js 加 `--baseline-assets DIRECTORY`
执行主体内部相对几何与计算样式比较；该目录应包含基准提交的 index.html/styles.css/preview.js，
不是家庭数据目录。该参数只用于测试渲染器，不进入预览应用。完整 SQLite/PostgreSQL
实际结果及最终 HEAD 记录在 PR 描述，不能用早先 HEAD 的 CI 代替。

**A1 已选定，A2 保留比较。** 统一顶部布局仍须 Windows 人工复核；本 PR 保持
OPEN / UNMERGED，等待 ChatGPT 审查，不批准正式 UI 替换。


## Windows 复核修复：所有页面统一顶部布局

基于审查 HEAD `7ba702545f38b85bd583b693df729128f07892e1`。
这不是页面美术取舍：Grid 子项的上下 auto margin 会吸收剩余空间，即使写有
align-self:start，内容短的整块 workspace 仍会居中。原首页 :has 特例只掩盖了首页。
在实际 Chromium 的 1828×1000 视口，原日程工具栏 y=284.09375、主内容 y=408.09375；
原安全中心分别为 y=287.671875、411.671875，复现了 Windows 报告的大片顶部空白。

本轮运行样稿的唯一改动是：

```css
.workspace { /* 保留原 padding / width / max-width / align-self */
  margin: 0 auto;
}
```

删除首页 .workspace:has(.home-design) 的 margin-block 覆盖。不增加页面特例、
固定高度、绝对定位、负 margin 或 transform。横向仍以 max-width:1440px 居中。
原工具栏字号、行高、Grid/Flex 对齐与窄桌面换行保持不变。
同一视口中，无论首页、待办、待确认、日程、安全、优惠查询或设置，workspace 和
工具栏 y 均为 0，main 起点均为工具栏底部加既定间距。1440/1152/1828 为 124px，
960 的两行工具栏为 149px，手机为 132px；窗口变高不能改变这些坐标。
不同响应式断点的固定节奏可以不同，不能在同一断点随内容多寡变化。

### 实际浏览器证据

| 页面 | 修复前（1828×1000） | 修复后 |
| --- | --- | --- |
| 日程 | [Before](screenshots/ux2-calm-premium/layout-before-calendar-1828.png) | [1828](screenshots/ux2-calm-premium/layout-after-calendar-1828.png) / [390](screenshots/ux2-calm-premium/layout-after-calendar-390.png) |
| 安全中心 | [Before](screenshots/ux2-calm-premium/layout-before-security-1828.png) | [1828](screenshots/ux2-calm-premium/layout-after-security-1828.png) / [390](screenshots/ux2-calm-premium/layout-after-security-390.png) |
| A1 首页 | 已有上方 A1 基准 | [1440](screenshots/ux2-calm-premium/layout-after-a1-1440.png) / [390](screenshots/ux2-calm-premium/layout-after-a1-390.png) / [320](screenshots/ux2-calm-premium/layout-after-a1-320.png) |
| 家庭待办 | 已有上方待办基准 | [1440](screenshots/ux2-calm-premium/layout-after-tasks-1440.png) / [390](screenshots/ux2-calm-premium/layout-after-tasks-390.png) |

新旧截图均为实际渲染。日程和安全前后使用相同视口、相同数据、相同主题，
没有修改截图来移动内容。待办内部的行高、分工、字体和交互不变，只把整块页面
移动到统一顶端；任务详情与确认弹窗、深色 tokens、移动底部导航均未修改。

新增 `tests/browser/ux2-layout.js` 以真实 DOM rect 比较 **384 个页面/窗口案例**：
8 视图（A1、A2、家庭待办、待确认、日程、安全中心、优惠查询、设置）×
6 宽度（1828/1440/1152/960/390/320）× 2 高度（桌面 1000/1600，手机 844/1200）×
2 语言 × 2 主题。逐一检查 workspace/工具栏顶端、main 与工具栏间距、同宽跨页/跨高度
坐标一致、横向溢出、控件尺寸、手机首项操作与滚动末端可见控件不被底部导航遮挡。
每组先从首页切换到日程、安全中心；没有只凭截图存在就认定修复。

新增脚本仅显式 --synthetic-only 运行，不接受真实数据库或数据路径：

```powershell
node .\tests\browser\ux2-layout.js --synthetic-only --screenshots
node .\tests\browser\ux2-preview.js --synthetic-only
```

使用既有 Playwright/Chromium，不安装依赖；UX2_CHROMIUM 可选择已有浏览器。
--capture-before 是修复前证据采集模式，只记录当前资产的原始坐标和两张截图，
明确不报告回归通过；不可用它代替常规测试。所有资源仍限三个固定本地文件，
外部请求被拒绝，临时渲染器结束即关闭。没有真实数据、API、数据库或 provider。
Windows 直接打开仍使用前述 PowerShell 命令，退出为关闭标签页；本环境不绕过
file:// 管理策略。完整 pytest、浏览器结果及最终 HEAD CI 记录在 PR 描述。

本轮验证过程没有跳过失败项：新环境最初缺少既有锁定依赖导致 pytest 收集错误，
按未改动的 requirements-dev.lock 补齐后完整重跑。新布局脚本首次误把折叠区隐藏
控件作为末端可见操作，已修正为 :visible 并重跑全部 384 案例。旧绝对像素基准
因本次有意的整页上移失败，现比较内部相对几何及完整指定样式；顶部位置则必须
通过独立的严格零偏移/跨页/跨高度断言，不以任何定位补丁归一化页面。
