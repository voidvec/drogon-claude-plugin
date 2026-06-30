---
name: drogon-setup-config
description: 生成 drogon 项目的配置文件（config.json 或 config.yaml），包含监听地址、SSL、会话、日志等配置。
version: 0.1.0
---

# drogon-setup-config

生成 drogon 项目的配置文件（`config.json` 或 `config.yaml`）。

## 使用场景

当创建一个新的 drogon 项目或需要更新配置文件时，使用此技能快速生成符合 drogon 约定的配置文件。

## 输入参数

- `format`: 配置文件格式（`json`/`yaml`，默认 `json`）
- `listen_address`: 监听地址（如 `0.0.0.0`，默认 `127.0.0.1`）
- `listen_port`: 监听端口（如 `8080`）
- `enable_https`: 是否启用 SSL（`true`/`false`，默认 `false`）
- `enable_session`: 是否启用会话（`true`/`false`，默认 `true`）
- `number_of_threads`: 事件循环线程数（`0` = CPU 硬件并发数）
- `log_level`: 日志级别（`DEBUG`/`INFO`/`WARN`/`ERROR`，默认 `INFO`）

## 输出

生成 `config.json` 或 `config.yaml` 文件。

## 示例

```
/drogon-setup-config listen_port=8080 enable_session=true log_level=DEBUG
```

生成 `config.json`，包含监听地址、端口、会话、日志等配置。
## 参考文件
详细实现指南见 `references/code-guide.md`（含参数验证、代码模板、禁止模式清单）。生成代码前先读取该文件。
