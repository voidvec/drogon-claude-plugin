---
name: drogon-gen-websocket
description: 需要 WebSocket 服务端/推送/广播/连接管理时，生成 drogon WebSocketController 代码，含心跳与跨循环纪律。
license: MIT
---

# drogon-gen-websocket

生成 drogon WebSocket 长连接服务端代码（客户端简述）。

## 使用场景

当需要服务端主动推送、聊天室广播、双向实时通信（IM/行情/协同）或 per-连接状态管理时使用。宏与方法签名均对照 v1.9.13 源码核对；A/B 组纪律（不阻塞事件循环、跨循环共享状态加锁）在 WS 同样适用。

## 输入参数

- `scene`: 业务场景——`chat`（聊天室/房间）/ `push`（服务端推送）/ `duplex`（双向通信）
- `path`: WS 路由（如 `/chat`；`WS_PATH_ADD` 不加类名前缀）
- `broadcast`: 是否需要广播（默认 `false`；`true` 用 `PubSubService` 模板）
- `state`: 连接状态存储——`context`（默认，per-连接）/ `map`（userId→conn 注册表，需加锁）
- `client`: 是否附带客户端示例（默认 `false`）
- `heartbeat`: 心跳间隔（可选；框架默认 30 秒自动 ping，一般不改）

## 输出

1. `WebSocketController<T>` 完整骨架：`handleNewConnection`/`handleNewMessage`/`handleConnectionClosed` + `WS_PATH_LIST_BEGIN`/`WS_PATH_ADD`/`WS_PATH_LIST_END` 宏注册
2. 连接状态绑定（`setContext` 存 userId 等）与广播实现（`PubSubService` 或加锁连接表）
3. 消息类型分支（Text/Binary/Ping/Pong/Close）与心跳说明
4. 可选：`WebSocketClient::newWebSocketClient` 客户端最小示例

## 示例

```
/drogon-gen-websocket scene=chat path=/chat broadcast=true
/drogon-gen-websocket scene=push path=/ws state=map client=true
```

## 参考文件

详细实现指南见 `references/code-guide.md`（含参数验证、控制器骨架、连接管理/广播、消息收发、禁止模式清单）。生成代码前先读取该文件。
