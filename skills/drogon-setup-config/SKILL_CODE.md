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

## 错误处理

- `format` 不是 `json` 或 `yaml`：返回错误消息
- `listen_port` 不是有效的端口号：返回错误消息
- `log_level` 不是有效的日志级别：返回错误消息
- 文件写入失败：返回错误消息