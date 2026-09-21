# 多宿主接入方案 对抗性评审记录 v0.3.0

> 日期:2026-09-21。评审对象:`docs/INTEGRATION-PLAN-v0.3.0.md` 初版。
> 方法:先实读官方文档核实事实(Codex:developers.openai.com/codex/plugins/build;Gemini:geminicli.com/docs/extensions/writing-extensions + 本机 figma/qt 权威实例;Cursor:官方文档 + 论坛),再从事实/架构/分发/体验/维护/安全/验证/定位八个方向攻击方案。
> 结论:**方案总体成立,但存在 2 个必须修复的设计缺陷、5 个需实测的风险点、3 处基于错误事实的评估需要修正**。逐条如下。

---

## 0. 官方文档实读结果(评审的事实基础)

### Codex CLI(developers.openai.com/codex/plugins/build,全文实读)

| 事实 | 对方案的影响 |
|------|------------|
| 清单:`.codex-plugin/plugin.json`(与 Claude 格式同源;`interface{}` 块支持 displayName/shortDescription/category/websiteURL/brandColor/icons) | 生成器需新增一份 Codex 清单 |
| 布局:skills/、hooks/hooks.json、.mcp.json、.app.json 在插件根;**Codex 声明直接兼容 legacy `.claude-plugin/marketplace.json`**,但 Codex 原生 marketplace 在 `$REPO_ROOT/.agents/plugins/marketplace.json`(存在时优先,忽略 legacy) | 双 marketplace 策略:保留 `.claude-plugin/`(Claude)+ 新增 `.agents/plugins/`(Codex 原生) |
| **Codex marketplace entry 必含 `policy: {installation, authentication}` 三件套 + `category`**,source 为 `{source, path}` 对象——与 Claude 条目格式(字符串 source + author)**不同** | 我们的 legacy marketplace 在 Codex 下能否完整解析**未验证**;原生清单规避此风险 |
| 安装:`codex plugin marketplace add owner/repo`(GitHub 简写/git URL/本地路径)→ 缓存 `~/.codex/plugins/cache/$MARKET/$PLUGIN/$VERSION/` | git 分发可行;npm/PyPI CLI 落盘后仍需用户执行 marketplace add |
| **官方公共插件目录:coming soon**——第三方暂时只能 git marketplace 分发 | v0.3 不指望目录收录;README 写 git 安装路径 |
| **hooks:与 Claude 相同的 hooks/hooks.json 布局,`${CLAUDE_PLUGIN_ROOT}` 也注入**(兼容层);但插件钩子默认 skip,**需用户 `/plugins` 里 review & trust** | posttooluse.py 可直接复用;信任步骤必须写进文档,否则钩子静默不生效 |
| 官方 PostToolUse 示例直接 `python3` 调脚本 | 我们的 post-tool-use 探测链照常工作 |

### Gemini CLI(geminicli.com/docs/extensions/writing-extensions + codelab + 本机实例)

| 事实 | 对方案的影响 |
|------|------------|
| **`skills/` 目录 + SKILL.md 原生支持**:"Gemini CLI automatically discovers skills bundled with your extension" | **推翻初版担忧**(初版以为 Gemini 无 skills 证据)——22 技能零改造直接进 extension |
| `gemini-extension.json` 字段:name/version/description/mcpServers{command,args,cwd}/settings[{name,description,envVar,sensitive}]/contextFileName;本机 figma/qt 两实例佐证 | 生成器产出最小清单即可(name/version/description/contextFileName) |
| **`contextFileName: "GEMINI.md"` 在每次会话开始注入上下文** | 规则层注入机制原生存在——等价于 SessionStart hook,CLAUDE.md 内容改名为 GEMINI.md 放入 extension |
| 安装:`gemini extensions install <git-url>` / `--path` / `gemini extensions link .`(开发);装到 `~/.gemini/extensions/<name>/`;分发走 git repo / GitHub Releases | **仓库根即 extension**:加 gemini-extension.json + GEMINI.md 即成,skills/ 已在根 ✓ |
| `${extensionPath}${/}` 变量;敏感 env 默认过滤 | 无 MCP 场景不涉及 |
| 注:官方页 banner 提及 unpaid-tier CLI 于 2026-06 被 Antigravity CLI 取代(免费层) | Gemini CLI 受众可能收窄——**降级为第二梯队优先级**(见裁决 #21) |

### Cursor(官方文档 + 论坛核实)

| 事实 | 对方案的影响 |
|------|------------|
| `.cursor/skills/` 放 SKILL.md(2.3.35+ 官方推荐) | 技能零改造 ✓ |
| hooks:项目级 `.cursor/hooks.json`(repo 根)/ 全局 `~/.cursor/hooks.json`;stdin/stdout JSON | hooks 存在,但**事件模型是 agent-loop stages,与 Claude 的 SessionStart/PostToolUse 命名不同**——session-start 注入规则在 Cursor 有无等价事件**需实测**(superpowers 的 hooks-cursor.json 用 snake_case `additional_context` 是活样本) |
| 无官方插件市场 | 分发 = CLI 落盘(项目级)或文档指引手工拷贝 |

---

## 1. 事实层攻击

**#1「Gemini 无 skills 支持」— 初版评估错误,已被官方文档推翻。**
裁决:✅ 修正。Gemini 有 skills 自动发现,且 GEMINI.md 提供原生规则注入——Gemini 的接入成本从"中"降为"低",但分发依赖 git URL 安装。

**#2「Codex 清单近亲、成本低」— 低估了三处。**
(a) marketplace entry 必含 policy 三件套,与 Claude 格式不同;(b) 官方目录 coming soon,短期只有 git 分发;(c) 插件钩子默认不被信任,需用户手动 trust——不写进文档用户会以为钩子坏了。
裁决:✅ 修正。采用双 marketplace 策略 + 文档明示 trust 步骤。

**#3「Codex 走 AGENTS.md 注入规则」— 有缺口。**
AGENTS.md 是**项目级**指令文件;Codex 插件本身没有 always-loaded 规则文件的概念(清单无 contextFile 字段)。我们的 CLAUDE.md 规则层在 Codex 宿主的注入途径只剩:(a) CLI 落盘 AGENTS.md 到项目(见 #6 的破坏性问题);(b) 塞进某个技能(违背路由设计)。
裁决:⚠️ 部分成立。Codex 宿主规则注入弱于 Claude/ZCode——接受降级,靠 AGENTS.md 落盘(修复 #6 后)+ PostToolUse 钩子补位。

**#4「Cursor hooks ✅」— 事件模型未对齐。**
Cursor hooks 真实存在但事件名/负载与 Claude 不同(SessionStart 等价物待实测)。
裁决:⚠️ 需实测。v0.3 先不做 Cursor hooks,只落 skills;.cursor/hooks.json 作为 v0.3.x 增量(实测事件后)。

## 2. 架构层攻击

**#5 版本断言从五处涨到七处以上。**
Codex `.codex-plugin/plugin.json`、Gemini `gemini-extension.json`、`.agents/plugins/marketplace.json` 的 version 全要进 publish.yml 断言——手工同步必炸。
裁决:✅ 成立。生成器**统一从一个 VERSION 常量派生**所有清单版本,publish 断言改为"所有清单版本一致"而非逐个 grep。

**#6 AGENTS.md 落盘是破坏性操作 — 方案的重大安全缺陷。**
authforge 实证:真实项目**已有自己的 AGENTS.md**(还有 CLAUDE.md/CODEBUDDY.md)。CLI `install --host agents` 若覆盖用户 AGENTS.md,直接违背 v0.2 承诺的"绝不触碰项目自有文件";即使追加也污染用户文件。
裁决:✅ **必改**。AGENTS.md 策略改为:(a) 目标不存在 → 落盘完整文件(首行注明来源与卸载方式);(b) 已存在 → **跳过并打印合并指引**(给出建议追加的标记段落让用户自己合),`--force-agents` 才允许追加带 `<!-- drogon-plugin begin/end -->` 标记的段落,uninstall 只删标记段。

**#7 `.agents/skills` 与宿主插件目录双落 → 技能重复发现。**
VS Code/Codex/ZCode 同时识别 `.agents/skills` 和各自插件目录时,同名技能重复(模型看到两份 description)。
裁决:✅ 成立。`install` 的 `all` 默认**互斥**:宿主有专有清单(Claude/ZCode/Codex/Gemini/Cursor)时**不落** `.agents/skills`;仅当选择 `--host agents`(无专有机制的宿主)时落。

## 3. 分发层攻击

**#8 npm/PyPI CLI 装的是"资产落盘",不是"宿主注册"。**
Codex 要 `codex plugin marketplace add`、Gemini 要 `gemini extensions install`——CLI 装完后仍需用户在宿主里执行一步。
裁决:✅ 成立(接受)。与 v0.2 行为一致(打印启用指引);指引按宿主精确化。

**#9 Gemini extension 安装会 clone 整个仓库。**
仓库含 tests/、scripts/、npm/、src/ 等——extension 用户拿一堆无关文件。
裁决:⚠️ 可接受但不优雅;若在意,发布分支或 release 附件只含 extension 所需文件。v0.3 先接受(官方也是这么装的,cloud-run mcp 同样整仓)。

## 4. 体验层攻击

**#10 22 技能全量塞进宿主 → 上下文成本。**
每技能 name+description 进入宿主的技能列表;Cursor/VS Code 的加载策略(全量列出 vs 按需)未验证。
裁决:⚠️ 部分成立。description 本就为一句话(触发导向),22 条 ≈ 1000-1500 token,可控;但**每个新宿主实测时把"上下文增量"列入验收项**。

**#11 scan 子命令输入模型不成立。**
posttooluse.py 的输入是 hook 的 tool_input JSON;CLI 化后输入应是文件路径列表——不能"封装了事"。
裁决:✅ 成立。scan 需要独立的输入层:扫文件路径(glob/显式列表),复用违规库,输出 human/json 两种格式;posttooluse.py 的扫描函数抽成共享模块。

## 5. 维护层攻击

**#12 十宿主 × 规范半年一变的维护成本被低估。**
实证:Cursor skills 是 2.3.35 新增、Codex 目录 coming soon、Gemini 免费 CLI 已被 Antigravity 替代——三家机制都在剧烈演化。
裁决:✅ 成立。分层承诺:README 明示「一级维护」(Claude/ZCode/Codex/Cursor/VS Code+agents 兜底)与「尽力维护」(Gemini/Qoder/CodeBuddy/Trae);每宿主一个结构性冒烟测试,规范变更时坏测试即知。

**#13 CI 矩阵爆炸(3 OS × 10 宿主 × 3 命令)。**
裁决:✅ 成立。宿主落点测试与 OS 无关(纯文件操作)——CI 里 per-host 测试只跑 ubuntu 一份,OS 矩阵只跑宿主无关的安装器/钩子测试。

## 6. 安全层攻击

**#14 Codex 钩子信任模型。**
默认 skip until trusted——文档必须写「装完执行 `codex plugin trust drogon`(或 /plugins 里 trust)」,否则 PostToolUse 在 Codex 静默失效,用户以为插件没用。
裁决:✅ 成立,纳入文档与 CLI 提示。

**#15 scan 读任意路径。**
裁决:✅ 成立。scan 限制在 cwd 之内(或显式 --root),拒绝 `..` 逃逸——沿用 v0.2 安装器的边界护栏风格。

## 7. 验证层攻击

**#16「真实会话验证」无客观标准。**
技能触发是概率行为,"AI 用了技能"怎么算验证过?
裁决:✅ 成立。定义两级验收:(a) **结构性**(自动化):install 后各宿主清单/落点/数量断言 + 宿主 CLI 无报错(`codex plugin list`、`gemini extensions list` 等);(b) **行为性**(手动,一次性):新会话问「给 /api/users 写个控制器」,检查响应体现路由表纪律(如主动引用技能名/遵守回调纪律)。行为性不做回归,结构性进 CI。

**#17 规范符合性验证依赖宿主官方校验器。**
Claude 有 `claude plugin validate`;Codex/Gemini 的校验入口(Codex:marketplace add 时的校验;Gemini:extensions install 时的校验)只在真安装时发生。
裁决:✅ 成立。CI 做不到;方案 C 阶段每宿主首次接入时人工跑一次真安装并把结果记录进本文件。

## 8. 定位层攻击(ROI)

**#18 drogon 受众在这些宿主的占比存疑。**
C++ 后端开发者主要集中在 VS Code(+Copilot)、Cursor、JetBrains;Codex/Gemini/Qoder/Trae/CodeBuddy 的 drogon 用户是长尾。
裁决:部分成立。但格式同源使边际成本极低(每宿主 ≈ 一份生成器模板 + 一份文档);真正贵的是**验证与长期维护**——已用 #12 分层承诺对冲。

**#19 一次 v0.3.0 吞十宿主,风险集中。**
裁决:✅ 成立。拆分:**v0.3.0 = Codex + Cursor + VS Code/Copilot + 通用兜底(agents)**;**v0.4.0 = Gemini + Qoder + CodeBuddy + Trae**(Gemini 因免费 CLI 被替换的受众不确定性,降入第二批;国内三家是纯生成器产物,零风险随时可加)。

**#20 与 superpowers 生态重复造轮子?**
裁决:不成立。superpowers 是通用技能库,我们是 drogon 领域库,互补。

---

## 9. 评审结论汇总

| 类别 | 裁决 | 动作 |
|------|------|------|
| 必改缺陷(2) | #6 AGENTS.md 破坏性、#11 scan 输入模型 | 方案修订,动工前落实 |
| 事实修正(3) | #1 Gemini 支持 skills、#2 Codex 成本、#3 Codex 规则注入弱 | 方案文档更新(本文档即记录) |
| 需实测(5) | #4 Cursor hooks 事件、#7 重复发现、#10 上下文增量、#17 各宿主真安装、Codex legacy marketplace 兼容度 | 列入 C 阶段验收清单,不阻塞动工 |
| 架构修订(4) | #5 版本单一来源、#7 all 互斥落盘、#13 CI 分层、#15 scan 边界 | 更新方案 |
| 排期修订 | #19 拆两版 | v0.3.0(四宿主+兜底)→ v0.4.0(Gemini+国内三家) |

**方案可行性判定:通过(带上述修订)。** 修订已同步至 `docs/INTEGRATION-PLAN-v0.3.0.md`。
