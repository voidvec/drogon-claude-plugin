# drogon-claude-plugin 专业化改进调研报告

> 日期：2026-09-23。调研对象：`drogon-claude-plugin` v0.3.1。
> 方法：全仓库源码只读取证（文件路径 + 行号 + 原文片段）→ 权威规范实读核对（Agent Skills / Claude Code 插件文档）→ 供应链安全静态扫描 → 按 A/B/C/D 四维归类、加权定级。
> 范围说明：按需求，A（工程化与质量门禁）、B（插件内容质量）、C（分发与生态）三维度深挖，D（治理与文档）仅列**必需项**；**本轮只做诊断，不引入任何新工具链**，工具链选型仅在第 8 节给出建议。
> 证据可复核，凡引用均标注 `相对路径:行号`。

---

## 1. 结论摘要

仓库的专业化底子**明显高于同类第三方插件**：单一版本来源（`VERSION`）+ 生成器 `--check` + CI 三平台矩阵 + 发布期 `tag == VERSION` 断言 + 多宿主"绝不触碰用户文件"的三态保护 + 违规扫描路径边界护栏，这些是许多成熟项目都未必具备的工程约束。

本次体检发现的问题**集中在"约束的覆盖度"而非"约束的有无"**：

| 维度 | 核心判断 | 高价值问题数 |
|------|----------|--------------|
| A 工程化与质量门禁 | 门禁"有骨架、缺闭环"：硬编码未收敛、校验有盲区、CI 无缓存无 pin | 6 |
| B 插件内容质量 | 存在**一处规范级不符**（SKILL.md 携带非允许字段 `version`），其余为一致性与守护缺口 | 7 |
| C 分发与生态 | 双 CLI 能力不对等且**无测试锁定**，verify 语义各有盲区，缺漂移检测 | 6 |
| D 治理与文档 | 仅 3 项必需缺口（技能作者手册缺失、CONTRIBUTING 版本清单过期、README 无互校） | 3 |

**最高优先级单点收益（P0 第一位）**：22 个 `SKILL.md` 全部携带的 `version:` 字段**不在 Agent Skills 规范的允许字段清单内**。移除它可**同时**解决两件事——消除宿主包装/上传时报 `Unexpected key(s) in SKILL.md frontmatter` 的兼容性风险，并彻底根除当前 `0.1.0 × 11 / 0.2.0 × 11` 的版本漂移（该字段无任何测试约束，属于"改了没人知道"的纯负债）。

---

## 2. 现状量化基线

| # | 指标 | 实测值 | 主要证据 |
|---|------|--------|----------|
| 1 | 硬编码 `22`（技能数量语义）出现处 | **34 处 / 16 个文件** | §5.A1 |
| 2 | 独立硬编码"技能数"常量位置 | **7 处**（cli.py / cli.js / test_structure / test_hosts×2 / gen-host-artifacts / dev-smoke×2） | `src/drogon_plugin/cli.py:55`、`npm/bin/cli.js:28` |
| 3 | 技能 frontmatter 字段数 | **仅 3 个**（name / description / version） | 22 个 `SKILL.md` |
| 4 | 技能 `version` 漂移 | **22/22 未对齐插件版本；两套值 0.1.0×11、0.2.0×11** | `skills/*/SKILL.md:4` |
| 5 | `version` 取值是否被测试引用 | **否**（仅断言存在） | `tests/test_structure.py:63` |
| 6 | SKILL.md 章节模板一致性 | **22/22 统一**（使用场景/输入参数/输出/示例/参考文件） | — |
| 7 | code-guide 行数区间 | **78 – 310 行** | §5.B2 |
| 8 | code-guide 含 0 个 ```cpp 代码块 | **3 个** | create-controller / db-config / cmake |
| 9 | "禁止模式清单"章名分裂 | **3 套**（中文专章 5 / 英文专章 10 / 无专章 7） | §5.B3 |
| 10 | SKILL.md 声明"含禁止模式清单"但实际无该章 | **7 个** | §5.B3 |
| 11 | 钩子规则总数 | **21 条**（CPP 9 + CSP 6 + CONFIG 3 + TEST 3） | `hooks/posttooluse.py:33-117` |
| 12 | 有正例的规则 | **21/21** | `tests/test_posttooluse.py` |
| 13 | **无反例（误报无守护）的规则** | **8 条**（C1/C2/C3/C4/C9/S2/S4/T3） | §5.B5 |
| 14 | CSP 规则实际启用 IGNORECASE | **0 条**（注释宣称启用，实现未启用） | `hooks/posttooluse.py:75` vs `:76-91` |
| 15 | PyPI ↔ npm 命令差集 | js **缺 2 个命令**（scan / hosts）+ 4 个参数 | §5.C1 |
| 16 | CLI 能力差异是否有测试锁定 | **无** | §5.C1 |
| 17 | CI 未 pin 版本的 pip 安装 | **4 处** | `ci.yml:49,91,98`、`publish.yml:41` |
| 18 | CI 未 pin SHA 的 action | **8 处**（ci 3 + publish 5） | §5.A4 |
| 19 | CI 缓存启用 | **0** | §5.A4 |
| 20 | 覆盖率 / lint / 类型检查步骤 | **0 / 0 / 0** | §5.A4 |
| 21 | 未被测试覆盖的一致性约束 | **≥9 项** | §5.A5 |
| 22 | 死代码 / 占位 / 弱断言 | **8 处** | §5.A2 |
| 23 | 技能目录内可执行脚本 | **0 个**（22 个技能全为纯 Markdown） | §4 安全扫描 |

---

## 3. 对标基准（权威规范实读结论）

### 3.1 Agent Skills / Claude Code 技能规范

实读 `https://code.claude.com/docs/en/skills` 与 `https://code.claude.com/docs/en/plugins`，得到三条对本仓库有直接约束力的事实：

1. **SKILL.md frontmatter 存在两条路径、两份允许字段清单**。规范原文给出的失败文案（打包/上传校验）为：

   > `Unexpected key(s) in SKILL.md frontmatter: argument-hint. Allowed properties are: allowed-tools, compatibility, description, license, metadata, name`

   并明确区分两条分发路径：

   | 分发路径 | 可用 frontmatter 字段 |
   |----------|----------------------|
   | Claude Code 技能（任意层级，**含 plugin 技能**） | 文档字段表中的全部字段（`name` / `description` / `when_to_use` / `argument-hint` / `arguments` / `disable-model-invocation` / `user-invocable` / `allowed-tools` / `paths` / `shell` / `metadata` / `license` / `compatibility`） |
   | claude.ai 上传、Skills API、`package_skill.py` 打包；以及 **Agent Skills 开放标准**（`.agents/skills` 路径） | 仅 6 个：`name`、`description`、`license`、`compatibility`、`metadata`、`allowed-tools` |

   规范对违规字段的态度是**硬失败而非忽略**（"packaging or upload fails with a hard error instead of ignoring the field"）。

   → **`version` 两份清单里都不存在**：既不在 Claude Code 字段表中，也不在 Agent Skills 的 6 字段白名单里。本仓库同时通过 `.agents/skills`（VS Code / 通用兜底）分发技能，因此**必须**满足 6 字段白名单。
   **对本仓库的含义**：22 个 `SKILL.md` 的 `version:` 属规范级不符，是**跨路径兼容性风险**；若需保留每技能版本信息，唯一合规落点是 `metadata`（自由格式键值映射，供自身工具读取，宿主不会解释其内容）。

   **附带发现（与 B4 直接相关）**：`description` 与 `when_to_use` 的合计文本在技能列表中**截断于 1536 字符**；且技能列表总体有**上下文预算**（默认为模型上下文窗口的 1%，可用 `skillListingBudgetFraction` 调整，`/doctor` 可查看占用）。这意味着"22 个技能的 description 总成本"是**有官方量化口径**的，触发词应写在 `description` 内而非单独新增 `when_to_use`（后者不在 6 字段白名单内，会破坏 `.agents/skills` 路径）。

2. **插件组件目录必须在插件根**：`.claude-plugin/` 只放 `plugin.json`，`skills/`、`hooks/`、`commands/`、`agents/` 等一律位于插件根。→ 本仓库结构**正确**，无需改动。

3. **`hooks/hooks.json` 支持顶层 `description` 字段**，hook 条目支持 `type` / `command` / `args` / `timeout`。→ 本仓库缺一个可选但有益的顶层 `description`（自文档化）。

### 3.2 版本与发布基准

`VERSION` 单一来源 + 生成器同步全部清单 + 发布期断言，是**优于业界常见做法**的模式；本报告不改动该模式，只把它扩展到尚未覆盖的产物（技能清单、能力矩阵、README 计数）。

---

## 4. 供应链安全扫描结论

扫描范围：`skills/`（22 个技能）与 `hooks/`（5 个文件 + `posttooluse.py`）。方法：本地静态只读分析（未执行任何技能代码）。

| 检测项 | 结论 |
|--------|------|
| 技能目录内可执行资产 | **0 个非 Markdown 文件**（`skills/` 递归统计 `Extension -ne .md` 计数为 0） |
| 提示注入 / 越权指令（"忽略以上指令"、system prompt、jailbreak） | 未发现 |
| 编码混淆（base64 / ROT13 / `fromCharCode` / 零宽字符 / Unicode 方向控制符） | 未发现（唯一 `base64` 命中为 `skills/drogon-gen-session-auth/references/code-guide.md:173` 的**防御性建议**：提示 cookie 值注入风险，需先编码） |
| 硬编码凭据 / 私钥 | 未发现 |
| 危险/破坏性命令（`rm -rf` / `mkfs` / `dd if=` / `reg delete` / `format`） | 未发现 |
| 子进程与网络 | 全部 `subprocess` 命中位于 `tests/`（`test_posttooluse.py:11,159,175`、`test_hosts.py:259,261`、`test_hooks.py:15,51,63,91`）与 `scripts/`（`dev-smoke-test.py:11,20`、`dev-smoke-test.mjs:7`），均为**显式参数列表 + `shell=False`**；hooks 全部离线（读取 stdin / 本地文件，无出站请求） |

**结论**：未发现中危及以上风险。22 个技能为纯文本知识资产，无代码执行面；风险面集中在 `hooks/` 与两个 CLI，而三者均无网络访问、无凭据读取。**本项不产生改造项**，仅保留为基线记录。

---

## 5. 差距清单

格式：**ID / 现状证据 / 为什么是问题 / 对标 / 改造方向**。

### A. 工程化与质量门禁

#### A1 — 技能数量无单一来源（P0）

- **现状**：`22` 以 7 处独立常量/断言存在——`src/drogon_plugin/cli.py:55`（`_EXPECTED_SKILLS = 22`）、`npm/bin/cli.js:28`、`tests/test_structure.py:16`、`tests/test_hosts.py:148,180`、`scripts/dev-smoke-test.py:80-81`、`scripts/dev-smoke-test.mjs:71`；另有 34 处文案出现在生成器（`scripts/gen-host-artifacts.py:76,103`）、双语 README（各 5 处）、`npm/README(zh).md`（各 2 处）、`AGENTS.md:5` / `GEMINI.md:5`、`.codex-plugin/plugin.json:25`、`.github/workflows/ci.yml:35`（`ls -d skills/*/ | wc -l" -eq 22`）。
- **为什么是问题**：新增/下线一个技能需要**人工同步 7 处常量 + 若干文案**，漏一处即产生静默不一致（测试断言与实现各说各话，CI 仍绿）。仓库已经用"`VERSION` 单一来源 + 生成器 `--check`"解决了版本类的同类问题，但技能数量没有享受到同一模式。
- **对标**：单一事实源（Single Source of Truth）原则；仓库自身既有成功实践。
- **改造方向**：技能数量一律由 `skills/` 目录**实枚举**派生（禁止字面量）；文案中的数量由生成器注入或由一致性门禁校验。

#### A2 — 死代码 / 占位代码 / 形同虚设的断言（P0）

- **现状（8 处）**：
  1. `src/drogon_plugin/cli.py:63` `_EXPECTED_HOOK_EVENTS = 2` —— **定义后从未被引用**（对照 `npm/bin/cli.js:249` 有使用）。
  2. `tests/test_hosts.py:258` `rc = gen.__name__  # placeholder to keep referrer honest; actual call below` —— 死变量 + 语义可疑的注释。
  3. `tests/test_hosts.py:118` `assert gen.check(_version()) == [], gen.check(_version())` —— 断言消息中**重复执行** `gen.check`。
  4. `tests/test_posttooluse.py:186-187` 与 5. `tests/test_hooks.py:172-173` —— `if __name__ == "__main__": sys.exit(0)` **空操作**（同仓库其它文件为 `pytest.main([__file__])`）。
  6. `tests/test_structure.py:71` `assert len(...) >= 40` —— 实际最薄 78 行，**阈值永不触发**。
  7. `tests/test_posttooluse.py:1-4` docstring 声称"every pattern … gets should-match and should-not-match fixtures"，实际 8 条规则无反例（见 B5）。
  8. `scripts/sync-assets.mjs:107` `typeof ok === 'string'` —— 冗余分支（`check()` 只返回 boolean）。
- **为什么是问题**：死代码与虚设断言会**给出虚假的安全感**——CI 全绿并不代表约束生效；后续维护者会误信已被守护。
- **对标**：测试有效性原则（断言必须可失败）。
- **改造方向**：删除死常量与占位；把弱阈值改为与当前实际水位匹配的下限；修正与实现不符的 docstring。

#### A3 — 双资产同步器平行实现，无一致性契约（P1）

- **现状**：`scripts/sync-assets.py` 与 `scripts/sync-assets.mjs` 各自的 `ASSETS` / `FILES` / `IGNORE_DIRS` 常量当前**取值一致**（`sync-assets.py:18,21,25` vs `sync-assets.mjs:15,16,20`），但**行为严格性不同**：mjs 的 `check()` 额外检测目标目录是否混入中间产物（`sync-assets.mjs:71-73`），py 版**不检测**；两者无任何测试保证常量等价。
- **为什么是问题**：两侧任一处新增资产类别（例如未来新增 `commands/`）时，另一侧会静默漏同步，且 CI 只跑各自 `--check`（对"漏了某类别"不敏感）。
- **对标**：仓库自身"单一事实源"原则在双实现场景下的应用。
- **改造方向**：抽取常量事实源并由一致性门禁校验两侧等价；补齐 py 版对中间产物的检测，使两者严格性对齐。

#### A4 — CI 质量门禁缺口（P0/P1）

- **现状**：
  - **未 pin 版本的 pip 安装 4 处**：`ci.yml:49`（`pip install pytest`）、`ci.yml:91`（`pip install build pytest`）、`ci.yml:98`（`pip install dist/*.whl`）、`publish.yml:41`（`pip install build`）。
  - **未 pin SHA 的 action 8 处**：`ci.yml:21,23,85`（`checkout@v4` / `setup-python@v5` / `setup-node@v4`）；`publish.yml:19,22,46,52,65`（含 `pypa/gh-action-pypi-publish@release/v1`、`softprops/action-gh-release@v2`）。
  - **缓存 0 处**（无 `actions/cache`、无 `setup-*` 的 `cache:`）。
  - **覆盖率 / lint / 类型检查 0 处**（`ci.yml:54` 仅 `py_compile` 单文件语法检查）。
  - 另：`ci.yml:35` 的 `wc -l -eq 22` 是 A1 的硬编码复现点。
- **为什么是问题**：依赖浮动（`pytest` 无版本）与 action 浮动（major tag 可被重定向）是**供应链风险**，与仓库已有的"零依赖、安全护栏"自我定位不匹配；无缓存导致三平台矩阵重复下载。
- **对标**：GitHub 官方安全加固建议（Pin actions to a full-length commit SHA）；OpenSSF Scorecard 的 Pinned-Dependencies 检查项。
- **改造方向**：pin 依赖版本（可用 `requirements-dev.txt` 或显式版本）与 action SHA；开启 pip/npm 缓存；（覆盖率/lint 见第 8 节建议）。

#### A5 — 存在 ≥9 项未被测试覆盖的一致性约束（P0）

- **现状**：下列约束**无任何测试**：
  1. 双语 README 互校（`README.md` ↔ `README.zh-CN.md`）；
  2. README 技能表格行数（`README.md:105-128` 与 `README.zh-CN.md:105-128` 各 22 行）；
  3. 技能 `version` 取值；
  4. SKILL.md 声明"含禁止模式清单" ↔ code-guide 实际章节（7 处不符）；
  5. PyPI ↔ npm CLI 能力 parity；
  6. `hooks.json` 的 `matcher` 字符串（`tests/test_hooks.py:162-169` 只查 `type/shell/timeout`）；
  7. code-guide 章节结构（仅 `>= 40` 行阈值）；
  8. `CONTRIBUTING.md` / `CHANGELOG.md` 与实现的一致性；
  9. `npm/README(zh).md` 与主 README 的一致性。
  已覆盖（值得肯定）：`GEMINI.md == AGENTS.md`（`tests/test_hosts.py:89-92`）、`AGENTS.md` 可由 `CLAUDE.md` 复现（`:121-123`）、7 个清单版本 == `VERSION`（`:95-114`）。
- **为什么是问题**：文档与产物的一致性靠"人记得改"，而仓库有 4 份 README/规则文件互相关联，遗漏概率高。
- **改造方向**：新增跨产物一致性门禁脚本并入 CI（见 A1/A3/B3/C1 的具体校验点）。

#### A6 — 测试入口与框架使用不一致（P2）

- **现状**：`tests/test_posttooluse.py:186-187`、`tests/test_hooks.py:172-173` 为空 `sys.exit(0)`，而 `test_structure.py:185-186`、`test_hosts.py:274-275` 为 `pytest.main([__file__])`。
- **为什么是问题**：直接 `python tests/test_hooks.py` 会静默"通过"（不跑任何测试），误导本地验证。
- **改造方向**：统一为 `pytest.main([__file__])`，或统一改为不提供 `__main__` 入口并文档化 `python -m pytest tests/`。

### B. 插件内容质量

#### B1 — 22 个 SKILL.md 携带规范外字段 `version`（P0，本报告最高优先级）

- **现状**：22 个 `skills/*/SKILL.md` 的 frontmatter **只有** `name` / `description` / `version` 三个字段；`version` 取值为 `0.1.0`（11 个）与 `0.2.0`（11 个），均与插件版本 `0.3.1` 不一致；`tests/test_structure.py:63` 仅断言该字段**存在**，**不校验取值**。
- **为什么是问题**（三重）：
  1. **规范级不符**：Agent Skills 允许字段为 `allowed-tools / compatibility / description / license / metadata / name`，`version` 不在其中；宿主在**打包或上传校验**时可能直接报错 `Unexpected key(s) in SKILL.md frontmatter`（规范原文见 §3.1）。
  2. **纯负债字段**：该字段不参与任何逻辑，却需要人工维护，且事实上已经漂移成两套值。
  3. **不可观测**：无测试约束，漂移不可被 CI 捕获。
- **对标**：§3.1 的规范允许字段清单。
- **改造方向**：**从全部 22 个 SKILL.md 移除 `version` 字段**（技能随插件整体版本发布，无需独立版本）；若确有每技能版本诉求，改用规范允许的 `metadata`（如 `metadata: { version: 0.3.1 }`），并纳入一致性门禁同步。同步更新 `tests/test_structure.py` 中断言 `version` 存在的校验。

#### B2 — code-guide 厚度与结构分布不均（P1）

- **现状**：行数区间 78–310。最薄 5 个：`drogon-gen-lambda-handler`(78)、`drogon-gen-file-upload`(79)、`drogon-gen-db-config`(84)、`drogon-gen-http-client`(85)、`drogon-gen-advice`(95)。**含 0 个 ```cpp 代码块**的有 3 个：`drogon-create-controller`(107)、`drogon-gen-db-config`(84)、`drogon-gen-cmake`(220)（后两者以 ```json / ```cmake 为主，可接受；前者作为最基础技能缺 C++ 模板值得补齐）。结构测试阈值 `>= 40` 行（`tests/test_structure.py:71`）**永不触发**。
- **为什么是问题**：技能是"按需加载的知识"，厚度不均意味着**触发后拿到的知识量不确定**；阈值虚设使"文档过薄"这一类问题不可发现。
- **对标**：仓库 README 宣称"每个 skill 的 code-guide.md 都对照 drogon v1.9.13 源码逐 API 核对"——薄文档难以支撑该承诺。
- **改造方向**：补齐最薄技能的模板与禁止模式；把结构校验从"行数阈值"升级为"章节完整性"（要求模板区块 + 禁止模式章节存在）。

#### B3 — "禁止模式清单"章节命名三套分裂，且 7 个技能声明与内容不符（P1）

- **现状**：
  - 中文专章 `## 5. 禁止模式清单`：5 个（monitoring / stream / rate-limiter / orm-model / websocket）；
  - 英文专章 `## Forbidden patterns|APIs|syntax`：10 个；
  - **无专章**：7 个（create-controller / cmake / db-config / orm-crud / plugin / redis-config / setup-config，其中 cmake 用 `## 构建纪律（禁止项）`，其余以"**禁止**"内联）。
  - 同时，**22 个 SKILL.md 的"参考文件"行全部宣称** code-guide 含"禁止模式清单"（如 `skills/drogon-create-controller/SKILL.md:38`），但其中 7 个实际**没有**该章节。
- **为什么是问题**：模型按 SKILL.md 的索引去 code-guide 找"禁止模式清单"时会**落空**，触发后的行为不可预期；人工维护时也无法靠固定章节名定位。
- **改造方向**：统一章节标题（建议保留一种，如 `## 禁止模式清单`），为 7 个无专章的技能补齐该章节；并把"SKILL.md 声明 ↔ code-guide 章节"纳入一致性门禁。

#### B4 — description 风格分裂，无长度/风格约束（P2）

- **现状**：5 个技能用"需要…时"触发式（monitoring / orm-model / rate-limiter / stream / websocket），17 个用"生成…"能力式；全部为中文，长度 39–94 字符（未超限但也无约束）。
- **为什么是问题**：`description` 是技能的**唯一触发依据**（规范称"仅 description 为推荐项"），风格不统一会导致触发敏感度不一致。
- **改造方向**：统一为"场景/触发词 + 能力"的写法，并在结构校验中加长度范围与关键词约束。

#### B5 — 钩子规则库为裸元组，8 条规则误报无守护（P1）

- **现状**：`hooks/posttooluse.py` 的规则为 `(regex, message[, flags])` 裸元组，共 21 条。逐条映射测试后：**21/21 有正例**（漏报有守护），但 **8 条无反例**：C1 `FILTER_ADD`、C2 `ADD_MIDDLEWARE`、C3 `METHOD_LIST_ADD`、C4/T3 `createDbClient`、C9 `register*Advice`、S2 `<%raw%>`、S4 `@@key@@`；C5（`AsyncTask` + `co_await`）仅有间接反例。
- **为什么是问题**：反例缺失意味着**误报（false positive）无守护**——钩子在 Agent 编辑后弹出警告，误报会直接消耗用户信任；且规则无稳定 ID，报告与测试无法精确引用某一条。
- **对标**：仓库自己在 v0.2.0 修过的正是误报类缺陷（`isDone()` / `task.done` 误报 `done()`），说明这类回归是真实发生过的。
- **改造方向**：规则升级为带**稳定 `rule_id`（如 `CPP.001`）、`severity`、`guide`（修复指向的 skill）** 的结构化条目；为每条规则补至少 1 正例 + 1 反例；`--scan` 输出**纯增量**（新增 `rule_id`），保持 `findings` / `total` 契约不变。

#### B6 — 注释与实现不符：CSP 规则的 IGNORECASE 声明（P2）

- **现状**：`hooks/posttooluse.py:75` 注释称 "CSP ... genuinely case-insensitive patterns keep IGNORECASE"，但 `CSP_VIOLATIONS`（`:76-91`）6 条规则**全部**为 2 元组，`flags` 默认 0，**无一条启用 IGNORECASE**。
- **为什么是问题**：注释误导后续维护者；且 `<%RAW%>` / `<%Raw%>` 这类大小写变体会漏检。
- **改造方向**：二选一——按注释意图为 CSP 规则加上 `re.IGNORECASE`（并补大小写变体正例），或修正注释为事实。

#### B7 — 无技能触发质量评估机制（P2）

- **现状**：现有测试全部是**结构性**的（文件存在、frontmatter 存在、路由表含技能名），没有任何机制评估"技能是否会被正确触发"。
- **为什么是问题**：`tests/test_structure.py:74-77` 只校验 `CLAUDE.md` 文本**包含**技能名，字符串出现不等于路由可理解；`description` 质量、路由表描述是否具备区分度均无人管。
- **对标**：`docs/INTEGRATION-REVIEW-v0.3.0.md:117` 已定义"行为性（手动）验收"两级口径，但该清单从未执行与记录。
- **改造方向**：短期以结构性近似替代（description 关键词与路由表描述的一致性/区分度启发式校验）；长期可建人工抽查清单（沿用既有两级验收框架）。**本轮不做行为性评估**（成本高、依赖宿主）。

### C. 分发与生态

#### C1 — PyPI ↔ npm CLI 能力不对等，且无测试锁定（P0/P1）

- **现状**：

  | 能力 | `src/drogon_plugin/cli.py` | `npm/bin/cli.js` |
  |------|---------------------------|------------------|
  | 命令集合 | install / verify / upgrade / uninstall / **scan** / **hosts** / version | install / verify / upgrade / uninstall / version |
  | `--host` 多宿主 | ✅（`:757,775`） | ❌ |
  | `--force-agents` / `--format` / `--strict` | ✅ | ❌ |
  | `HOSTS` 注册表（10 宿主） | ✅（`:79-98`） | ❌ |
  | 指令文件三态保护 | ✅（`:246-276`） | ❌ |
  | upgrade 语义 | 幂等重装 | 先比版本，同版本直接返回（`:291-296`） |

  `CHANGELOG.md:50` 已如实声明该差异为"已知限制"，但**没有任何测试保证该差异不被进一步扩大**（例如 npm 侧未来悄悄新增一个语义不同的 `--host`）。
- **为什么是问题**：同一命令在不同包管理器下行为不同，用户难以预期；差异仅靠 CHANGELOG 散文维护，属"文档承诺"而非"机器事实"。
- **对标**：仓库"双实现一致性"应有契约（`docs/INTEGRATION-PLAN-v0.3.0.md` Phase B5 曾列出"双实现一致性测试"，实际未落地）。
- **改造方向**：建立**能力矩阵事实源**（命令集合、是否支持 `--host` 等），由两侧实现与其测试共同读取；差异（缺 scan/hosts）显式声明为"计划内缺失"，并有测试锁定"差异集合 == 声明集合"。

#### C2 — verify 语义各有盲区（P1）

- **现状**：两侧 `verify` 校验项不对等且**各有盲区**——
  - py 独有：逐宿主落点状态（`cli.py:462-482,516`）、`.zcode-plugin` 校验（`:513-514`）；
  - js 独有：逐个技能 `SKILL.md` 存在性（`cli.js:231-234`）、`hooks.json` JSON 合法性 + 事件数（`:244-253`）、`CLAUDE.md` 存在（`:256`）；
  - py **不校验** `hooks.json` 合法性、不校验 `CLAUDE.md` 存在；js **不校验** `.zcode-plugin`。
- **为什么是问题**：用户用不同包管理器安装后，`verify` 给出的"通过"含义不同，可能掩盖真实损坏。
- **改造方向**：定义统一的 verify 校验集合（取并集），两侧按同一清单实现；用能力矩阵表达"可选校验项"。

#### C3 — 无安装完整性 / 资产漂移检测（P1）

- **现状**：`verify` 只做**存在性**与**计数**校验（如 `cli.py:507-509`），不校验内容是否与随包版本一致。安装戳（`_STAMP_V2` / `_STAMP_V3`）记录 `files` 计数但不含哈希。
- **为什么是问题**：用户手工改过 `.drogon-plugin/` 内文件、或残留上一版本文件时，`verify` 仍报通过；`upgrade` 的前后差异也无从审计。
- **改造方向**：安装时记录受管文件的摘要（如 SHA-256），`verify` 报告"被修改/过期/缺失"三类漂移；无哈希时优雅降级为仅存在性检查（保持向后兼容）。

#### C4 — 发布链已较强，但生成器覆盖面可再扩展（P2）

- **现状（优点）**：`VERSION` 单一来源、`gen-host-artifacts.py` 同步 5 个产物 + 7 处版本号、`--check` 供 CI 与发布双重把关（`ci.yml:40`、`publish.yml:37`）、发布断言 `tag == VERSION`（`publish.yml:26-34`）。**未覆盖**：技能列表与计数、能力矩阵、README 计数、包元数据（`npm/package.json` 的 `files`/`keywords` 与 `pyproject.toml` 的对应项）。
- **为什么是问题**：B1 的 `version` 漂移正是"生成器覆盖不到"的直接后果；扩展覆盖面可防止同类问题再生。
- **改造方向**：把"技能清单 + 能力矩阵"纳入生成器/门禁的校验范围。

#### C5 — 缺少各宿主应用目录的收录材料（P2）

- **现状**：分发依赖 git 仓库与 npm/PyPI；`.codex-plugin/plugin.json` 有 `interface` 块，`.claude-plugin/marketplace.json` 有目录字段，但没有面向"官方插件目录收录"的说明文档。
- **为什么是问题**：仓库已有完整元数据，却缺少"如何提交到各宿主目录"的操作记录，后续难以复用。
- **改造方向**：在报告中记录现状即可；**本轮不做目录提交**（依赖外部流程）。

#### C6 — npm `prepack` 依赖仓库相对路径（P2）

- **现状**：`npm/package.json:16` `"prepack": "node ../scripts/sync-assets.mjs"` —— 发布 npm 包时依赖**仓库上层目录结构**。
- **为什么是问题**：若在 `npm/` 目录单独发布（或目录结构变化），`prepack` 会失败；该耦合无测试锁定。
- **改造方向**：改为包内自包含的同步脚本，或在 CI 中显式断言发布路径（`ci.yml:104-119` 已有 npm pack 冒烟，可扩展断言）。

### D. 治理与文档（仅必需项）

#### D1 — 缺技能作者手册（P0，必需）

- **现状**：新增技能的流程散落在 `CONTRIBUTING.md:20-26`（6 行），内容为"创建 SKILL.md → 补 code-guide → 登记 CLAUDE.md 路由表 → 登记 README → 若涉及检测则扩充 hook"。但实际约束远超这 5 步：技能数需同步 **7 处常量**（A1）、需同步**双语 README + npm 双语 README**、需注意 **frontmatter 允许字段**（B1）、需保证 **code-guide 章节结构统一**（B3）、需补**钩子正反例**（B5）。
- **为什么是问题**：手册缺失是 A1/B1/B3 这类"新增技能时漏同步"问题的**根因**；有手册才能把流程从"口口相传"变成"可执行清单"。
- **改造方向**：新增 `docs/SKILL-AUTHORING.md`，含元数据规范、触发词写法、知识文档分层要求、四处双向同步清单、新增/修改技能的可执行步骤、测试与门禁要求。

#### D2 — CONTRIBUTING 的版本同步清单已过期（P1，必需）

- **现状**：`CONTRIBUTING.md:18` 写"插件版本在 `.claude-plugin/plugin.json`、PyPI `src/drogon_plugin/__init__.py`、npm `npm/package.json` **三处**同步更新"；`CONTRIBUTING.md:34` 写"tag 前先更新 CHANGELOG.md 与**三处**版本号"。实际由 `gen-host-artifacts.py` 统一维护 **7 处**（`.claude-plugin/plugin.json`、`.zcode-plugin/plugin.json`、`.claude-plugin/marketplace.json`、`pyproject.toml`、`npm/package.json`、`__init__.py` 的 `__version__` 与 `PLUGIN_VERSION`），加上 `VERSION` 为唯一来源（`gen-host-artifacts.py:145-154`）。
- **为什么是问题**：贡献者按过期清单手工改版本，会漏改 `VERSION` 或生成物，触发 CI/发布失败。
- **改造方向**：改写为"改 `VERSION` → 跑 `python scripts/gen-host-artifacts.py` → 跑 `--check`"，并指向 CHANGELOG 既有流程说明。

#### D3 — 双语 README 无互校（P1，必需）

- **现状**：`README.md` 与 `README.zh-CN.md` 结构对应（各自 22 行技能表，`README.md:105-128` / `README.zh-CN.md:105-128`），但无任何测试比较二者；`npm/README.md` 与 `npm/README.zh-CN.md` 同理。
- **为什么是问题**：双语 README 是主要门面，缺失互校会导致一侧更新、一侧停留在旧内容（当前 `22` 在两份文件中各出现 5 次，均需人工同步）。
- **改造方向**：门禁校验两份文件的**结构等价性**（标题层级序列一致、技能表行数与技能名集合一致、代码块数量一致），而非逐字比对。

#### D — 明确不做（评估后放弃，附理由）

| 项 | 理由 |
|----|------|
| 文档站（mkdocs 等） | 内容量（4 份 README + 1 份规则文件 + 22 技能）尚未到需要站点的规模；引入站点会新增构建链与部署面，与本轮"不引入工具链"冲突 |
| 路线图 / ROADMAP | `CHANGELOG.md` 的 Unreleased + 既有两份 PLAN 文档已承载规划语义；新增独立路线图会形成第二个事实源 |
| `CODEOWNERS` | 单维护者仓库，`CODEOWNERS` 无语义收益 |
| 更多 CI 平台（GitLab 等） | 无实际受众，纯维护负担 |

---

## 6. 加权优先级与改造计划

加权口径：**收益 = 规范/安全影响 × 可自动化程度 × 影响面**；**成本 = 改动文件数 × 回归风险**。

| 优先级 | ID | 改造项 | 收益 | 成本 | 依赖 |
|--------|----|--------|------|------|------|
| **P0** | B1 | 移除 22 个 SKILL.md 的规范外 `version` 字段 | 高（规范符合 + 根除漂移） | 低（22 个文件同一处删除） | — |
| **P0** | A1 | 技能数量改为实枚举派生，消除 7 处常量 + 34 处文案硬编码 | 高 | 中 | 能力矩阵事实源 |
| **P0** | A2 | 清理 8 处死代码/占位/虚设断言 | 中 | 低 | — |
| **P0** | A5 | 新增跨产物一致性门禁（含 D3/A3/B3/C1 的校验点） | 高 | 中 | A1 |
| **P0** | A4 | CI pin 依赖与 action SHA + 开启缓存 | 中高（供应链） | 低 | — |
| **P0** | D1 | 新增 `docs/SKILL-AUTHORING.md` | 高（根因治理） | 低 | — |
| **P1** | B5 | 钩子规则结构化（`rule_id`/`severity`/`guide`）+ 补 8 条反例 | 高 | 中 | — |
| **P1** | C1 | 能力矩阵事实源 + PyPI/npm 差异测试锁定 | 高 | 中 | A1 |
| **P1** | C2 | verify 校验集合统一（取并集） | 中 | 中 | C1 |
| **P1** | C3 | verify 增加资产漂移检测（哈希，向后兼容） | 中 | 中 | C1 |
| **P1** | B2/B3 | 补齐薄文档 + 统一"禁止模式清单"章节 | 中高 | 中（7–12 个文件） | — |
| **P1** | A3 | 双同步器常量事实源 + 严格性对齐 | 中 | 低 | A5 |
| **P1** | D2/D3 | CONTRIBUTING 版本清单改写 + 双语 README 互校 | 中 | 低 | A5 |
| **P2** | B4 | description 风格统一 + 长度约束 | 中 | 中（22 个文件） | B1 |
| **P2** | B6 | CSP 规则 IGNORECASE 与注释对齐 | 低 | 低 | B5 |
| **P2** | A6 | 测试入口统一 | 低 | 低 | — |
| **P2** | C4/C6 | 生成器覆盖面扩展 / npm prepack 解耦 | 中 | 中 | A1 |
| **P2** | B7 | 技能触发质量评估（结构性近似） | 中 | 高 | B4 |

---

## 7. 验收口径

### 7.1 可自动化（进 CI，硬性）

| 验收项 | 判定方式 |
|--------|----------|
| 技能数量唯一来源 | 全仓库 `grep -n '\b22\b'` 在技能数量语义上**零命中**（除 `CHANGELOG.md` 等历史记录）；断言由实枚举派生 |
| SKILL.md 元数据规范 | 校验字段集合 ⊆ `{allowed-tools, compatibility, description, license, metadata, name}`；`name == 目录名`；`description` 长度在约定区间 |
| 技能 `version` 漂移 | 字段已移除（或已迁入 `metadata` 并纳入同步）；校验取值一致 |
| code-guide 章节完整性 | 每个 code-guide 含约定章节（模板区块 + 禁止模式清单）；行数下限与当前水位匹配（≥ 70 行） |
| SKILL.md ↔ code-guide 声明一致 | SKILL.md 声明的章节名在 code-guide 中真实存在 |
| 钩子规则守护 | 每条规则至少 1 正例 + 1 反例；规则 ID 唯一且稳定 |
| `--scan` 契约 | `{findings:[{file,violations[]}], total}` 字段保留；新增字段为纯增量 |
| CLI 能力矩阵 | 两侧实现的命令/参数集合与能力矩阵声明**完全相等** |
| 双同步器等价 | 两侧 `ASSETS`/`FILES`/`IGNORE_DIRS` 取值与严格性一致 |
| 双语 README 结构等价 | 标题序列、技能表行数与技能名集合、代码块数量一致 |
| 版本一致性 | `VERSION` == 7 处清单版本（既有断言保持） |
| 死代码 | 无未引用常量、无占位变量、无永不触发的阈值断言 |

### 7.2 人工（一次性，记录结果）

| 验收项 | 方式 |
|--------|------|
| 各宿主真安装 | 沿用 `docs/INTEGRATION-PLAN-v0.3.0.md` Phase C 清单：Codex `plugin marketplace add` + trust、Cursor/VS Code 打开项目、Gemini `extensions install`，确认技能列表与规则注入生效 |
| SKILL.md 字段移除的宿主兼容性 | 在 Claude Code 与 Codex 各打包/安装一次，确认**不再**出现 `Unexpected key(s) in SKILL.md frontmatter`，且技能可正常触发 |
| 上下文增量 | 记录各宿主技能列表进入上下文的 token 增量（沿用评审 #10 口径） |

---

## 8. 工具链选型建议（仅建议，本轮不引入）

以下建议**均不在本轮落地**（按需求只做诊断）。判断依据：仓库承诺"零运行时依赖"，下列工具全部为 **dev-only**，不进入 wheel / npm 包，因此不破坏该承诺。

| 建议引入 | 替代/解决的问题 | 理由 | 优先级 |
|----------|-----------------|------|--------|
| **ruff** | 现无 lint/format（仅 `py_compile`） | 单工具同时覆盖 lint + format，替代 flake8/black/isort，配置面小、执行快；对 `src/`、`scripts/`、`hooks/`、`tests/` 统一风格 | 高 |
| **pytest-cov + 覆盖率门槛** | 现零覆盖率度量 | 仓库核心逻辑（`cli.py` 的所有权校验/边界护栏、`posttooluse.py` 的规则匹配）属高风险区，覆盖率能防止"改了没测"；建议先设低门槛（如 70%）再逐步提升 | 高 |
| **mypy（或 pyright）** | 现零类型检查 | `cli.py` 大量使用 `Optional`/`dict` 结构，`_PKG_VERSION: "str | None"` 等已带类型标注，启用成本低；可先只覆盖 `src/` 与 `scripts/` | 中 |
| **eslint + prettier** | npm CLI 零静态检查 | `npm/bin/cli.js` 415 行、`sync-assets.mjs` 111 行，规模已到需要一致性风格的程度 | 中 |
| **pre-commit** | 现无本地门禁 | 把 ruff / 一致性门禁脚本挂在 commit 前，避免"CI 才发现"；可用 `repo: local` 调用仓库自身脚本，零外部依赖 | 中 |
| **dependabot**（或 renovate） | 依赖与 action 浮动 | 与 A4 的 SHA pin 策略配套：pin 住之后需要自动化来跟进更新，否则会被"忘记升级" | 中 |
| **actionlint + zizmor** | workflow 静态检查 | 仓库已发生过 `publish.yml` YAML 解析错误导致发布从未执行（`CHANGELOG.md:15`），此类检查可直接预防复发；zizmor 还能检查 workflow 安全反模式 | 中 |
| **CodeQL** | 现无安全扫描 | GitHub 原生集成、对 Python/JS 免费；可覆盖两个 CLI 的注入/路径穿越类问题 | 中 |
| **OpenSSF Scorecard** | 供应链评分 | 仓库已是公开开源项目，Scorecard 的 Pinned-Dependencies / Token-Permissions 检查项与 A4 直接对应，可作为外部体检看板 | 低 |
| **mkdocs-material** | 文档站 | 当前内容规模尚不需要（见 D 维度"明确不做"）；若技能数突破 40 或新增教程类内容再评估 | 低（暂不） |

**不推荐的项**：`flake8`/`black`/`isort` 组合（被 ruff 覆盖，徒增配置）；`tox`/`nox`（CI 矩阵已覆盖多平台，无需本地矩阵编排器）。

---

## 9. 附录：本次调研的取证方法

1. **全量源码通读**：`README(zh).md`、`CLAUDE.md`、`pyproject.toml`、`CHANGELOG.md`、`CONTRIBUTING.md`、`MANIFEST.in`、`.gitignore`、`.gitattributes`、全部 CI/发布 workflow、全部宿主清单、`src/drogon_plugin/cli.py`、`npm/bin/cli.js`、`hooks/`（5 个文件）、`scripts/`（5 个脚本）、`tests/`（4 个测试 + fixtures）、`docs/`（3 份历史文档）、`PRD/`（2 份）。
2. **量化统计**：`grep` 计次（硬编码 `22`、`version:`、规则元组）、PowerShell 行数统计（code-guide 行数分布、description 长度分布）、`skills/` 非 Markdown 文件计数。
3. **规范实读**：Agent Skills / Claude Code 官方文档（skills、plugins、hooks、plugins-reference），核对 frontmatter 允许字段、插件目录布局、hooks 格式。
4. **安全静态扫描**：提示注入、编码混淆、零宽字符、凭据、破坏性命令、子进程/网络六类模式全仓库检索。
5. **规则↔测试映射**：逐条把 21 条钩子规则映射到 `tests/test_posttooluse.py` 的 `*_MATCH` / `*_NO_MATCH` fixture，得出"无反例规则"清单。

> 本报告为**诊断结论**。第 6–7 节的改造项与验收口径可直接作为落地实施的依据。

---

## 10. 本轮落地情况（改造后回填）

### 10.1 按差距项对照

| ID | 状态 | 落地内容 / 证据 |
|----|------|------------------|
| A1 | ✅ 完成 | 技能数一律由 `skills/` 实枚举：`cli.py::_bundled_skill_count`、`cli.js::bundledSkillCount`、生成器 `skill_count()`、两个冒烟脚本、两个测试；CI 断言改为下限哨兵。README 中的数字由门禁校验（写错会指出文件与原文）。**代码/脚本层面已无任何技能数字面量** |
| A2 | ✅ 完成 | 8 处全部处理：`_EXPECTED_HOOK_EVENTS` 改为真实校验用途（不再是死常量）、`test_hosts.py` 占位变量与重复调用删除、两个测试文件补 `pytest.main` 入口、code-guide 阈值 40→70 并配章节契约、`test_posttooluse.py` docstring 现由规则级契约兑现、`sync-assets.mjs` 冗余分支删除 |
| A3 | ✅ 完成 | `check-consistency.py` 断言两份同步器的 `ASSETS`/`FILES`/`IGNORE_DIRS` 等价；`sync-assets.py::check()` 补齐"目标侧混入 `__pycache__`"检测，严格性与 `.mjs` 对齐 |
| A4 | ⚠️ 部分 | 已完成：`requirements-dev.txt` 固定依赖版本、CI/publish 均改用 `-r requirements-dev.txt`、`setup-python` 开启 `cache: pip`。**未完成**：action 的 SHA 固定（需要真实 commit SHA，不宜凭空填写；建议由依赖机器人接管，见 §8） |
| A5 | ✅ 完成 | 新增 `scripts/check-consistency.py`（7 项检查）：README 计数与事实源一致、双语 README 技能覆盖、双语 README 表格对齐（含"主 README 须有完整技能表"防假绿）、双同步器常量等价、CLI 能力契约、无硬编码技能数（含**正向**要求实枚举入口）、钩子规则 ID 唯一且非空。CI 与 pytest 共用同一实现 |
| A6 | ✅ 完成 | 两个测试文件的空 `sys.exit(0)` 改为 `pytest.main([__file__])` |
| B1 | ✅ 完成 | 22 个 `SKILL.md` 的 `version` 全部移除、改加 `license: MIT`；`description` 统一触发式；白名单字段由 `test_structure.py` 强制 |
| B2 | ⚠️ 部分 | 已建立**结构契约**（行数下限 70 + 必须有「禁止模式清单」+ 必须有模板块）并为 6 个技能补写了该章节；**未做**逐篇增厚到与最厚技能（310 行）可比的统一水平——属内容演进，契约已就位 |
| B3 | ✅ 完成 | 16 处标题重命名 + 6 处新增，22/22 统一为 `## 禁止模式清单`；`SKILL.md` 的声明与 `code-guide` 实际章节由测试校验一致 |
| B4 | ✅ 完成 | 22 条 `description` 统一为「需要……时，…」，并由测试强制句式与长度上界 |
| B5 | ✅ 完成 | 规则升级为 `Rule(rule_id, severity, pattern, message, guide, flags)`；21 条规则**全部**具备 1 正例 + 1 反例（此前 8 条无反例）；`rule_id` 唯一性纳入门禁 |
| B6 | ✅ 完成 | CSP 规则真正启用 `re.IGNORECASE`（此前注释声称启用、代码未启用），并补大小写变体反例 |
| B7 | ❌ 未做 | 行为性触发评估成本高且依赖宿主，按需求保留为建议；本轮以 `description` 句式契约作为结构性近似 |
| C1 | ✅ 完成 | `scripts/plugin-capabilities.json` 为能力契约事实源；pytest 断言两侧实现的命令集合与声明完全相等，且"npm 缺口 == 已登记缺口"；npm 侧 `COMMANDS` 为单一来源并支持 `--capabilities` |
| C2 | ✅ 完成 | PyPI `verify` 补上 `CLAUDE.md` 存在性与 `hooks/hooks.json` 事件数校验（此前仅 npm 侧有）；两侧校验集合现为并集 |
| C3 | ✅ 完成 | 安装时记录受管文件 SHA-256 清单，`verify` 报告被改动/缺失/多余；旧版安装无清单时优雅跳过；两侧 CLI 均有测试覆盖 |
| C4 | ✅ 部分 | 技能数已由生成器派生；`version` 字段移除后不再有"生成器覆盖不到的技能级版本"。包元数据一致性（`npm/package.json` ↔ `pyproject.toml`）未纳入门禁 |
| C5 | ❌ 未做 | 各宿主官方目录收录材料（依赖外部流程，本轮不涉及） |
| C6 | ❌ 未做 | npm `prepack` 仍依赖仓库相对路径；CI 的 `npm pack` 冒烟已覆盖该路径 |
| D1 | ✅ 完成 | 新增 `docs/SKILL-AUTHORING.md`（字段白名单、触发词写法、结构契约、四处同步清单、钩子流程、`--scan` 契约、发布流程） |
| D2 | ✅ 完成 | `CONTRIBUTING.md` 重写：修正"三处版本号"为 `VERSION` + 生成器维护 7 处，补手册入口与本地验证命令 |
| D3 | ⚠️ 部分 | 双语 README 的**技能表格**行数与覆盖已对齐并纳入门禁；**未做**逐字/全章节对齐（成本高、收益低） |

### 10.2 对抗性复核发现并修复的真实缺陷

| 缺陷 | 性质 | 处理 |
|------|------|------|
| `npm/bin/cli.js` 的 `install` 日志行仍引用已删除的 `EXPECTED_SKILLS` | **会阻断 CI**（`ReferenceError` → `install` 失败），且当时的门禁只查"是否有字面量 22"，反而**放过**了"删了常量但漏改引用点" | 已改为 `bundledSkillCount()`；门禁新增**正向断言**（CLI 必须存在实枚举入口），并补 npm CLI 端到端测试 `test_npm_cli_install_verify_uninstall` |
| `_check_hook_rules_have_ids` 在规则库为空时静默通过 | 门禁假绿：规则库被清空会"没有重复 ID"而通过 | 已补空集断言（规则库为空即失败） |
| 双语 README 对齐检查使用"含 `drogon-` 的表格行" | 宿主安装表格含 `drogon-claude-plugin`，会误计 | 改为精确匹配"首列为反引号技能名"的表格行，并新增"主 README 技能表行数 ≥ 技能数"断言 |
| `cmd_scan` 动态加载随包扫描器时写入 `__pycache__` | 把中间产物留进 `drogon_plugin_assets/hooks/`，导致 `verify` 报"未受管文件"、`sync-assets --check` 报不一致；且该污染**运行测试后必然发生** | 在两处动态导入前设 `sys.dont_write_bytecode = True` 从源头消除（由本轮新增的严格性检查发现） |

### 10.3 明确未做（附理由）

| 项 | 理由 |
|----|------|
| action 的 commit SHA 固定 | 需要真实的 40 位 SHA；凭空填写会直接让 CI 红。正确做法是引入依赖机器人自动提 PR（§8 已建议），本轮不引入新工具链 |
| ruff / pytest-cov / mypy / eslint / pre-commit / CodeQL / Scorecard / mkdocs | 按需求"本轮只做诊断、不改工具链"，仅在第 8 节给选型建议 |
| B7 技能触发行为性评估 | 依赖真实宿主会话，成本高；已有 `docs/INTEGRATION-PLAN-v0.3.0.md` Phase C 的人工清单可复用 |
| 22 篇 code-guide 的全面增厚 | 已建立结构契约并补齐缺失章节；逐篇增厚属内容演进，不应在结构改造中一次做完 |
| 逐字双语 README 对齐 | 结构（技能表/计数）已对齐；逐字对齐会带来大量无信息量的改动 |

### 10.4 验收结果（本轮实测）

```
python scripts/gen-host-artifacts.py --check   → ✅ 宿主产物与事实源一致(版本 0.3.1)
python scripts/sync-assets.py --check          → ✅ 插件资产与源码同步
node scripts/sync-assets.mjs --check           → ✅ npm 资产与源码同步
python scripts/check-consistency.py            → ✅ 跨产物一致性检查通过(12 项)
python -m pytest tests/ -q                     → 127 passed
```

测试数：47 → **127**（第一轮 +56：规则级正反例 42、能力契约 3、漂移检测 3、npm CLI 端到端 2、门禁与规范契约 6；第二轮 +24，见下）。

### 10.5 第二轮评审与整改（规范符合性 / 功能正确性 / 多宿主兼容性）

第二轮评审记录见 [`docs/SPEC-CORRECTNESS-COMPAT-REVIEW.md`](SPEC-CORRECTNESS-COMPAT-REVIEW.md)。要点：

- **规范性结论**：SKILL.md 移除 `version` 后**更合规**（该键不在 Agent Skills 六字段白名单，也不在 Claude Code 技能字段表中，规范对未知键是硬失败）——本轮无相关修复。
- **修复 11 项确证缺陷**：按宿主卸载失效（bundle 空操作）、按宿主卸载误删共享 `AGENTS.md`、共享技能目录无保护（`copilot`/`agents`）、`file_category` 子串误判、标记段半损坏、`rmtree` 未判目录、SessionStart 漏 `resume`、`session-start` 控制字符转义不全、`--scan --format` 缺值崩溃、npm 回退整仓复制、**无扩展名钩子脚本未固定 LF**（Windows 克隆会得 CRLF → bash 静默失效）。
- **门禁 7 → 12 项**；回归测试净增 24 例。
- **明确不盲改**：3 条来自评审的推测被官方文档反证（Codex `interface` 必填字段、`hooks` 字段被 validator 拒绝、SKILL.md 缺章节），5 项列入**真机核实清单**（`shell` 字段容忍度、`MultiEdit` matcher、Codex `interface`、Trae `.mdc`、Cursor 空 `globs:`）。
- **对抗性复核的结论取舍**：复核提出的"CRLF 导致孤立标记清理失效"经**实证为误报**（`Path.write_text` 在 Windows 写出 CRLF，但 `Path.read_text` 默认启用 universal newlines，读回为 LF）；复核另发现的"共享技能目录无引用计数"与"marker 路径残留安装戳"确证成立并已修复。
