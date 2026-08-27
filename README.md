# drogon-claude-plugin

> **Drogon C++ 后端开发的 Claude Code 插件** — 提供 AI 辅助开发规则与代码生成技能，让 AI 写出正确的异步代码，避开回调/事件循环等高频陷阱。

[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![PyPI version](https://img.shields.io/pypi/v/drogon-claude-plugin.svg)](https://pypi.org/project/drogon-claude-plugin/)
[![npm version](https://img.shields.io/npm/v/drogon-claude-plugin.svg)](https://www.npmjs.com/package/drogon-claude-plugin)
[![Claude Code](https://img.shields.io/badge/Claude%20Code-plugin-8A2BE2)](https://docs.anthropic.com/en/docs/claude-code/plugins)

基于 [Drogon](https://github.com/drogonframework/drogon) C++ HTTP 框架的应用项目提供 **AI 辅助开发规则与代码生成技能**，让 AI 写出正确的异步代码，避开回调/事件循环等高频陷阱。

## 安装

### 方式 A：通过 marketplace（推荐）

```bash
# 添加 marketplace 源（首次）
claude plugin marketplace add https://github.com/voidvec/drogon-claude-plugin

# 安装插件
claude plugin install drogon

# 更新到最新版
claude plugin update drogon
```

### 方式 B：通过 npm / PyPI（CLI 安装器）

```bash
# npm
npx drogon-claude-plugin install

# 或 PyPI
pipx install drogon-claude-plugin
drogon-plugin install
```

> 两种包共用同一份插件资产，CLI 提供 `install` / `verify` / `uninstall` 子命令，详见 [CLI 安装器](#--cli-安装器)。

### 方式 C：本地安装

```bash
git clone https://github.com/voidvec/drogon-claude-plugin
cd <你的 drogon 项目>
claude plugin install ../drogon-claude-plugin --scope project
```

### 验证安装

```bash
claude plugin details drogon
```

应显示 17 个技能和 2 个钩子（SessionStart + PostToolUse）。

## CLI 安装器

`drogon-claude-plugin` 同时发布到 [npm](https://www.npmjs.com/package/drogon-claude-plugin) 与 [PyPI](https://pypi.org/project/drogon-claude-plugin/)，两种包内置同一份插件资产（skills / hooks / CLAUDE.md / .claude-plugin），并提供一致的命令行界面（bin 名均为 `drogon-plugin`）：

| 命令 | 作用 |
|------|------|
| `drogon-plugin install [--scope project\|user\|local]` | 将插件资产拷贝到当前项目（或指定 scope），并提示执行 `claude plugin install` 启用 |
| `drogon-plugin verify` | 校验插件的技能数 / 钩子 / manifest，输出结构报告 |
| `drogon-plugin uninstall` | 从当前项目（或由 `--target` 指定目录）移除已安装的插件资产 |
| `drogon-plugin version` | 显示 CLI 与内置插件版本 |

安装器只负责**分发与落盘**，不替换 Claude Code 官方插件机制——启用插件仍走 `claude plugin install`。

## 功能组件

### 规则层（CLAUDE.md，自动注入会话上下文）

CLAUDE.md 采用**精简路由**设计：只保留跨所有任务的顶层纪律（异步回调模型、事件循环模型）+ Skill 路由表，**详细知识（模板、API 速查、配置格式、禁止模式）全部下沉到各 Skill 的 `references/code-guide.md` 按需加载**，避免常驻占用上下文。

顶层纪律覆盖：

- **A 异步回调模型**：回调恰好一次、按值捕获、禁阻塞、优先协程、异常安全
- **B 事件循环模型（Trantor IO）**：不阻塞循环、重活走线程池、跨循环共享状态加锁
- **通用纪律**：所有 I/O 异步、异步操作双回调、异常不逃逸 handler、配置加载 try/catch、键名严格

### 代码生成技能（17 个）

每个技能提供准确的 drogon API 用法、代码模板与常犯错误警告。遇到对应任务时 AI 主动调用，按需加载详细知识：

| 技能 | 用途 |
|------|------|
| `drogon-create-controller` | 生成控制器（Simple/Http/WebSocket），含路径前缀差异、`:param`、自动注册 |
| `drogon-gen-cmake` | 生成 CMakeLists.txt，含 Conan、插件过滤器编译 |
| `drogon-gen-csp-view` | 生成 CSP 视图模板，含 `drogon_ctl create view` 管线、布局 |
| `drogon-gen-db-config` | 生成数据库配置，含键名黑名单、SQL 注入防护、运行期异常 |
| `drogon-gen-filter` | 生成 Filter 请求拦截器 |
| `drogon-gen-middleware` | 生成 Middleware 处理链 |
| `drogon-gen-plugin` | 生成 Plugin 系统级扩展（连接池/SDK 初始化），含三者职责边界 |
| `drogon-gen-orm-crud` | 生成 ORM CRUD 代码，含禁 `execSqlSync`、事务纪律 |
| `drogon-gen-redis-config` | 生成 Redis 配置 + 单例/异步/订阅防泄漏用法 |
| `drogon-gen-test` | 生成 DROGON_TEST 测试，含断言宏、CMake 扫描 |
| `drogon-setup-config` | 生成完整配置文件，含路径解析、键名黑名单、多环境 |
| `drogon-gen-session-auth` | 生成 Session 登录/登出/鉴权 handler（防 fixation） |
| `drogon-gen-file-upload` | 生成文件上传 handler（MultiPartParser + 校验 + 落盘） |
| `drogon-gen-advice` | 生成 AOP Advice（11 切面，拦截型/观察型） |
| `drogon-gen-coroutine-handler` | 生成协程 handler/中间件/ORM（参数按值，区分 Task/AsyncTask，含 `forwardCoro`） |
| `drogon-gen-http-client` | 生成出站 HttpClient 调用（异步/协程/反向代理） |
| `drogon-gen-lambda-handler` | 生成 `registerHandler` lambda 路由（`{N}` 参数绑定） |

### 自动化检测钩子（PostToolUse）

在 AI 编辑文件后自动扫描 drogon API 违规：

| 文件类型 | 检测项 |
|---------|--------|
| `.h/.cc/.cpp` | `FILTER_ADD`、`ADD_MIDDLEWARE`、`METHOD_LIST_ADD`、`createDbClient`、`AsyncTask`+`co_await` 未兜异常、回调式 `HttpMiddleware` 内 `co_await`、同步 `sendRequest` 死锁、`session->operator[]`、Advice 在 handler 内注册 |
| `.csp` | `{{ }}`、`<%raw%>`、`<%viewpath`、`@@key@@`、`<%extends`、`{% if %}` |
| `config.json/.yaml` | `"password"`、`"username"`、`"ssl": "字符串"` |
| `test*.cc` | `done()`、`ASSERT_*`、`createDbClient` |

> v0.2.0 修复：C++ 标识符检测改为大小写敏感（不再误报 `isDone()`）；移除与 CLAUDE.md 示例冲突的 callback 变量名硬约束。

## 使用

在 drogon 项目中启用插件后，AI 自动生效。典型对话：

```
> 创建一个 /api/users 的 REST 控制器
AI: [使用 drogon-create-controller 技能] 生成 UserController.h/.cc...

> 添加一个 JWT 认证过滤器
AI: [使用 drogon-gen-filter 技能] 生成 JwtAuthFilter.h + registerFilter()...

> 写一个测试验证用户注册接口
AI: [使用 drogon-gen-test 技能] 生成 DROGON_TEST(UserRegister)...

> 这个 handler 代码有问题吗？
AI: [对照 CLAUDE.md 异步回调纪律] 这个 handler 的提前返回路径没有调用 callback...
```

## 前提

- Claude Code CLI 已安装
- 插件用于 **依赖 drogon 框架的应用项目**（drogon 本身作为库被安装）
- Python 3 在 PATH 中（PostToolUse 钩子需要）

## 仓库结构

```
├── .claude-plugin/
│   ├── plugin.json
│   └── marketplace.json
├── .github/workflows/
│   ├── ci.yml              # 插件结构/CLI 冒烟测试
│   └── publish.yml         # tag 触发 → PyPI + npm + GitHub Release
├── hooks/
│   ├── hooks.json
│   └── posttooluse.py
├── src/drogon_plugin/      # PyPI 包（CLI 安装器）
│   ├── __init__.py
│   └── cli.py
├── npm/                    # npm 包（CLI 安装器）
│   ├── package.json
│   └── bin/cli.js
├── skills/
│   ├── drogon-create-controller/
│   ├── drogon-gen-advice/
│   ├── drogon-gen-cmake/
│   ├── drogon-gen-coroutine-handler/
│   ├── drogon-gen-csp-view/
│   ├── drogon-gen-db-config/
│   ├── drogon-gen-file-upload/
│   ├── drogon-gen-filter/
│   ├── drogon-gen-http-client/
│   ├── drogon-gen-lambda-handler/
│   ├── drogon-gen-middleware/
│   ├── drogon-gen-orm-crud/
│   ├── drogon-gen-plugin/
│   ├── drogon-gen-redis-config/
│   ├── drogon-gen-session-auth/
│   ├── drogon-gen-test/
│   └── drogon-setup-config/
├── CLAUDE.md
├── LICENSE
├── README.md
└── pyproject.toml           # PyPI 打包配置
```

## 许可

MIT — 详见 [LICENSE](LICENSE)。
