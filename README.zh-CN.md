# drogon-claude-plugin

> **Drogon C++ 后端开发 coding agent 插件** — 提供 AI 辅助开发规则与代码生成技能，让 AI 写出正确的异步代码，避开回调 / 事件循环等高频陷阱。**Claude Code 与 ZCode 双宿主**，**Windows / Linux / macOS** 全平台可用。

[English](README.md) | **简体中文**

[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![CI](https://github.com/voidvec/drogon-claude-plugin/actions/workflows/ci.yml/badge.svg)](https://github.com/voidvec/drogon-claude-plugin/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/drogon-claude-plugin.svg)](https://pypi.org/project/drogon-claude-plugin/)
[![npm version](https://img.shields.io/npm/v/drogon-claude-plugin.svg)](https://www.npmjs.com/package/drogon-claude-plugin)
[![Claude Code](https://img.shields.io/badge/Claude%20Code-plugin-8A2BE2)](https://docs.anthropic.com/en/docs/claude-code/plugins)
[![ZCode](https://img.shields.io/badge/ZCode-plugin-8A2BE2)](https://z.ai)

面向基于 [Drogon](https://github.com/drogonframework/drogon) C++ HTTP 框架应用项目的 [Claude Code](https://docs.anthropic.com/en/docs/claude-code/plugins) / [ZCode](https://z.ai) 插件。提供 AI 辅助开发规则与 **22 个代码生成技能**，让 AI 产出正确、地道的异步代码，避开回调 / 事件循环的高频陷阱。

## 安装

### 方式 A：通过 marketplace（推荐，双宿主）

**Claude Code：**

```bash
# 添加 marketplace 源（首次）
claude plugin marketplace add https://github.com/voidvec/drogon-claude-plugin

# 安装 / 升级 / 卸载
claude plugin install drogon
claude plugin update drogon
claude plugin uninstall drogon
```

**ZCode：** 在 ZCode 的插件管理中添加同一 marketplace（`https://github.com/voidvec/drogon-claude-plugin`），然后安装 `drogon` 插件。ZCode 直接兼容标准 Claude 插件格式——技能、钩子、规则注入行为完全一致。

### 方式 B：通过 npm / PyPI（CLI 安装器）

npm 与 PyPI 两种包**内置同一份插件资产**，提供 `install` / `verify` / `upgrade` / `uninstall` / `version` 子命令。资产装入项目内自包含的 `.drogon-plugin/` 子目录——**绝不触碰项目自有文件**（包括你自己的 `CLAUDE.md`）。

```bash
# npm（免安装，直接跑）
npx drogon-claude-plugin install

# 或 PyPI（推荐，可持久使用）
pipx install drogon-claude-plugin
drogon-claude-plugin install
```

> CLI 安装器只负责**分发与落盘**资产，不替代宿主的插件机制——安装后按 CLI 打印的指引执行一次本地注册（`claude plugin install .drogon-plugin --scope project`，或 ZCode 走 marketplace），之后升级用 `drogon-claude-plugin upgrade` 或 `claude plugin update drogon`。

### 方式 C：从源码安装

```bash
git clone https://github.com/voidvec/drogon-claude-plugin
cd <你的 drogon 项目>
claude plugin install ../drogon-claude-plugin --scope project
```

### 验证安装

```bash
claude plugin details drogon        # Claude Code
drogon-claude-plugin verify         # CLI 安装器（任意宿主皆可校验）
```

应看到 **22 个技能**与 **2 个钩子**（SessionStart + PostToolUse）。

## CLI 安装器

`drogon-claude-plugin` 同时发布于 [npm](https://www.npmjs.com/package/drogon-claude-plugin) 与 [PyPI](https://pypi.org/project/drogon-claude-plugin/)，两包内容一致：

| 命令 | 作用 |
|------|------|
| `drogon-claude-plugin install [--target DIR]` | 把插件资产装入 `<DIR>/.drogon-plugin/`，并打印双宿主启用指引 |
| `drogon-claude-plugin verify [--target DIR]` | 校验已安装结构（技能/钩子/清单/版本一致性） |
| `drogon-claude-plugin upgrade [--target DIR]` | 升级到随包版本（自动迁移 v0.1.x 根目录布局） |
| `drogon-claude-plugin uninstall [--target DIR]` | 移除插件资产——逐项归属校验，项目自有 `CLAUDE.md` 绝不会被误删 |

## 插件构成

三层结构，各司其职：

| 层 | 位置 | 职责 |
|----|------|------|
| **规则** | `CLAUDE.md` | 每个会话自动注入的顶层纪律（异步回调模型、事件循环模型） |
| **技能** | `skills/`（22 个） | 按需加载的 drogon 代码生成/配置技能，深度知识在 `references/code-guide.md` |
| **检测** | `hooks/`（2 个） | 编辑后扫描文件，标记 drogon API 违规并提示修复 |

### 规则层 — `CLAUDE.md`

**精简路由**设计：只有对*所有*任务都成立的纪律（异步回调模型、事件循环模型）与技能路由表留在 `CLAUDE.md`。其余——模板、API 速查、配置格式、禁止模式——全部下沉到各技能的 `references/code-guide.md`，**按需加载**，节省上下文窗口。

顶层纪律覆盖：

- **A. 异步回调模型** — 恰好回调一次、按值捕获、不阻塞、优先协程（参数必须按值！）、异常安全
- **B. 事件循环模型（Trantor IO）** — 绝不阻塞循环、重活儿走线程池、跨循环共享状态加锁
- **通用** — 所有 I/O 异步、异步操作双回调、异常不逃逸、配置加载 try/catch、键名严格、优先内建能力（Hodor/PromExporter/AccessLogger）、生成代码不手改

### 代码生成技能（22 个）

每个技能的 `references/code-guide.md` 均对照 **drogon v1.9.13 源码**（而非仅文档）编写——官方文档与源码不一致处以源码为准并显式标注。

| 技能 | 用途 |
|------|------|
| `drogon-create-controller` | 控制器（Simple/Http/WebSocket）、路径前缀差异、`:param`、自动注册 |
| `drogon-gen-lambda-handler` | `registerHandler` lambda 路由（`{N}` 参数绑定） |
| `drogon-gen-orm-crud` | ORM CRUD（回调式+协程式）；禁 `execSqlSync`、事务纪律 |
| `drogon-gen-orm-model` | `drogon_ctl create model` 工作流：model.json 配置、生成物约定、CMake 接入、MSVC/C++20 codecvt shim |
| `drogon-gen-db-config` | 数据库配置、键名黑名单、SQL 注入防护、运行期异常 |
| `drogon-gen-redis-config` | Redis 配置 + `execCommandAsync` 双回调、订阅防泄漏、协程 |
| `drogon-setup-config` | 完整配置：HTTPS 监听、静态文件、`custom_config`/`getCustomConfig`、`loadConfigJson`、多环境 |
| `drogon-gen-cmake` | CMake 构建：`drogon_create_views`、drogon_ctl 模型接入、Conan 2、MSVC 专项 |
| `drogon-gen-coroutine-handler` | 协程 handler/中间件/ORM（参数按值、Task vs AsyncTask、`forwardCoro`） |
| `drogon-gen-http-client` | 出站 HttpClient（异步/协程/反向代理） |
| `drogon-gen-csp-view` | CSP 视图模板、`drogon_ctl create view` 管线、布局 |
| `drogon-gen-filter` | Filter 请求拦截器 |
| `drogon-gen-middleware` | Middleware 处理链 |
| `drogon-gen-plugin` | 系统级插件：完整生命周期、`shutdown()` 排水、专属 EventLoopThread、静态库注册丢失对策 |
| `drogon-gen-advice` | AOP 切面（11 个，拦截型 vs 观察型） |
| `drogon-gen-file-upload` | 文件上传（MultiPart 解析+校验+落盘） |
| `drogon-gen-stream` | 流式上传（RequestStream）与 chunked 流式响应（`newStreamResponse`/`newAsyncStreamResponse`） |
| `drogon-gen-session-auth` | Session 登录/登出/鉴权（防 fixation）+ Cookie 安全 |
| `drogon-gen-websocket` | WebSocket 控制器、连接管理/广播、跨线程 send 安全、心跳 |
| `drogon-gen-rate-limiter` | Hodor 配置 + 自定义 429；编程式 RateLimiter/SafeRateLimiter；Redis 分布式限流 |
| `drogon-gen-monitoring` | Prometheus 指标（PromExporter + Counter/Gauge/Histogram） |
| `drogon-gen-test` | DROGON_TEST：断言宏、异步测试、自定义 main、端口隔离 |

### 检测钩子（跨平台、规则注入零依赖）

PostToolUse 钩子在 AI 每次编辑后扫描 drogon API 违规；SessionStart 钩子注入规则层。钩子执行采用**多语言启动器**（`hooks/run-hook.cmd`，superpowers 插件验证过的成熟模式）：

- **SessionStart 是纯 shell 实现**——不依赖 Python/Node 等解释器，Windows（Git Bash）/Linux/macOS 三平台、Claude Code 与 ZCode 双宿主行为一致。
- **PostToolUse** 自动探测 Python 3（`python3` → `python` → `py`，可用 `DROGON_PLUGIN_PYTHON` 覆盖），找不到时静默降级——绝不拖垮宿主。
- v0.1.x 的钩子裸调 `python`，在 Ubuntu 24.04+（无 `python` 命令）和多数 Windows 环境下静默失效——v0.2.0 已修复。

| 文件类型 | 检测项 |
|----------|--------|
| `.h/.cc/.cpp` | `FILTER_ADD`、`ADD_MIDDLEWARE`、`METHOD_LIST_ADD`、`createDbClient`、未包 try/catch 的 `AsyncTask`+`co_await`、回调式中间件里的 `co_await`、阻塞式 `sendRequest`、`session->operator[]`、handler 内注册 Advice |
| `.csp` | `{{ }}`、`<%raw%>`、`<%viewpath`、`@@key@@`、`<%extends`、`{% if %}` |
| `config.json/.yaml` | `"password"`、`"username"`、字符串形式的 `"ssl"` |
| `test*.cc` | `done()`、`ASSERT_*`、`createDbClient` |

## 使用效果

在 drogon 项目中启用后自动生效。典型对话：

```
> 给 /api/users 建一个 REST 控制器
AI: [调用 drogon-create-controller] 生成 UserController.h + UserController.cc...

> 从生产库 schema 生成 ORM 模型
AI: [调用 drogon-gen-orm-model] 写 model.json、跑 drogon_ctl create model、
    把 OBJECT library + orm_compat shim 接进 CMake...

> 给用户注册接口写个测试
AI: [调用 drogon-gen-test] 生成 DROGON_TEST(UserRegister) 用例...

> 这个 handler 写得对吗？
AI: [依据 CLAUDE.md 异步纪律] 这个 handler 的提前返回路径没有调用 callback...
```

## 环境要求

- Claude Code 或 ZCode
- 一个**依赖 drogon 框架**的项目（drogon 作为库安装）
- 规则注入（SessionStart）：开箱即用——需要 bash（Windows 即 Git Bash，两个宿主本就依赖它）
- 违规扫描（PostToolUse）：可选，需要机器上有任意 Python 3 解释器

## 仓库结构

```
├── .claude-plugin/         # Claude Code 清单 + marketplace 条目
├── .zcode-plugin/          # ZCode 清单（与 .claude-plugin 同步）
├── .github/workflows/
│   ├── ci.yml              # 三平台矩阵：结构 + 钩子 + CLI 冒烟测试
│   └── publish.yml         # tag 触发 → PyPI + npm + GitHub Release
├── scripts/                # 构建辅助（资产同步 + 冒烟测试）
├── hooks/
│   ├── hooks.json          # SessionStart + PostToolUse 注册
│   ├── run-hook.cmd        # 跨平台多语言启动器
│   ├── session-start       # 纯 shell 规则注入
│   ├── post-tool-use       # 探测 Python 3，缺失时优雅降级
│   └── posttooluse.py      # 违规扫描器
├── skills/                 # 22 个代码生成技能
├── tests/                  # pytest：扫描器、结构校验、钩子端到端
├── src/drogon_plugin/      # PyPI 包（CLI 安装器）
├── npm/                    # npm 包（CLI 安装器）
├── CLAUDE.md               # 规则层
└── CHANGELOG.md
```

## 许可

MIT — 见 [LICENSE](LICENSE)。
