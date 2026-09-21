# drogon-setup-config Implementation

## 输入解析

从用户输入中提取：
- `format`: 配置文件格式（默认 `json`）
- `listen_address`: 监听地址（默认 `127.0.0.1`）
- `listen_port`: 监听端口（必需）
- `enable_https`: 是否启用 SSL（默认 `false`）
- `enable_session`: 是否启用会话（默认 `true`）
- `number_of_threads`: 事件循环线程数（默认 `0`）
- `log_level`: 日志级别（默认 `INFO`）

## JSON 模板

```json
{
  "listeners": [
    {
      "address": "${listen_address}",
      "port": ${listen_port},
      "https": ${enable_https}
    }
  ],
  "app": {
    "number_of_threads": ${number_of_threads},
    "enable_session": ${enable_session},
    "session_timeout": 1200,
    "log": {
      "log_path": "./logs",
      "logfile_size": 104857600,
      "log_level": "${log_level}"
    }
  }
}
```

## YAML 模板

```yaml
listeners:
  - address: ${listen_address}
    port: ${listen_port}
    https: ${enable_https}
app:
  number_of_threads: ${number_of_threads}
  enable_session: ${enable_session}
  session_timeout: 1200
  log:
    log_path: ./logs
    logfile_size: 104857600
    log_level: ${log_level}
```

## 文件生成

1. 根据 `format` 选择模板（JSON 或 YAML）
2. 将模板中的变量替换为实际值
3. 生成 `config.json` 或 `config.yaml` 文件到项目根目录

## 配置加载语义与纪律

### 路径解析（`app().loadConfigFile`）
1. 相对路径：相对于当前工作目录（CWD）解析
2. 绝对路径：直接使用
3. 路径分隔符：drogon 内部用 `drogon::utils::toNativePath()` 自动转平台原生格式（Windows `\`，Unix `/`）

### 加载失败处理（源码 `lib/src/ConfigLoader.cc`）
- 文件不存在 / 无权限 / 解析失败均抛 `std::runtime_error`。
- **必须**在 `loadConfigFile()` 外层 try/catch，**禁止**假设配置一定加载成功。

### 格式纪律
- 按扩展名自动判断格式（`.json` / `.yaml` / `.yml`）。
- **禁止**在 YAML 里用 JSON 语法（双引号键），也**禁止**在 JSON 里用 YAML 语法（无引号键、注释）。

### 多环境配置
推荐环境变量覆盖（`loadConfigFile` 前设 `setenv()`），或多文件（`config.dev.json` / `config.prod.json`）在 `main` 中选择。**禁止**建议手改配置（版本控制风险），**禁止**硬编码环境特定配置（IP、端口）。

## 配置项语义（高频陷阱）

- `listeners[].https` 必须是**布尔** `true/false`（不是字符串）；HTTPS 监听需同时提供 `cert` / `key`（`ConfigLoader.cc:651-652`）。顶层另有全局 `ssl` 块（`ConfigLoader.cc:705`）。
- `client_max_body_size`：请求体上限，值为**字符串**如 `"1M"`/`"20M"`（`ConfigLoader.cc:467`），文件上传场景必须调大；等价代码 API 为 `app().setClientMaxBodySize(bytes)`。
- 连接数上限键是 `max_connections` / `max_connections_per_ip`（**不是** `max_connection_num`）。
- **禁止**错误键名：`threads`、`num_threads`、`enable_sessions`（正确是 `enable_session`）、`max_connection_num`。
- **禁止**把布尔值写成字符串。

## HTTPS 监听完整字段（源码核对，v1.9.13）

`listeners[]` 数组内每个对象的全部字段（源码 `ConfigLoader.cc:642-674` `loadListeners`，以 `config.example.json:15-38` 为准）：

| 字段 | 类型 | 默认值 | 源码 | 说明 |
|------|------|--------|------|------|
| `address` | string | `"0.0.0.0"` | `ConfigLoader.cc:649` | 监听 IP |
| `port` | 整数 | `0` | `ConfigLoader.cc:650` | 监听端口 |
| `https` | **布尔** | `false` | `ConfigLoader.cc:651` | 是否启用 TLS |
| `cert` | string | `""` | `ConfigLoader.cc:652` | 证书路径，**为空时回落全局 `ssl` 块** |
| `key` | string | `""` | `ConfigLoader.cc:653` | 私钥路径，为空时回落全局 `ssl` 块 |
| `use_old_tls` | 布尔 | `false` | `ConfigLoader.cc:654` | 允许 TLS1.0/1.1 |
| `ssl_conf` | 数组 | 无 | `ConfigLoader.cc:656-669` | 1 或 2 元素元组，传给 `SSL_CONF_cmd` |

顶层全局 `ssl` 块（源码 `ConfigLoader.cc:676-699` `loadSSL`，`config.example.json:5-14`）：
- `cert`（`:681`）、`key`（`:680`）：全局证书/私钥，供 `cert`/`key` 为空的 HTTPS listener 使用
- `conf`：1-2 元素元组数组（如 `["Options", "-SessionTicket"]`）

完整示例（HTTP + HTTPS 双监听）：

```json
{
    "ssl": {
        "cert": "certs/server.crt",
        "key": "certs/server.key"
    },
    "listeners": [
        { "address": "0.0.0.0", "port": 80, "https": false },
        {
            "address": "0.0.0.0",
            "port": 443,
            "https": true,
            "cert": "",
            "key": "",
            "use_old_tls": false,
            "ssl_conf": [ ["MinProtocol", "TLSv1.2"] ]
        }
    ]
}
```

纪律：
- `ssl_conf` / `conf` 元素必须是 1 或 2 元素数组，否则 `LOG_FATAL` + `abort`（`ConfigLoader.cc:660-665`）。
- **禁止**只写 `"https": true` 而不提供任何证书（listener 或全局二选一），启动时报错。
- 等价代码 API：`app().addListener(addr, port, useSSL, cert, key, useOldTLS, sslConfCmds)`（`ConfigLoader.cc:671-672` 调用形式）。

## 静态文件服务配置（源码核对，v1.9.13）

全部位于 `app` 段（源码 `ConfigLoader.cc:246-530` `loadApp`，字段名以 `config.example.json:116-187` 为准）：

| 字段 | 类型 | 默认值 | 源码 | 说明 |
|------|------|--------|------|------|
| `document_root` | string | `"./"` | `ConfigLoader.cc:281-284` | 静态文件根目录 |
| `home_page` | string | `"index.html"` | `ConfigLoader.cc:499` | `/` 对应的首页文件 |
| `use_implicit_page` | 布尔 | `true` | `ConfigLoader.cc:500-501` | 目录访问隐式补隐式页 |
| `implicit_page` | string | `"index.html"` | `ConfigLoader.cc:502-503` | 隐式页文件名 |
| `upload_path` | string | `"uploads"` | `ConfigLoader.cc:306-307` | 上传保存目录（相对 `document_root`） |
| `static_file_headers` | 数组 | 无 | `ConfigLoader.cc:286-304` | 静态文件附加响应头 |
| `static_files_cache_time` | 整数 | `5` | `ConfigLoader.cc:446-447` | 缓存秒数：`0`=永久缓存，**负值=不缓存** |
| `file_types` | 数组 | 内置列表 | `ConfigLoader.cc:309-319` | 允许下载的扩展名 |
| `mime` | 对象 | 无 | `ConfigLoader.cc:504-523` | 扩展名→MIME 扩展映射 |
| `locations` | 数组 | 无 | `ConfigLoader.cc:321-373` | 按 URI 前缀的静态文件位置 |
| `gzip_static` | 布尔 | `true` | `ConfigLoader.cc:463-464` | 优先发同名 `.gz` 文件 |
| `br_static` | 布尔 | `true` | `ConfigLoader.cc:465-466` | 优先发同名 `.br` 文件 |
| `use_sendfile` | 布尔 | `true` | `ConfigLoader.cc:440-441` | 用 `sendfile()` 发送静态文件 |

**注意**：**`enable_static_file_cache` 不是真实字段**——`config.example.json` 与 `ConfigLoader.cc` 中均不存在此键；缓存开关由 `static_files_cache_time` 的值控制（`0` 永久 / 负值禁用）。**禁止**生成该键名。

`static_file_headers` 完整示例（必须是 `name`/`value` 对象数组，否则抛 `std::runtime_error`，`ConfigLoader.cc:299-303`）：

```json
"app": {
    "document_root": "./public",
    "upload_path": "uploads",
    "static_files_cache_time": 3600,
    "static_file_headers": [
        { "name": "Cache-Control", "value": "public, max-age=3600" },
        { "name": "X-Content-Type-Options", "value": "nosniff" }
    ]
}
```

## custom_config 与 getCustomConfig

`config.json` **顶层**的 `custom_config` 段（`config.example.json:348-358`）留给业务自定义配置；ConfigLoader 不解析其内容，应用内经 `app().getCustomConfig()` 读取——实现即 `jsonConfig_["custom_config"]`（`HttpAppFrameworkImpl.h:56`）。

config.json 写法：

```json
{
    "custom_config": {
        "pay": {
            "base_path": "/api/pay",
            "metrics_base_url": "http://127.0.0.1:5566/metrics/base"
        },
        "credentials": [
            { "user": "drogon", "password": "dr0g0n" }
        ]
    }
}
```

读取完整模式（jsoncpp 遍历 + 类型断言）：

```cpp
const Json::Value &custom = app().getCustomConfig();

// 1. 标量读取：get(key, default) 提供 fallback，禁止裸 asString()（键缺失时 jsoncpp 默认构造值）
std::string basePath = custom["pay"].get("base_path", "/api/pay").asString();

// 2. 存在性 + 类型守卫再读（键可能整段缺失）
if (custom.isMember("pay") && custom["pay"].isObject())
{
    const Json::Value &pay = custom["pay"];
    if (pay.isMember("metrics_base_url"))
        url = pay["metrics_base_url"].asString();
}

// 3. 遍历对象键（getMemberNames 返回 vector<string>）
for (const auto &key : custom.getMemberNames())
{
    LOG_DEBUG << "custom_config key: " << key;
}

// 4. 遍历数组 + 类型断言
for (const auto &cred : custom["credentials"])
{
    if (cred.isObject())
        LOG_DEBUG << "user=" << cred.get("user", "").asString();
}
```

纪律：
- `getCustomConfig()` 返回 `const Json::Value&`（引用单例内 JSON），**禁止**长期持有后跨线程改写。
- 敏感值（密码、密钥）**禁止**明文写进 `custom_config` 提交版本库——用占位符 + 运行时环境变量替换（见下节）。

## loadConfigJson 编程式加载（.env / 占位符替换模式）

`app().loadConfigJson(const Json::Value &)` / `loadConfigJson(Json::Value &&)`（`HttpAppFramework.h:469`/`:479`）接受与配置文件同构的 JSON 对象；两者均 `noexcept(false)`——**同样会抛异常，必须 try/catch**。

pay-plugin（`examples/pay-server/main.cc`）验证过的完整模式：先 `.env` 进环境，再读 `config.json`、替换 `__env_var:VAR__` 占位符，最后 `loadConfigJson(std::move(json))`：

```cpp
#include <drogon/drogon.h>
#include <json/json.h>
#include <fstream>

int main()
{
    // 1. 加载 .env 到进程环境（KEY=VALUE 逐行 setenv）
    ConfigLoader::loadEnvFile(".env");

    // 2. 手工解析 config.json（jsoncpp，勿用已废弃的 Json::Reader）
    std::ifstream configFile("./config.json");
    if (!configFile.is_open())
    {
        LOG_FATAL << "Failed to open config.json";
        return 1;
    }
    Json::Value config;
    Json::CharReaderBuilder builder;
    std::string errors;
    if (!Json::parseFromStream(builder, configFile, &config, &errors))
    {
        LOG_FATAL << "Failed to parse config.json: " << errors;
        return 1;
    }

    // 3. 递归替换占位符：
    //    "__env_var:PAY_DB_PASSWORD__" -> getenv("PAY_DB_PASSWORD")
    //    "__env_var__"                  -> 用键名作为环境变量名
    Json::Value processedConfig = ConfigLoader::loadConfig(config);

    // 4. 注入框架（右值重载，避免整棵 JSON 拷贝）
    drogon::app().loadConfigJson(std::move(processedConfig));
    drogon::app().run();
}
```

config.json 中占位符写法：

```json
"db_clients": [
    {
        "name": "default",
        "rdbms": "postgresql",
        "host": "127.0.0.1",
        "dbname": "pay_db",
        "user": "pay",
        "passwd": "__env_var:PAY_DB_PASSWORD__"
    }
]
```

纪律：
- **必须**在 `app().run()` 之前调用 `loadConfigJson`（与 `loadConfigFile` 相同时机）。
- `loadConfigJson` 与 `loadConfigFile` 二选一，**禁止**先后都调（后一次覆盖前一次的部分状态，行为不可预期）。
- **禁止**把明文密码写进 config.json 后提交版本库——.env 不入库（CI 里由环境变量注入）。

## 多环境配置实践（authforge 模式）

authforge（`apps/server/config/`）验证过的多环境布局，在前述「多环境配置」基础上的完整实践：

```
apps/server/config/
├── config.json        # 开发基线（所有环境的公共部分）
├── config.dev.json    # 本地开发（localhost DB/Redis、宽松 CORS）
├── config.ci.json     # CI（内存存储、禁用持久化）
├── config.bench.json  # 压测（高并发、连接池调优）
└── config.prod.json   # 生产（启用全部安全特性、HTTPS、严格 CORS）
```

- **加载方式**：部署期选择，不做运行时 if/else——Dockerfile 里 `COPY config.prod.json ./config.json`（authforge `deploy/docker/Dockerfile:84`），程序永远只找 `./config.json`；main 里只做候选路径回退（`./config.json` → `../config.json`，authforge `main.cc:162-166`）。
- **敏感值**：prod 配置中写占位哨兵（如 `"passwd": "OVERRIDE_VIA_FULLA_DB_PASSWORD"`），运行时由环境变量覆盖（`FULLA_DB_PASSWORD` 等）；**禁止**在 prod JSON 里留真实凭据。
- **环境差异示例**（dev → prod）：DB host `127.0.0.1` → `postgres`；`number_of_threads` `1` → `0`（CPU 核数）；`session_same_site` `"Null"` → `"Lax"`；`number_of_connections`、`timeout`、`auto_batch`、`statement_timeout` 均按环境调高。
- **同步纪律**：修改 `config.json` 基线时**必须**同步到 `config.dev.json` / `config.ci.json` / `config.prod.json`（否则环境间漂移，authforge AGENTS.md 明文规定）。
- **禁止**用 `config.prod.json` 做开发调试（prod 配置启用了 Hodor 限流/严格 CORS，本地行为不一致）。

## 错误处理

- `format` 不是 `json` 或 `yaml`：返回错误消息
- `listen_port` 不是有效的端口号：返回错误消息
- `log_level` 不是有效的日志级别：返回错误消息
- 文件写入失败：返回错误消息
