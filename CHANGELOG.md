# Changelog

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 与 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

发布流程：**更新本文件 → 同步四处版本号（`plugin.json` / `__init__.py`（含 `PLUGIN_VERSION`） / `pyproject.toml` / `npm/package.json`）→ 打 tag `vX.Y.Z`**（tag 名必须与版本号一致，publish.yml 已加断言），CI 自动发布 PyPI + npm + GitHub Release。

## [Unreleased]

### Fixed

- ci.yml:validate-plugin 在 pytest 前先运行 `sync-assets.py` 生成 `drogon_plugin_assets/`(该目录 gitignore,test_hosts.py 依赖其存在;此前该测试从未在 CI 真正执行过,一直被上游 Unicode 崩溃掩盖)。

## [0.3.1] - 2026-09-21

CI/发布修复版本。0.3.0 的 publish.yml 存在 YAML 解析错误,发布从未实际执行;且 `0.3.0` 文件名在 PyPI 曾被上传后删除而永久禁用复用,故以 0.3.1 发布。

### Fixed

- **publish.yml 解析错误**:heredoc 内 Python 代码顶格书写,提前终止了 `run: |` 块标量,workflow 整体解析失败(publish run 零 job 即失败)。改为纯 bash 断言 `tag == VERSION`,全部清单版本一致性复用 `gen-host-artifacts.py --check`(单一事实源,覆盖面更全);`setup-python` 移至断言之前,不再依赖 runner 预装 python3。
- **Windows cp1252 UnicodeEncodeError**:Windows runner 管道 stdout 默认 cp1252,print `✅`/中文 抛异常,validate-plugin 与 CLI smoke 两个 job 均失败:
  - ci.yml / publish.yml 顶层 `env.PYTHONUTF8: 1`;
  - CLI / scripts / hook 各入口将 stdout/stderr reconfigure 为 UTF-8(同步保护 Windows 终端与管道场景下的最终用户);
  - dev-smoke-test.py 对子进程输出显式按 UTF-8 解码。

## [0.3.0] - 2026-09-21

多宿主版本:Codex / Cursor / VS Code (Copilot) / Gemini CLI / Qoder / CodeBuddy / Trae / 通用 `.agents` 接入(方案与两轮对抗性评审见 `docs/INTEGRATION-PLAN-v0.3.0.md`、`docs/INTEGRATION-REVIEW-v0.3.0.md`;全部宿主落点依据官方文档实读)。

### Added

- **仓库级宿主产物**(由 `scripts/gen-host-artifacts.py` 从单一事实源生成,`VERSION` 文件为版本唯一来源):
  - `AGENTS.md` / `GEMINI.md`:CLAUDE.md 去宿主专有内容的中立规则层;
  - `.codex-plugin/plugin.json` + `.agents/plugins/marketplace.json`(Codex 原生格式,policy 三件套):`codex plugin marketplace add voidvec/drogon-claude-plugin` 即装;
  - `gemini-extension.json`:`gemini extensions install <repo>` 即装(skills 自动发现 + GEMINI.md 上下文)。
- **CLI v3(PyPI,参考实现)**:
  - `install --host <claude|zcode|codex|cursor|copilot|agents|gemini|qoder|codebuddy|trae|all>`,`all` 含互斥规则(有专有清单的宿主不重复落 `.agents/skills`);
  - **指令文件三态保护**:AGENTS.md/GEMINI.md/CODEBUDDY.md 已存在时默认跳过并打印合并指引,`--force-agents` 才追加标记段,卸载只删标记段;
  - `scan [--format json] [--strict] [路径...]`:无钩子宿主 / CI 违规扫描(进程内执行,路径限定项目内);
  - `hosts` 子命令;`verify` 逐宿主报告;`uninstall --host` 按宿主清理;安装戳 `.drogon-plugin-install.json` 记录全部落点。
- **posttooluse.py `--scan` 模式**:独立扫描器(文件/目录参数、human/json 输出、`--strict` 退出码、cwd 边界护栏)。
- **测试**:新增 `tests/test_hosts.py`(18 例:生成器产物、Codex policy 字段、三态保护、互斥落盘、per-host 卸载、scan 契约、九处清单版本一致性),套件 47 例全绿。
- **CI/发布**:publish.yml 断言 tag == VERSION == 全部清单版本 + 宿主产物最新;ci.yml 增加生成器 `--check`。

### Changed

- sync-assets:发行资产纳入 AGENTS.md/GEMINI.md/gemini-extension.json/.codex-plugin;`.agents/`(Codex 市场发现入口)不入资产。

### Known limitations(如实声明)

- npm CLI 保持 v0.2 行为(bundle 安装/校验/卸载,与 0.3.0 资产完全兼容):多宿主 `--host` 与 `scan` 暂仅 PyPI CLI 提供(安全扫描器对 Node 侧动态路径子进程模式的持续误报,按风险权衡推迟;行为差异已在 README 标注)。
- 行为性验证(各宿主真实会话中技能触发)为一次性人工步骤,清单见评审文档 §Phase C;结构性验证已自动化入 CI。
- Codex 对本仓库 legacy `.claude-plugin/marketplace.json` 的兼容度、Cursor hooks 事件模型为待实测项(不阻塞使用;`.agents/plugins/marketplace.json` 为 Codex 主路径)。

## [0.2.0] - 2026-09-20

生产级跨平台与双宿主版本：Windows / Linux / macOS 三平台安装-升级-卸载全链路，Claude Code 与 ZCode 双宿主，技能层补齐官方文档全部功能域。

### Added — 跨平台与双宿主（P0）

- **ZCode 宿主支持**：新增 `.zcode-plugin/plugin.json`（与 `.claude-plugin` 同步），随包分发；ZCode 直接兼容标准 Claude 插件格式。
- **跨平台钩子架构**（替换 v0.1.x 裸调 `python` 的方案——该方案在 Ubuntu 24.04+（无 `python` 命令）和多数 Windows 环境下静默失效）：
  - `hooks/run-hook.cmd`：多语言启动器（superpowers 插件验证过的模式），Windows 经批处理段定位 Git Bash，Unix 经 bash ENOEXEC 回退直接执行；
  - `hooks/session-start`：**纯 shell** 规则注入，零解释器依赖；
  - `hooks/post-tool-use`：Python 3 探测链（`DROGON_PLUGIN_PYTHON` → `python3` → `python` → `py`，含版本校验），缺失时静默降级；
  - `hooks.json` 改为 `shell: "bash"` + run-hook.cmd 分发，双宿主字段兼容。
- **CLI 安装器 v2**（PyPI + npm 同步）：
  - 新增 `upgrade` 子命令（版本比对 + v0.1.x 根目录布局自动迁移）；
  - 安装布局改为自包含 `.drogon-plugin/` 子目录，**不再覆盖项目根的 `CLAUDE.md` 等自有文件**；
  - 卸载/迁移逐项归属校验（安装戳 + 内容签名），项目自有文件绝不误删；拒绝在文件系统根/用户主目录操作；
  - 安装后打印 Claude Code 与 ZCode 双宿主启用指引。
- **测试体系**（`tests/`，27 个用例）：违规扫描器逐条正例/反例 fixture（含 v0.1.0 误报回归：`cb`/`cbPtr` 命名自由、`isDone()`/`task.done` 大小写豁免）、结构校验（技能清单/frontmatter/路由表/四处版本一致性/钩子文件）、钩子端到端（Windows 显式定位 Git Bash，规避 WSL bash 路径不可见问题）。
- **CI 三平台矩阵**：validate-plugin 与 smoke-cli 均跑 ubuntu / macos / windows，含 SessionStart 钩子端到端冒烟。
- **publish.yml 版本一致性断言**：tag 名与四处版本号不符即失败（防复发 v0.1.2 发布事故）。

### Added — 技能层覆盖补齐（17 → 22 个）

新增 5 个技能，全部对照 drogon v1.9.13 源码逐 API 核对（两个真实生产项目验证的高价值缺口）：

- `drogon-gen-orm-model`：`drogon_ctl create model` 工作流——真实参数（`--table=`/`-f`/`-o`/`--clear-output`，注意 `-a`/`--r`/`--restful` 等旧文档参数**在 v1.9.13 不存在**，全库/关系/restful 均走 model.json）、生成物 DO-NOT-EDIT 约定、CMake OBJECT library 接入、MSVC/C++20 codecvt shim（force-include 方案）；
- `drogon-gen-rate-limiter`：Hodor 插件全字段（源码核对，如 `trust_ips` 而非报错文案里的 "trusted_ips"；`user_capacity` 需 `setUserIdGetter` 否则静默失效）+ 自定义 429（authforge 模式）+ 编程式 `RateLimiter`/`SafeRateLimiter` + Redis 分布式；
- `drogon-gen-monitoring`：PromExporter + Counter/Gauge/Histogram（`increment()` 而非 `add()`；官方示例实为 `HttpCoroMiddleware` 挂载）+ 原子计数器补充模式；
- `drogon-gen-websocket`：真实宏名（`WS_PATH_LIST_BEGIN` 而非 `WS_PATH_BEGIN`）、三 handler 签名（消息为右值 `std::string&&`）、框架自动心跳、`send` 跨线程安全（trantor 内部 queueInLoop）、广播用 PubSubService 模式；
- `drogon-gen-stream`：流式上传三回调模型 + `newStreamResponse`/`newAsyncStreamResponse` 流式响应（HttpResponse.h 源码核对）+ 背压策略。

### Changed — 既有技能强化（对照源码修正多处文档性错误）

- `drogon-setup-config`（91→310 行）：HTTPS 监听全字段、静态文件 13 字段、`custom_config`+`getCustomConfig` 四种读取模式、`loadConfigJson`+.env 占位符替换（pay-plugin 模式）、多环境切换（authforge 模式）；标注 `enable_static_file_cache` **不存在**；
- `drogon-gen-redis-config`（54→188 行）：`execCommandAsync` 双回调模板、`%s`/`%b` 格式语义、订阅真实 API（`newSubscriber()`+`subscribe`，非 `subscribeAsync`）、失败回调异常实为 `RedisException`、协程、常用命令速查；
- `drogon-gen-cmake`（63→220 行）：`drogon_create_views` 位置参数真实签名、`ParseAndAddDrogonTests`（非 `drogon_discover_tests`）、drogon_ctl 模型 OBJECT 库接入、Conan 2 完整链、MSVC 专项（`/bigobj`、`/FI`、`/utf-8`）、目标名统一 `Drogon::Drogon`；
- `drogon-gen-plugin`（127→297 行）：六步生命周期时序、`shutdown()` 优雅排水骨架（EventLoopThread + promise 哨兵）、静态库 `ensureLinked` 对策、BeginningAdvice 分工清单；
- `drogon-gen-session-auth`（108→187 行）：Cookie 安全一节（`setHttpOnly` 默认 true、`kNone` 自动连带 Secure、`setPartitioned` 联动、禁手拼 Set-Cookie）；
- `drogon-gen-test`（125→283 行）：自定义 test main（`DROGON_TEST_MAIN` 宏实际不存在于 drogon_test.h，pay-plugin 的 define 是无效残留）、端口隔离（PAY_TEST_PORT 模式）、CMake POST_BUILD 接线；
- `CLAUDE.md`：路由表扩至 22 技能；A/B 组补充 `setExceptionHandler`、协程参数按值、`IOThreadStorage`、`EventLoopThread` 指引；新增"优先内建能力""生成代码不手改"通用纪律；新增安装/升级一节。

### Fixed

- `posttooluse.py`：`session->operator[]` 正则无法匹配 `sessionPtr` 等变量名（`\b` 误用）——已修复并有回归 fixture。

## [0.1.2] - 2026-08-28

- 文档与品牌：双语 README（en 默认）、npm 包 README、社区文件（CODE_OF_CONDUCT / SECURITY / ISSUE 模板）、清理本地路径泄露；CI 修复 smoke-cli 资产同步。

## [0.1.1] - 2026-08-27

- CLI 命令统一为 `drogon-claude-plugin`；wheel 资产打包修复（setuptools src layout 需显式 `package-data`）；资产同步过滤 `__pycache__`。

## [0.1.0] - 2026-08-27

首次公开发布。

- 17 个 drogon 开发技能（控制器 / ORM / 协程 / 中间件 / 插件 / 测试等）
- 精简路由 CLAUDE.md：顶层纪律 + Skill 路由表，详细知识下沉到各 skill 的 `references/code-guide.md`
- PostToolUse 钩子：编辑后自动扫描 drogon API 违规并告警
- PyPI / npm 双发行包（CLI 安装器）、GitHub Actions（ci.yml / publish.yml）

[Unreleased]: https://github.com/voidvec/drogon-claude-plugin/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/voidvec/drogon-claude-plugin/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/voidvec/drogon-claude-plugin/compare/v0.1.2...v0.2.0
[0.1.2]: https://github.com/voidvec/drogon-claude-plugin/releases/tag/v0.1.2
[0.1.1]: https://github.com/voidvec/drogon-claude-plugin/releases/tag/v0.1.1
[0.1.0]: https://github.com/voidvec/drogon-claude-plugin/releases/tag/v0.1.0
