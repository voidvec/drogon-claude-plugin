# drogon-claude-plugin

Claude Code 插件，为基于 [Drogon](https://github.com/drogonframework/drogon) C++ HTTP 框架的应用项目提供 **AI 辅助开发规则与代码生成技能**。

让 AI 写出正确的异步代码，避开回调/事件循环等高频陷阱。

## 安装

### 方式 1：通过 marketplace（推荐）

```bash
# 添加 marketplace 源（首次）
claude plugin marketplace add https://github.com/vilas/drogon-claude-plugin

# 安装插件
claude plugin install drogon

# 更新到最新版
claude plugin update drogon
```

### 方式 2：本地安装

```bash
git clone https://github.com/vilas/drogon-claude-plugin
cd <你的 drogon 项目>
claude plugin install ../drogon-claude-plugin --scope project
```

### 验证安装

```bash
claude plugin details drogon
```

应显示 10 个技能和 2 个钩子（SessionStart + PostToolUse）。

## 功能组件

### 规则层（CLAUDE.md，自动注入会话上下文）

11 组可执行约束，覆盖 drogon 全栈开发的核心陷阱：

| 组 | 主题 | 内容 |
|----|------|------|
| A | 异步回调模型 | 回调恰好一次、按值捕获、禁阻塞、优先协程、异常安全 |
| B | Trantor IO/事件循环 | 不阻塞循环、重活走线程池、跨循环共享状态 |
| C | drogon_ctl 脚手架 | `create controller/view/filter/model/project` 用法 |
| D | 控制器注册与路由 | `PATH_ADD`（1 参数）/ `METHOD_ADD`（3 参数）/ `WS_PATH_ADD` |
| E | 配置文件 | `config.json` 结构与 `app.loadConfigFile()` |
| F | CMake/构建集成 | `find_package(drogon)` 与 CMake 目标 |
| G | ORM 数据层 | Mapper CRUD、异步回调与协程模式、Criteria |
| H | 数据库连接配置 | `passwd` 而非 `password`、`addDbClient` 而非 `createDbClient` |
| I | Redis 客户端 | 异步 redis 操作、`newTransactionAsync`、连接配置 |
| J | CSP 视图模板 | `@@`、`$$`、`[[ ]]`、`<%c++ %>`、`<%layout %>` 语法 |
| K | Plugin/Filter/Middleware | `registerFilter()`/`registerMiddleware()`，不存在 `FILTER_ADD` 等宏 |
| L | DROGON_TEST 测试 | `CHECK`/`REQUIRE`/`MANDATE` 断言，异步测试模式，无 `done()` |

### 代码生成技能（10 个）

每个技能提供准确的 drogon API 用法与常犯错误警告：

| 技能 | 用途 |
|------|------|
| `drogon-create-controller` | 生成控制器（Simple/Http/WebSocket） |
| `drogon-gen-cmake` | 生成 CMakeLists.txt |
| `drogon-gen-csp-view` | 生成 CSP 视图模板 |
| `drogon-gen-db-config` | 生成数据库配置 |
| `drogon-gen-filter` | 生成 Filter 请求拦截器 |
| `drogon-gen-middleware` | 生成 Middleware 处理链 |
| `drogon-gen-orm-crud` | 生成 ORM CRUD 代码 |
| `drogon-gen-redis-config` | 生成 Redis 配置 |
| `drogon-gen-test` | 生成 DROGON_TEST 测试用例 |
| `drogon-setup-config` | 生成完整配置文件 |

### 自动化检测钩子（PostToolUse）

在 AI 编辑文件后自动扫描 drogon API 违规：

| 文件类型 | 检测项 |
|---------|--------|
| `.h/.cc/.cpp` | `FILTER_ADD`、`ADD_MIDDLEWARE`、`METHOD_LIST_ADD`、`createDbClient` |
| `.csp` | `{{ }}`、`<%raw%>`、`<%viewpath`、`@@key@@`、`<%extends`、`{% if %}` |
| `config.json/.yaml` | `"password"`、`"username"` |
| `test*.cc` | `done()`、`ASSERT_*`、`createDbClient` |

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
AI: [对照 CLAUDE.md A 组规则] 这个 handler 的提前返回路径没有调用 callback...
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
├── hooks/
│   ├── hooks.json
│   └── posttooluse.py
├── skills/
│   ├── drogon-create-controller/
│   ├── drogon-gen-cmake/
│   ├── drogon-gen-csp-view/
│   ├── drogon-gen-db-config/
│   ├── drogon-gen-filter/
│   ├── drogon-gen-middleware/
│   ├── drogon-gen-orm-crud/
│   ├── drogon-gen-redis-config/
│   ├── drogon-gen-test/
│   └── drogon-setup-config/
├── CLAUDE.md
├── LICENSE
└── README.md
```

## 许可

MIT — 详见 [LICENSE](LICENSE)。
