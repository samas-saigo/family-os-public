# Samas Family OS 离线原型外观

本功能基于已合并 UX1（PR #83）的同一 H1 页面。仅增加视觉配色，不创建另一个
应用、不连接 T1/G3b、真实账号、提供方或模型；现有布局、业务文案、授权、个人
决定、共享任务、CAS/重放和安全判断保持不变。PR #83 不修改、不重新打开。

## 唯一入口与使用规则

**设置与隐私 → 外观 / Settings & Privacy → Appearance**。
桌面从左侧“设置与隐私”进入；手机从“更多”进入同一设置。没有顶部主题按钮，
任务详情、事项确认和安全详情也没有外观快捷开关。

| 选择 | 行为 |
| --- | --- |
| 跟随系统 / Follow system（默认） | 读取浏览器报告的系统配色，系统变化时自动更新，不刷新页面 |
| 浅色 / Light | 覆盖系统偏好，始终使用浅色 |
| 深色 / Dark | 覆盖系统偏好，始终使用深色 |

从手动模式返回“跟随系统”立即读取当前偏好，并继续响应后续变化。
Windows、macOS 和移动浏览器均通过标准 `prefers-color-scheme` / `matchMedia`
信号工作，不根据 User-Agent 推断设备，也不收集系统身份。浏览器自身的覆盖设置
可能影响报告的偏好；应用遵循浏览器实际提供的值。

选择只保留在当前标签页内存中，不使用 localStorage、sessionStorage、Cookie、
数据库或服务。刷新后恢复“跟随系统”；同一标签页切换虚构成员或语言不会改变
外观。其他标签页、设备或家庭成员没有持久化同步偏好。确认“重新开始演示”会
像其他演示偏好一样恢复默认，取消重置则保持原选择。

外观选择立即生效，不是业务决定，不要求保存确认、不产生业务成功消息或历史。
系统主题变化只更新根元素的视觉属性，不重建页面或弹窗，不改变焦点、未保存
草稿、来源权限、任务或风险状态。主题不能把“未知”变成“安全”。

## 配色与实现边界

使用现有本地 CSS 的语义变量覆盖表面、文字、边框、交互状态和风险提示。
浅色保留 UX1 的白/灰和少量深绿；深色使用炭灰 `#202327`、面板 `#262a2f`、
控件 `#2d3238`，主文字 `#e6e8eb`、次文字 `#b5bdc8`。不以大面积纯黑、
高饱和色或新增装饰区分区域。原有 Dashboard、导航、列表、筛选、优惠、空状态、
弹窗、粘性确认操作、来源共享及安全提示均使用主题变量。

文本强调与主按钮填充分离，避免深色中出现白字配浅色按钮。原生表单控件通过
`color-scheme` 采用相应外观；焦点轮廓宽度、触摸尺寸、排版和响应式断点不变。
配色立即切换，不做按钮背景/边框颜色过渡，避免新字色与旧背景短暂混合而降低
对比度；悬停、按下和焦点反馈仍保留。CSS 的系统媒体查询覆盖延迟脚本执行前
的初始配色；手动模式设置后只由显式主题
决定，不再被系统媒体查询覆盖。

没有新框架、字体、外部资源、浏览器持久化或后端字段。新增的四条双语文字仅为
“外观”“跟随系统”“浅色”“深色”；既有产品文案及业务枚举不变。

## Windows 手动验收

检出本 PR 分支后，在仓库目录运行：

```powershell
Start-Process (Resolve-Path '.\prototypes\h0-workbench\index.html').Path
```

1. 设置与隐私 → 外观，确认默认“跟随系统”。
2. 在 Windows 设置 → 个性化 → 颜色切换应用浅/深色，页面应无需刷新即更新。
3. 选“浅色”后切换系统为深色，页面仍浅色；“深色”反向验证。
4. 返回“跟随系统”，应立即匹配当前系统状态，并继续响应后续变化。
5. 在未保存的事项确认打开时切换系统主题；确认内容和草稿应保留，取消不保存。
6. 检查中文/英文、键盘 Tab/方向键/Esc、320/390 宽度及浏览器缩放。
7. 刷新后应回到跟随系统，且没有真实账号、数据接入或外部操作。

macOS 可通过系统设置 → 外观验证；移动设备可通过系统显示/外观设置验证。
这些真实平台步骤需人工完成；自动测试使用 Linux Chromium 媒体模拟，不声称已
操作实际 Windows/macOS/手机系统。直接 file:// 的 CSP 和实际字体/缩放仍是人工门槛。

## 真实截图（仅批准的虚构数据）

同一入口、同一批准 fixtures，离线 Chromium 实际渲染并阻止所有网络请求。

| 场景 | 浅色 | 深色 |
| --- | --- | --- |
| 首页桌面 1440 | [浅色](screenshots/appearance/home-light-1440.png) | [深色](screenshots/appearance/home-dark-1440.png) |
| 首页手机 390 | [浅色](screenshots/appearance/home-light-390.png) | [深色](screenshots/appearance/home-dark-390.png) |
| 首页手机 320 | [浅色](screenshots/appearance/home-light-320.png) | [深色](screenshots/appearance/home-dark-320.png) |
| 英文确认 390 | [浅色](screenshots/appearance/confirm-light-en-390.png) | [深色](screenshots/appearance/confirm-dark-en-390.png) |
| 设置与外观桌面 | [浅色](screenshots/appearance/settings-light-1440.png) | [深色](screenshots/appearance/settings-dark-1440.png) |

## 验证与限制

- 49 项配色测试：40 个正常文本对比度组合至少 4.5:1，8 个焦点/控件边界组合至少 3:1，
  以及系统初始深色与显式深色配色一致性。
- 专项浏览器检查：初始化 CSS、系统动态变化、手动覆盖、唯一入口、打开的确认、
  无业务状态变更、重置/刷新、键盘焦点和两种语言。
- 实际 DOM 的配色/文字与控件尺寸检查覆盖浅/深色、两语言、1440/390/320，所有
  主页面及主要详情、确认和设置弹窗；既有 UX1 的放大等效布局与权限回归继续运行。
- 不以浏览器媒体模拟替代真实系统验收，不宣称认证、后台集成或持久化偏好已实现。
- 全量 SQLite/PostgreSQL 测试数和实际 CI 链接在本 PR 描述记录。

开发者验证（使用已安装 Playwright 和 Chromium，不启动服务）：

```text
python -m pytest -q tests/test_workbench_appearance.py
node tests/browser/appearance-interactions.js
node tests/browser/appearance-interactions.js --synthetic-only --screenshots
```

截图命令仅使用指纹匹配的现有虚构 fixtures，不读取家庭数据库或冻结评估集。
本 PR 保持 OPEN，由 ChatGPT、Muse 和用户 Windows 验收后人工决定是否合并。
