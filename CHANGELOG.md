# Changelog

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 与 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

发布流程：**更新本文件 → 同步四处版本号（`plugin.json` / `__init__.py`（含 `PLUGIN_VERSION`） / `pyproject.toml` / `npm/package.json`）→ 打 tag `vX.Y.Z`**（tag 名必须与版本号一致，publish.yml 已加断言），CI 自动发布 PyPI + npm + GitHub Release。

## [Unreleased]

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

[Unreleased]: https://github.com/voidvec/drogon-claude-plugin/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/voidvec/drogon-claude-plugin/compare/v0.1.2...v0.2.0
[0.1.2]: https://github.com/voidvec/drogon-claude-plugin/releases/tag/v0.1.2
[0.1.1]: https://github.com/voidvec/drogon-claude-plugin/releases/tag/v0.1.1
[0.1.0]: https://github.com/voidvec/drogon-claude-plugin/releases/tag/v0.1.0
