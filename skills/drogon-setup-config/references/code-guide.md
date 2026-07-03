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

## 错误处理

- `format` 不是 `json` 或 `yaml`：返回错误消息
- `listen_port` 不是有效的端口号：返回错误消息
- `log_level` 不是有效的日志级别：返回错误消息
- 文件写入失败：返回错误消息