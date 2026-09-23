# 第二轮评审：规范符合性 / 功能正确性 / 多宿主兼容性

> 日期：2026-09-23。对象：`drogon-claude-plugin` v0.3.1（含第一轮专业化改造后的工作区）。
> 方法：全量只读取码取证（`文件:行号` + 原文）+ 官方规范实读核实（Claude Code 技能/插件文档、Codex 构建插件文档、Agent Skills 规范）。
> 定级标准（三档，全程一致）：**高置信度缺陷** = 已读码复现或有官方文档直接依据；**中置信度风险** = 逻辑成立但有条件/未触发；**需外部核实** = 静态无法定论，须真机验证。
>
> 本轮**不改动任何产物**，只产出结论。整改项见文末 §7。

---

## 0. 先回答：移除 SKILL.md 的 `version` 还符合规范吗？

**结论：符合，且比修改前更合规。`version` 本来就是违规字段。**

官方文档（`https://code.claude.com/docs/en/skills`）把 skill frontmatter 分成两条分发路径，两条路径的允许字段都是**封闭白名单**：

| 分发路径 | 允许的 frontmatter 字段 | `version` 是否允许 |
|----------|------------------------|-------------------|
| Claude Code 技能（任意层级，**含 plugin 技能**） | 字段表全集：`name` / `description` / `when_to_use` / `argument-hint` / `arguments` / `disable-model-invocation` / `user-invocable` / `allowed-tools` / `paths` / `shell` / `metadata` / `license` / `compatibility` | ❌ 不在表内 |
| claude.ai 上传、Skills API、`package_skill.py`；**Agent Skills 开放标准**（`.agents/skills`、Cursor、Codex、Gemini 的技能发现） | 仅 6 个：`name`、`description`、`license`、`compatibility`、`metadata`、`allowed-tools` | ❌ 不在白名单 |

规范对未知键的态度是**硬失败而非忽略**（原文："If you include any field the spec doesn't allow, packaging or upload fails with a **hard error** instead of ignoring the field"）。因此携带 `version` 属于跨路径兼容性风险（第一轮已识别）。

**现状核对（22 个 `SKILL.md` 全量）**

| 检查项 | 结果 |
|--------|------|
| 字段集合 ⊆ 白名单 | ✅ 全部为 `{name, description, license}` |
| `name` == 目录名 | ✅ 22/22 一致 |
| `description` 长度 | ✅ 53–123 字符（列表截断上限 1536） |
| frontmatter 首行为 `---` | ✅ 22/22 |
| YAML 特殊字符风险（`: `、`#`、引号、`<`/`>`） | ✅ 未发现（`drogon-create-controller` 含 `:param`，冒号后紧跟字母，非 `: `，安全） |
| `license` 是否合规 | ✅ 属 Agent Skills 规范字段（Claude Code 接受但不据此行动） |

**技能版本号去哪了**：由 `.claude-plugin/plugin.json` 的 `version` 统一承载 —— 这正是规范指定的位置（技能随插件整体发布，不需要独立的技能级版本）。若确有"每技能独立版本"的诉求，唯一合规落点是 `metadata`（自由键值映射，宿主不解释其内容）。

**本轮无任何修复动作。**

---

## 1. 规范符合性评审

### 1.1 `.claude-plugin/plugin.json` ✅ 合规

`name`（必需）存在；`version` / `description` / `author{name}` / `license` / `repository` / `homepage` / `keywords[]` 全部为规范内字段且类型正确；**无规范外自定义键**；`version` == `VERSION`。

### 1.2 `hooks/hooks.json` ⚠️ 1 处待确认 + 1 处自文档化缺失

| 项 | 实际 | 规范 | 判定 |
|----|------|------|------|
| 顶层 `description` | **缺失** | 可选（`{"description": <string>, "hooks": {...}}`） | 可选，但补上可自文档化（低成本） |
| 事件名 | `SessionStart` / `PostToolUse` | 合法 | ✅ |
| `matcher` | `startup\|clear\|compact` / `Write\|Edit\|MultiEdit` | 可选正则 | ⚠️ 见 §3.1（漏 `resume`） |
| `hooks[].type` / `command` / `timeout` | `"command"` / `"${CLAUDE_PLUGIN_ROOT}/..."` / `10` | 合法 | ✅ |
| `hooks[].shell` | `"bash"` | **不在文档字段表内** | ⚠️ 需外部核实（见 §4） |
| `hooks[].args` | 未使用（子命令内嵌在 command 字符串） | 可选数组 | ✅ 合法 |

### 1.3 `.claude-plugin/marketplace.json` ✅ 合规

`name` / `description` / `owner{name}` / `plugins[]` 齐备；条目含 `name` / `source`（字符串形态）/ `version` / `description` / `displayName` / `author` / `category` —— 均为官方目录字段。

### 1.4 多宿主清单 ✅ 结构自洽（Codex 有 2 处需外部核实）

- `.zcode-plugin/plugin.json`：`skills: "./skills"`、`hooks: "hooks/hooks.json"` 符合该宿主约定（有测试断言）。
- `.codex-plugin/plugin.json`：`skills: "./skills/"`、`hooks: "./hooks/hooks.json"` 均以 `./` 开头、相对插件根 —— 符合 Codex「清单路径规则」。
- `.agents/plugins/marketplace.json`：`source: {source: "local", path: "./"}`、`policy{installation, authentication}`、`category`、`version` 齐备。
- `gemini-extension.json`：`name` / `version` / `description` / `contextFileName: "GEMINI.md"` 正确。
- **版本一致性**：`VERSION`(0.3.1) 与 10 处落点（6 清单 + `pyproject.toml` + `npm/package.json` + `__init__.py` 双常量）**全部一致**，均有断言守护。

### 1.5 规范符合性结论

**无必须修复的规范违规项。** 两项低成本完善（`hooks.json` 补顶层 `description`、SessionStart matcher 补 `resume`）与两项待核实项（`shell` 字段、Codex `interface`），见 §3/§4。

---

## 2. 功能正确性评审

### 2.1 高置信度缺陷

#### C1 — `uninstall --host claude|zcode` 是空操作（bundle 永不删除）

- **证据**：`src/drogon_plugin/cli.py:643-668` 的 `_uninstall_hosts` 只有三个分支——`"skills" in kind`（`:648`）、`"rulefile" in kind`（`:654`）、`"instruction" in kind`（`:659`）；而 `HOSTS` 在 `:82-83` 把 claude/zcode 定义为 `kind == "bundle"`，三个 `in` 判定**全为 False** → 循环体什么都不做，仅把 host 从 `stamp["hosts"]` 移除（`:667`）。
- **复现**：`install --target P --host claude` 后 `uninstall --target P --host claude` → 输出"所选宿主无产物"，但 `P/.drogon-plugin/` 完整残留。
- **影响**：`--host` 装/卸不对称。npm 侧无 `--host`，其 `cmdUninstall` 直接删整目录，故只有 PyPI CLI 受影响。
- **定级**：高置信度缺陷（读码 + 逻辑可判定）。

#### C2 — 按宿主卸载会删掉仍被其它宿主共享的 `AGENTS.md`

- **证据**：`cli.py:659-664`，`instruction` 分支读 `stamp["instruction_files"][name]`，若为 `"full"` 则直接 `(project/name).unlink()` **整份删除**，不判断是否还有其它已安装宿主依赖该文件。
- **复现**：`install --target P --host codex`（`AGENTS.md` 不存在 → 记为 `full`）→ 随后 `uninstall --target P --host qoder` → `AGENTS.md` 被整份删除，codex 的规则文件消失。
- **影响**：**数据破坏**；涉及所有共享 `AGENTS.md` 的宿主（codex / qoder / copilot / agents）。
- **补充**：全量 `uninstall`（`cli.py:701-705`）按 stamp `full` 删除是**正确**的（确实由我们创建）；仅"按宿主"路径有此缺陷。指令文件的 rank 合并逻辑（`:471-473`、`:486-492`）本身正确，不降级。
- **定级**：高置信度缺陷。

#### C3 — `file_category` 用裸子串判定，`latest.cc` 被误判为测试文件

- **证据**：`hooks/posttooluse.py:200`：`if 'test' in base.lower() or base.lower().endswith('_test.cc') or ...`
- **复现**：`file_category("src/latest.cc")` → `"test"`（期望 `"cpp"`）。同理 `contest.cc` / `greatest.cc` / `fastest.cc` / `attested.cc`。
- **影响**：`rules_for("test")` 返回 `TEST_RULES + CPP_RULES`（`:222-229`），于是普通源文件会套用测试规则集——例如 `task.done()` 被 `\bdone\s*\(\s*\)` 命中而误报 `TEST.001`。hook 模式与 `--scan` 模式同时受影响。
- **定级**：高置信度缺陷（假阳性，且触发错误规则集）。

#### C4 — npm `findAssets()` 回退时把整个仓库（含 `.git`）复制进用户项目

- **证据**：`npm/bin/cli.js:40-49`，当 `npm/assets/` 不存在时 fallback 返回仓库根（因 `.claude-plugin/plugin.json` 在仓库根存在）；`copyAssets`（`:134-143`）→ `listFiles`（`:66-75`）**无任何忽略列表**，递归复制 `.git/`、`node_modules/`、`scripts/`、`tests/` 等。
- **触发条件**：从源码检出直接 `node npm/bin/cli.js install --target P` 且未先运行 `node scripts/sync-assets.mjs`。
- **影响**：产物体积爆炸 + 把版本控制内部对象泄漏进用户项目；随后 `verify` 的 `fileHashes` 会把它们全部视为受管文件。
- **为何 CI 未暴露**：`npm pack` 会触发 `prepack` → 生成 assets，故不触发回退；`tests/test_hosts.py` 的 npm 端到端测试带 `skipif(not (REPO_ROOT/"npm"/"assets").is_dir())`，恰好跳过该路径。
- **定级**：高置信度缺陷。

#### C5 — `--scan --format`（缺取值）抛 `IndexError`

- **证据**：`hooks/posttooluse.py:341-344`：
  ```python
  if "--format" in args:
      i = args.index("--format")
      fmt = args[i + 1]      # ← --format 为末位参数时越界
      del args[i:i + 2]
  ```
  scan 分支（`:333-348`）无 try 包裹。
- **复现**：`python hooks/posttooluse.py --scan --format` → traceback，非优雅失败。
- **为何未覆盖**：该分支不经 argparse（CLI 的 `--format` 有 `choices` 校验），单测未触达。
- **定级**：高置信度缺陷。

### 2.2 中置信度风险

#### M1 — `scan --format json` 在错误路径不输出 JSON
`cli.py:778` 在路径越界预检失败时 `print(..., file=sys.stderr); return 2`，**早于 JSON 输出**。CI 若用 `--format json` 解析 stdout 会拿到非 JSON。定级：中（需 `--format json` + 越界路径组合触发）。

#### M2 — `_MARKER_SECTION_RE` 与进入判据不一致，"有 begin 无 end"时静默写回
`cli.py:299-301` 用 `_MARKER_BEGIN in text` 作为进入替换分支的判据，但替换用的 `_MARKER_SECTION_RE`（`:71-73`）要求 begin…end **成对**。若文件含孤立 `<!-- drogon-plugin begin -->`（用户手改损坏），`in` 为真、`sub` 不匹配 → 原文写回、却仍返回 `"marker"` 并记入 stamp；后续 `uninstall --host` 以为可剥标记段而实际未剥。另 `count=1`（`:301`、`:317`）在多段标记时只处理第一段。定级：中（需用户把文件改坏）。

#### M3 — `rmtree` 未判目录
`cli.py:651-652`：`for d in sorted(base.glob("drogon-*")): shutil.rmtree(d)`，未先判 `d.is_dir()`。同名**文件**会抛 `OSError`（未被 catch，仅靠 `main` 兜底）。定级：中（条件触发）。

#### M4 — `_skills_ok` 在资产缺失时"非空即通过"
`cli.py:147-151` / `cli.js:94-98`：`expected == 0` 时退化为 `n > 0`。若随包 `skills/` 丢失，`cmd_verify` 的计数校验失去意义（并会打印 `技能数 N != 随包 0`，变成反向误报）。定级：中（需发行包残缺）。

#### M5 — `available_commands()` 依赖私有 API（**澄清：不会静默失效**）
`cli.py` 用 `parser._actions` + `argparse._SubParsersAction`。经核对：若结构变化返回 `[]`，能力契约检查会因 `[] != declared` **报错**（`test_hosts.py` 亦然）→ **响亮失败而非假绿**。`_SubParsersAction` 在 3.9–3.14 均存在。定级：低（已澄清，无需改动）。

### 2.3 已验证无问题（勿重复投入）

| 项 | 结论 |
|----|------|
| `_file_hashes` / `_drift_problems` | `skip` 与 `__pycache__` 过滤完备；旧版无 `hashes` 时正确静默；`upgrade` 会刷新清单 |
| 指令文件 rank 合并 | `full` 不被 `marker` 降级，逻辑正确 |
| 归属校验 / `_cleanup_empty_dirs` | 三重签名校验；空目录仅 `rmdir`，不会删非空目录 |
| 钩子正则 | 21 条**无灾难性回溯**（有界量词）；CPP.007 不误伤合法重载；CSP 统一 `IGNORECASE` 后未引入新误报 |
| `--scan` JSON 契约 | `rules` 与 `violations` 由同一 `hits` 就地生成，顺序与长度恒定，`zip` 安全 |
| `gen-host-artifacts.py` | 幂等；`plugins[0].version` 正则不会改错字段 |
| 版本一致性 | 10 处落点全一致且有断言 |

---

## 3. 多宿主兼容性评审

### 3.1 高置信度：SessionStart `matcher` 漏 `resume`（Claude 与 Codex 同时受影响）

- **证据**：`hooks/hooks.json:5` = `"startup|clear|compact"`。
- **外部依据**：Codex/Claude 的 SessionStart **来源（source）取值为 `startup` / `resume` / `clear` / `compact`**（两处独立佐证：文档说明"matcher 过滤的是启动来源(startup、resume、clear、compact)"；真实插件 `hooks.json` 示例使用 `startup|resume|clear|compact`）。
- **影响**：会话**恢复**（resume）时规则不注入。
- **为何无守护**：`tests/test_hooks.py` 只断言 `type` / `shell` / `timeout`，**不断言 matcher**。
- **定级**：高置信度（有官方依据，且 Claude 侧同样缺失）。

### 3.2 中置信度

| # | 项 | 证据 | 影响 |
|---|----|------|------|
| H2 | `rmtree` 未判目录 | `cli.py:651-652` | 同 M3 |
| H3 | 标记段半损坏静默写回 | `cli.py:299-301` vs `:71-73` | 同 M2 |
| H4 | `--format json` 错误路径无 JSON | `cli.py:778` | 同 M1 |
| H5 | `session-start` 的 JSON 转义不含其余 C0 控制字符 | `hooks/session-start:21-29` 仅转义 `\` `"` `\n` `\r` `\t` | 规则文件若含 `\f`/`\v` 等控制字符 → 产出**非法 JSON** → 注入静默失效（当前文件无此字符，属脆弱性） |

### 3.3 已验证兼容的项（勿重复投入）

- **ZCode 双清单不构成重复注册**：按优先级取首个（`.zcode-plugin/` 优先，`.claude-plugin/` 兼容）。
- **`.agents/skills` 互斥是刻意设计**：`ALL_HOSTS` 排除 `copilot`/`agents`；`--host copilot` 是用户显式 opt-in。
- **Codex 下 `${CLAUDE_PLUGIN_ROOT}` 可用**：Codex 为兼容既有插件会注入 `CLAUDE_PLUGIN_ROOT` / `CLAUDE_PLUGIN_DATA`（同时提供自己的 `PLUGIN_ROOT` / `PLUGIN_DATA`）。
- **Codex 插件钩子需用户 trust**：安装不会自动信任，需在 `/plugins` 审核 —— CLI 提示已包含该步骤。
- **Codex 默认钩子路径**：`hooks/hooks.json`（插件根）—— 与本仓库一致。
- **指令文件三态保护**：`AGENTS.md`/`GEMINI.md`/`CODEBUDDY.md` 的"不存在→full / 存在→跳过 / force→marker / 卸载只剥标记段"逻辑正确（除 C2 的按宿主路径外）。
- **Windows**：`run-hook.cmd` polyglot、Git Bash 定位顺序、`.gitattributes` 的 `*.cmd eol=lf`、各 Python 入口的 `_utf8_stdio` 均正确；Node 侧无 cp1252 问题。
- **`SKILL.md` 字段在各宿主可接受**：见 §0。

---

## 4. 被官方文档反证 / 未经证实，因此**不予整改**的项

> 这一节同样重要：它记录"看起来像缺陷但实际不是"的项，避免后续重复投入或做出错误改动。

| 推测 | 核实结果 | 处置 |
|------|----------|------|
| `.codex-plugin/plugin.json` 的 `interface` 块缺 `longDescription` / `developerName` / `capabilities` / `defaultPrompt` 四个 **validator 必填**字段，会导致 `codex plugin marketplace add` 失败 | **未被证实**。Codex 构建插件文档明确：「`.codex-plugin/plugin.json` 是必需的入口文件。**其他清单字段都是可选的**」，且 `interface` 内**未标注任何必填项**；文档给出的最小可运行示例仅用 `name` / `version` / `description` / `skills` 四个字段 | **不修改**，登记为真机核实项 |
| `plugin.json` 显式声明 `hooks` 会被 Codex scaffold validator 拒绝 | **被官方文档反证**：「如果在 `.codex-plugin/plugin.json` 中定义了 `hooks`，Codex 会使用清单中的条目，而不是默认的 `hooks/hooks.json`」；「若放在默认的 `./hooks/hooks.json`，则**不需要**在清单里写 `hooks` 条目」。我们声明的正是 `"./hooks/hooks.json"` —— 与默认路径同文件，**行为等价** | **不修改**（可选简化，非缺陷） |
| 22 个 `SKILL.md` 正文不含 `## 禁止模式清单` 章节 | **设计如此**：该章节位于 `references/code-guide.md`，`SKILL.md` 的「参考文件」行只是引述，且已有测试断言其真实存在 | 非问题 |
| `hooks.json` 未使用 `args` 数组 | 可选字段，省略合法 | 非问题 |
| `skills` / `hooks` 路径写法在不同宿主清单间不一致（`"./skills"` vs `"./skills/"`） | 各自宿主均接受；无规范要求统一 | 非问题 |

---

## 5. 需真机核实清单（静态无法定论；作为人工验收项）

| # | 待核实 | 为什么必须真机 | 核实方法 |
|---|--------|----------------|----------|
| V1 | Codex 对 `hooks.json` 中未知字段 `shell` 的容忍行为（忽略 / 校验失败） | Codex hooks 无独立 JSON schema；未知字段策略无公开文档 | 真机 `codex plugin marketplace add` + 触发 hook，观察是否报错与是否执行 |
| V2 | Codex 对 `PostToolUse` matcher 中 `MultiEdit`（Claude 专有工具名）的反应 | Codex 文件编辑工具为 `apply_patch`（别名 `Edit`/`Write`），`MultiEdit` 对其无意义 | 真机验证 `Write\|Edit` 可命中、`MultiEdit` 不导致错误 |
| V3 | Codex `interface` 是否需要更多字段 | 官方文档只说明"其余字段可选"，未给必填清单 | 真机 `codex plugin marketplace add` 观察校验输出 |
| V4 | Trae 是否识别 `.mdc` 扩展名与空值 `globs:` | Cursor 与 Trae 当前共用同一份 `.mdc` 内容（`description` + 空 `globs` + `alwaysApply: true`） | 在 Trae 打开项目确认规则是否生效 |
| V5 | Cursor 空值 `globs:` 的行为 | `alwaysApply: true` 时空 globs 预期被忽略，但未实测 | Cursor 中确认规则生效且无告警 |
| V6 | `.agents/plugins/marketplace.json` 的 `source.path: "./"` 在 Codex 缓存安装下的解析基准 | "marketplace 与插件同根"形态在规范中无样例；本地插件 `$VERSION` 为 `local` | 真机安装后检查 `~/.codex/plugins/cache/...` 内容完整性 |

> 建议沿用既有 `docs/INTEGRATION-PLAN-v0.3.0.md` Phase C 的"每宿主真安装一次"清单执行，并把结果回填到本表。

---

## 6. 低价值观察（记录，不建议本轮处理）

- 若干清单字段（`plugin.json` 的 `description`/`author`/`license`/`repository`/`homepage`/`keywords`、marketplace 顶层 `name`/`owner`/`description`、`gemini-extension.json` 的 `description` 等）当前**未被任何测试断言取值**。E 档收益、中档成本，可在需要时纳入一致性门禁。
- `docs/` 下 5 份历史文档、`PRD/` 下 2 份文档未被清单/脚本引用（属正常的历史资料，非死文件）。

---

## 7. 整改项（本轮执行）

| ID | 缺陷 | 等级 | 修复方向 |
|----|------|------|----------|
| C1 | `uninstall --host bundle` 空操作 | 高 | `_uninstall_hosts` 改为 **kind → 动作显式映射**，补 bundle 分支（删 `.drogon-plugin/`） |
| C2 | 按宿主卸载误删共享指令文件 | 高 | 引入**引用计数**：仅当移除本批宿主后无人再引用且 stamp 记 `full` 才整删，否则剥标记段 |
| C3 | `file_category` 子串误判 | 高 | 改为路径段精确匹配 + 文件名前后缀精确匹配，移除裸子串判定 |
| C4 | npm 回退整仓复制 | 高 | 回退路径加受管资产白名单 + 忽略 `.git`/`node_modules` 等，并显式告警 |
| C5 | `--scan --format` 缺取值崩溃 | 高 | 输出用法提示并返回 2（不再 traceback） |
| H1 | SessionStart matcher 漏 `resume` | 高 | matcher 补为 `startup\|resume\|clear\|compact`；补顶层 `description` |
| H2 | `rmtree` 未判目录 | 中 | 先判 `is_dir()` |
| H3 | 标记段半损坏静默写回 | 中 | 用 `_MARKER_SECTION_RE.search` 作进入判据 |
| H4 | `--format json` 错误路径无 JSON | 中 | 错误路径也输出含 `error` 字段的 JSON（纯增量） |
| H5 | `session-start` 控制字符转义不全 | 中 | 拼装前剔除 C0 控制字符（保留 `\t`/`\n`），`tr` 不可用时优雅降级 |
| H6 | 无扩展名钩子脚本（`hooks/session-start`、`hooks/post-tool-use`）**未被 `.gitattributes` 固定为 LF**（`git ls-files --eol` 显示 `attr/` 为空）；按扩展名的 `*.sh`/`*.py` 规则覆盖不到它们 | 高（Windows 上 `core.autocrlf=true` 克隆即触发；bash 会把 `\r` 当成命令的一部分 → 钩子静默失效） | `.gitattributes` 显式声明 `eol=lf`；门禁断言声明存在 + 测试断言磁盘无 CRLF |

> H6 由对抗性复核的"CRLF"线索追查发现。注意复核最初给出的"CRLF 导致孤立标记清理失效"经**实证为误报**：`Path.write_text` 在 Windows 写出 CRLF，但 `Path.read_text` 默认启用 universal newlines，读回的是 LF，故正则不会失配。真正的换行风险在 H6。

**同时**：把 C1/C2/H1/H5 的约束固化为自动化门禁与回归测试（见计划），避免同类缺陷再生。
