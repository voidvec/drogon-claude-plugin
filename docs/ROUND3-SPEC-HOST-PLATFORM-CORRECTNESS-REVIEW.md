# 第三轮评审：规范性 / 宿主兼容性 / 平台兼容性 / 功能正确性（四维深审）

> 日期：2026-09-23。对象：`drogon-claude-plugin` v0.3.1 工作区（`0930a44` 专业化整改之后）。
> 方法：四个独立评审代理分维度全量读码 + 2026-09 官方文档/官方源码实读核实；所有"高置信度"结论均由主评审逐条实证复现或对撞官方源后才登记。
> 定级：**高** = 已复现或有官方源直接依据；**中** = 逻辑成立但条件触发/未复现；**待真机** = 静态与文档均无法定论。
> 基线确认：第二轮 §7 的 11 项整改（C1–C5 / M1–M4 / H1–H6）**全部已落地且各有回归测试/门禁**，本机 `pytest tests/ -q` 127 passed。本轮是在"已整改基线"上找残余与新增缺陷。

---

## 0. 执行摘要

| 维度 | 结论 | 本轮新增高置信度 |
|------|------|------------------|
| 插件规范性 | 无硬违规；1 处低危字段形态不符 + matcher 枚举过时 | R1（marketplace `source`）、R2（漏 `fork`） |
| 宿主兼容性 | **Codex 上 PostToolUse 扫描必然空转**（结构性失效）；Trae 规则落点与官方文档不符 | R3（apply_patch 空转）、R10（Trae `.mdc`） |
| 平台兼容性 | Windows stdin 编码崩溃可复现；npm 分发丢可执行位 | P1（stdin 编码）、P2（npm 无 chmod） |
| 功能正确性 | `upgrade` 重置宿主范围并强注用户文件；钩子畸形输入崩溃；CFG 规则对 YAML 整体漏报；2 处技能模板 API 错误 | R1、R4、R5、R6、R7 |

最高优先修复组合：**R3**（一个改动同时消掉 R2/R3/N2 类白名单漂移）> **R4**（upgrade 破坏安装契约）> **P1**（Windows 崩溃）。

---

## 1. 插件规范性（Axis A）

### R1 — `.claude-plugin/marketplace.json:10` `"source": "."` 不符官方形态【高】
- 官方依据（已二次核实原文）："Local plugin sources must start with `./`"，示例 `"source": "./plugins/my-plugin"`；必填 `name`+`source`。
- 修复：改为 `"./"`。同步链：`npm/assets/.claude-plugin/marketplace.json`、`src/drogon_plugin/drogon_plugin_assets/.claude-plugin/marketplace.json`（由 sync-assets 生成，改源即可）。建议进 `check-consistency.py` 门禁。

### R2 — SessionStart matcher 漏 `fork`【高（覆盖面）/修复成本极低】
- 官方依据：Claude Code hooks 文档当前 source 枚举为 `startup / resume / clear / compact / fork`；Codex 的 `session-start.command.input.schema.json` 同样含 `fork`。fork（会话分叉）是 Codex 0.148+ 主推场景。
- 现状：`hooks/hooks.json:6` = `startup|resume|compact|resume` 四值，无 `fork`；`tests/test_hooks.py:173` 只断言 `"resume" in matcher`（子串断言，`"noresume"` 也能过——断言方向本身弱）。
- 修复建议：matcher 改 `"*"`（规则注入对所有启动来源都应为真），并同步加强测试为集合相等断言。

### 规范符合度确认（勿再投入）
| 项 | 裁定 | 依据 |
|----|------|------|
| `hooks[].shell: "bash"` | ✅ 合法字段 | Claude hooks 文档字段表 "Accepts 'bash' or 'powershell'"；V1 结案（§5） |
| SKILL.md frontmatter `{name, description, license}` | ✅ 全宿主可接受 | agentskills.io；**修正第二轮 §0**："未知字段硬失败"表述过强，Claude 现文档为 unknown fields ignored |
| SKILL.md 规模 / `references/` 组织 | ✅ 22 个均 39–42 行，<500 行上限 | agentskills.io 渐进披露 |
| `gemini-extension.json` | ✅ `name`/`version` 必填，`contextFileName` 为现行字段 | gemini-cli writing-extensions |
| `.codex-plugin/plugin.json` | ✅ 结构合规；`interface` 无必填项 | 见 V3（§5） |
| 版本 10 处落点 | ✅ 一致且有断言 | 第二轮结论未回归 |

### 低优先观察
- `.zcode-plugin/plugin.json:21-22`：`skills: "./skills"`（无尾斜杠）与 `hooks: "hooks/hooks.json"`（无 `./` 前缀）形态不一——ZCode 无公开规范，不可外部验证，仅登记。
- PostToolUse matcher 含 `MultiEdit`：Claude 当前文档工具列表示例仅 `Write|Edit`（N3，归入宿主轴）。
- `hooks.json` 可加顶层 `$schema` 提升编辑器校验（可选）。

---

## 2. 宿主兼容性（Axis B）

### 宿主 × 能力矩阵（本轮再核实）
| 宿主 | 技能发现 | hooks | 指令文件 | 判定 |
|------|---------|-------|---------|------|
| Claude Code | ✅ 插件 bundle | ✅（matcher 漏 fork = R2） | CLAUDE.md；≥2.1.277 无 CLAUDE.md 时读 AGENTS.md | 基本可用 |
| Codex | ✅ `.agents/skills` 原生 + 插件 skills | ⚠️ 会触发但**扫描空转**（R3） | AGENTS.md ✅ | 结构缺陷 |
| Gemini CLI | ✅ `.gemini/skills`+`.agents/skills` | ✅ 扩展可带 hooks | GEMINI.md ✅ | 可用 |
| Cursor | ✅ `.cursor/skills`（frontmatter 必填 name/description） | — | `.mdc` description/globs/alwaysApply 现行有效 | 可用 |
| Trae | 未见本地 hooks 文档 | `.trae/skills` 有映射 | **项目规则为 `.trae/rules/*.md`，文档无 `.mdc`**（R10）；AGENTS.md/CLAUDE.md 兼容 | 规则落点存疑 |
| Qoder | `.qoder/skills`（N4：当前未投放） | CLI 有 hooks 文档 | AGENTS.md + `.qoder/rules/**/*.md` ✅ | 规则可用、技能通道缺 |
| CodeBuddy | `.codebuddy/skills`（N5：未投放） | 有 hooks（未利用） | CODEBUDDY.md ✅ | 同上 |
| Copilot / VS Code / agents | `.agents/skills` ✅ | Copilot agents hooks 已有官方文档（未利用） | AGENTS.md ✅ | 可用 |
| ZCode | 无公开文档 | 无公开文档 | — | 待真机 |

### R3 — Codex 上 PostToolUse 扫描**必然空转**（结构性失效）【高】
- 官方源码证据（openai/codex `codex-rs/core/src/tools/hook_names.rs:28-39`，原文已核对）：文件编辑的 canonical stdin 名是 **`apply_patch`**；`Write`/`Edit` 仅是 **matcher 别名**——"matcher aliases … must not change the payload seen by hook processes"。
- 因此：`hooks.json` 的 matcher `Write|Edit` 能命中 ✅，但 `hooks/posttooluse.py:394` 白名单 `tool_name in ('Write','Edit','MultiEdit')` 永远看不到 `apply_patch` → 直接 `print({})` 退出。且 Codex 的 `tool_input` 是 `{"command": <patch文本>}`，无 `file_path/content/new_string`，即使过了白名单也无内容可扫。
- 影响面：hook 兜底在 8 个宿主中实际只有 Claude-系（Claude Code / ZCode / Qoder-IDE 等用 Write/Edit 工具名的）生效；README/AGENTS.md 宣称的"PostToolUse hook 兜底"对 Codex 用户是**空承诺**。
- 修复方向（同时消掉 R2/N3 漂移）：白名单改**黑名单**——除已知非文件工具外一律尝试提取；对 `tool_name == 'apply_patch'` 增加 patch 文本解析路径（提取 `*** Update File: <path>` 与新增行作为 content）；`npm/assets`、`drogon_plugin_assets` 同步。
- 关联：`session-start` 在 Codex 的 `additionalContext` 超 ~2500 token 会溢出为磁盘预览（中，N7，待真机观察中文规则全文是否降级）。

### R10 — Trae 规则落点 `.trae/rules/drogon-plugin.mdc` 与官方文档不符【高】
- 证据：`src/drogon_plugin/cli.py:102`（HOSTS 表 trae 分支）写 `.mdc`；docs.trae.ai/ide/rules 页面**零处提及 `.mdc`**，规则样例均为 `.trae/rules/*.md`（如 `git-commit-message.md`、`rules.md`），并明示 AGENTS.md/CLAUDE.md 兼容（AGENTS.md 需放项目根）。
- 影响：Trae 宿主大概率不读取该文件；缓解因素——同一安装已把 `AGENTS.md` 以 marker 写入项目根（Trae 官方支持），所以**规则注入实际靠 AGENTS.md 兜住**，`.mdc` 产物是 inert 文件。
- 修复方向：trae 分支改为仅 `instruction AGENTS.md`，删 `.mdc` 投放；或改投 `.md`。V4 由此结案（证伪 .mdc 假设）。

### N3/N4/N5 — 中低优先（登记，下轮或随 R3 批次处理）
- N3：`MultiEdit` 已从 Claude 工具集消失、`NotebookEdit` 未覆盖——matcher 与 `posttooluse.py:394` 双处过时（R3 的黑名单改法一并解决）。
- N4/N5：qoder/codebuddy 宿主只落指令文件，`.qoder/skills`、`.codebuddy/skills` 官方发现通道未利用（安装器增强项，非缺陷）。
- N8：Cursor 的 SKILL.md 支持字段清单不含 `license`，未知字段行为未文档化（大概率忽略；待真机）。

---

## 3. 平台兼容性（Axis C）

### P1 — Windows 钩子模式 stdin 未切 UTF-8，非 ASCII 负载可致崩溃【高，已复现】
- 证据：`hooks/posttooluse.py:353-359` `_utf8_stdio` 只重配 stdout/stderr；`:388` `json.load(sys.stdin)` 用 locale 编码；`UnicodeDecodeError` 不在 `except (json.JSONDecodeError, IOError)` 内。
- 复现（本机实证）：`PYTHONIOENCODING=cp1252:strict python hooks/posttooluse.py < payload`（payload 含 0x81 等 cp1252 未定义字节）→ `UnicodeDecodeError` traceback，exit 1。真实触发：编辑含中文的文件时宿主把 payload 经管道交给 python，locale 为 cp1252/cp936 的 Windows 会话即可能命中（CP1252 系地区风险最高；GBK 下多为乱码误判而非崩溃）。
- 掩盖原因：CI 设 `PYTHONUTF8=1` 且负载全 ASCII；第二轮 §3.3"各入口 `_utf8_stdio` 均正确"对 stdout/stderr 成立、**对 stdin 证伪**。
- 修复：`_utf8_stdio` 纳入 `sys.stdin`，或 except 加 `ValueError`；补回归测试（非 ASCII stdin）。

### P2 — npm 安装丢失可执行位（Linux/macOS）【中高，读码确证】
- 证据：`npm/bin/cli.js:164` `copyAssets` 逐文件 `fs.copyFileSync`（不携带源 mode），全文件无 chmod；npm 分发经 git checkout 保 755，但复制落地后 `hooks/run-hook.cmd` 无可执行位 → 宿主直接执行 command 时 Permission denied → 钩子静默失效。
- 关联：PyPI 侧 `shutil.copy2` 保 stat，但 wheel 条目 mode 取决于构建平台（旧 wheel 实证 0666 无 x）；pip 解包是否补 x 未实证（并入真机清单）。
- 修复：`copyAssets` 后对 `hooks/run-hook.cmd`、`hooks/session-start`、`hooks/post-tool-use`、`hooks/posttooluse.py` 显式 `fs.chmodSync(0o755)`（Windows 上为 no-op）。

### 中低优先
- `hooks/run-hook.cmd:24-38` bash 定位链在「用户级 Git 安装 + 已装 WSL」时经 `where bash` 命中 System32 bash（WSL），打不开 `D:\` 路径——补探 `%LOCALAPPDATA%\Programs\Git\bin\bash.exe`。
- `hooks/post-tool-use:15-16` 刻意 word-split `DROGON_PLUGIN_PYTHON`，带空格路径（`C:\Program Files\...`）断裂。
- CI 矩阵 Python 钉 3.11、Node 仅 20，`requires-python>=3.9` 边界无人守护（L：建议矩阵加 3.9/3.13）。
- 工作区多个 .md/.json 磁盘检出为 CRLF（陈旧 renormalize），新鲜克隆无影响；宜 `git add --renormalize .` 一次。

### 已验证无虞（勿再投入）
H6 换行固定（autocrlf=true 临时克隆实证 4 钩子脚本全 LF；`git ls-files --eol` attr 生效）；`_utf8_stdio` 对全部 Python 入口 stdout/stderr 覆盖；所有 `open()/read_text/write_text` 显式 `encoding='utf-8'`；Node API 与 `engines>=18` 一致；106 个跟踪文件无仅大小写重名；npm `.cmd` 垫片路径解析正确。

---

## 4. 功能正确性（Axis D）

### R4 — `upgrade` 重置为全宿主并强制写用户指令文件【高，已复现】
- 证据：`src/drogon_plugin/cli.py:643-645` `cmd_upgrade` 仅 `args.force_agents=True; return cmd_install(args)`；`:409` 附近 `_parse_hosts(None)` → ALL_HOSTS。
- 复现（临时目录实证）：用户自有 `AGENTS.md` → `install --host claude` → `upgrade` → 输出多出 codex/cursor/gemini/qoder/codebuddy/trae 六宿主产物（`.cursor/`、`.trae/`、`GEMINI.md`、`CODEBUDDY.md`），且用户 `AGENTS.md` 被注入标记段（未经 `--force-agents` 同意），stamp hosts 从 `[claude,zcode]` 变全量 8 宿主。
- 违背 install 的三态保护承诺（存在→跳过）；`tests/` 对 upgrade **零覆盖**（grep 无 "upgrade" 用例）。
- 修复方向：upgrade 读 v3 stamp 复用原 hosts 集合（允许 `--host` 显式扩大）；force 语义不默认放大；补 upgrade 回归测试。

### R5 — 钩子对畸形 stdin 无兜底，traceback 逃逸【高，已复现】
- 复现：`echo '{"tool_name":"Edit","tool_input":"oops"}' | python hooks/posttooluse.py` → `AttributeError: 'str' object has no attribute 'get'`（`posttooluse.py:400`），rc=1。与"never blocks、优雅降级"自述相悖；宿主侧 PostToolUse 报错。
- 修复：`tool_input` 非 dict → 输出 `{}` 退出 0；main 钩子分支整体 try 包裹；补畸形 payload 用例（与 P1 同一测试族）。

### R6 — CFG 规则对 YAML 整体漏报【高，已实证】
- 证据：`posttooluse.py:137-148` 三条模式全要求双引号键（`"password"\s*:` JSON 形态），`:189` 却把 `.yaml/.yml` 归 `config`；注释宣称 "config.json, config.yaml, config.yml"。实证：三条规则对 `password:/username:` YAML 命中均 False；`file_category('config/config.yaml')=='config'`。
- 影响：drogon 支持 YAML 配置场景下高频键名误用（`passwd`/`user` 黑名单）完全不设防——守卫方向缺口。
- 修复：YAML 形态补充无引号键模式（`(?m)^\s*password\s*:`，仅对 config 类文件），或规则按 JSON/YAML 分支；测试补 YAML 正例（当前 CFG×YAML 组合无正向对照）。

### R7 — 技能模板领域错误（2 处，均对撞官方源码证实）【高】
| 技能 | 缺陷 | 官方依据 |
|------|------|----------|
| `drogon-gen-orm-crud/references/code-guide.md:88,94` | batch_insert 模板在 detached `std::thread` 上调 `getEventLoopOfCurrentThread()->queueInLoop(…)`——新线程无 trantor 循环，**必现空指针解引用**；且与模板自身"派回连接所属循环"文字矛盾 | trantor `EventLoop.h:110-116`："Return nullptr if there is no event loop in the current thread" |
| `drogon-gen-coroutine-handler/references/code-guide.md:102-113` | `co_await app().forwardCoro(req, "backend.example.com", 8080)`——第三参是 `double timeout` 非端口；静默变 8080 秒超时+端口丢失 | drogon v1.9.13 `HttpAppFramework.h:760-772`（`forward(…, hostString="", timeout=0)`，coro 版同形） |

修复：orm-crud 模板改捕获 `req->getLoop()`（或 loop 指针参数）再 `queueInLoop`；coroutine 模板改 `forwardCoro(req, "host:port")`。两处同步 `npm/assets`、`drogon_plugin_assets`。
抽查通过项：websocket、redis-config 两技能全部断言与 v1.9.13 头文件/ConfigLoader 行级吻合；coroutine/orm-crud 除上述外其余断言 ✅。

### 中低优先
| # | 项 | 证据 |
|---|----|------|
| M4' | `_skills_ok` expected==0 时"非空即过"退化仍在（刻意降级），残缺包下计数校验失效 | `cli.py:154-158` / `cli.js:122-126` |
| L1 | py↔npm 互操作断裂：py 装的 v3 stamp，npm `uninstall` 不识别 → `.drogon-plugin-install.json` 永久残留 | `cli.js:427-448`；已复现 |
| L2 | npm `--target` 缺值静默按 cwd 执行（py argparse 会报错），行为不对称、typo 即装错目录 | `cli.js:499-506` |
| L3 | `full` 归属的指令文件被用户追加内容后卸载整删（v3 stamp 不记哈希）；建议至少告警 | `cli.py:737-740` |
| L4 | `--scan` 直用模式项目内符号链接文件绕过 realpath 预检（泄露面小） | `posttooluse.py:277-288` |
| L5 | install 循环中途异常无回滚：产物落盘但 stamp 不更新 → 孤儿文件 | `cli.py:434-521` |
| L6 | CPP.007 漏 `sendRequest(req, timeoutVar)` 同步重载；CSP.001 `{{ }}` 跨行漏检 | `posttooluse.py:86,114` |
| L7 | publish.yml 未跑 `check-consistency`/`sync-assets --check`；两 workflow action 未 SHA-pin | `publish.yml:33-46` |

### 测试/门禁盲区（本轮结构性发现）
1. `upgrade` 子命令零 pytest 覆盖（R4 因此漏网）。
2. `test_hooks.py:173` matcher 断言为子串（`"noresume"` 也过）——应改集合相等。
3. 钩子畸形 payload（R5）与 CFG×YAML（R6）均无正/反向用例。
4. `check-consistency` 12 项检查无逐检查反例夹具（方向正确的声明本身未锁）。
5. py↔npm 互操作（L1）、npm 参数严格性（L2）无对照测试。

---

## 5. 第二轮 V1–V6 裁定更新

| # | 裁定 | 依据 |
|---|------|------|
| V1 | **已证实**：Claude `shell` 为文档字段；Codex 对未知字段**忽略**（handler 无 deny_unknown_fields，源码级） | code.claude.com/docs/en/hooks；codex-rs hook_config.rs |
| V2 | **已裁定并升级为新缺陷 R3**：`Write|Edit` 经别名机制命中，但 stdin payload 名为 `apply_patch` → 扫描空转 | codex-rs hook_names.rs:28-39 |
| V3 | **基本证伪必填担忧**：Codex 清单仅 `name` 必填、`interface` 无必填项；真机降级为冒烟确认 | Codex 构建插件文档 |
| V4 | **已证伪**：Trae 规则为 `.trae/rules/*.md`，文档零处 `.mdc` → R10 | docs.trae.ai/ide/rules（页面全文检索） |
| V5 | **已证实**：`globs`/`alwaysApply` 现行有效，`alwaysApply:true` 全文应用 | cursor.com/docs/context/rules |
| V6 | **仍需真机**（Codex 缓存安装下 `source.path` 解析基准无公开样例）；另注意 Codex 原生发现 `.agents/skills`，该兜底通道价值上升 | — |

新增待真机项：V7 = pip 解包 wheel 后钩子脚本可执行位是否保留（P2 关联）；V8 = Codex `additionalContext` ~2500 token 上限下中文规则全文注入是否降级为磁盘预览（N7）。

---

## 6. 整改优先级（建议第四轮执行序）

| 批次 | 项 | 等级 | 一句话动作 |
|------|----|------|-----------|
| ① | R3 | 高 | posttooluse 白名单改黑名单 + `apply_patch` patch 文本解析路径 |
| ① | R2 | 高 | SessionStart matcher → `"*"`；测试改集合相等断言 |
| ① | P1/R5 | 高 | stdin 纳入 `_utf8_stdio` + except ValueError；钩子分支全 try 兜底；同批补畸形/非 ASCII 用例 |
| ② | R4 | 高 | upgrade 复用 stamp hosts 集合、不默认放大 force；补 upgrade 测试族 |
| ② | R6 | 高 | CFG 规则加 YAML 无引号键分支 + 正向对照 |
| ② | R7 | 高 | 修 orm-crud batch_insert 空指针模板、coroutine forwardCoro 端口/超时参数；同步两份资产副本 |
| ③ | R1/R10 | 高/低 | marketplace `source` → `"./"`（进门禁）；Trae 改走 AGENTS.md、撤 `.mdc` |
| ③ | P2 | 中高 | npm `copyAssets` 后对 4 个钩子文件 chmod 755 |
| ④ | N3/N4/N5/L1–L7/M4' | 中低 | 按需；L1/L2 建议随 ② 批次（同文件改动） |
| ⑤ | 门禁 | — | 盲区 1–5 各补正/反向用例；publish.yml 加 check-consistency；CI 矩阵加 py3.9/3.13 |

> 所有 `skills/`、`hooks/` 修复必须走 `scripts/gen-host-artifacts.py` + `sync-assets` 同步链，`npm/assets/` 与 `drogon_plugin_assets/` 为生成物，勿手改。
