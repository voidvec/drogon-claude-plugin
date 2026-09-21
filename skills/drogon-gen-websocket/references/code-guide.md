# drogon-gen-websocket Implementation

针对 drogon v1.9.13，全部宏/API 已对照源码核对（引用为 文件:行号）。

## 1. 参数验证

1. `path` 非空且以 `/` 开头；`scene` 必须是 `chat` / `push` / `duplex` 之一。
2. **WS 适用性判断**（先于写代码）：仅客户端拉取、无服务端主动推送 → 普通 HTTP 即可；单向推送、客户端从不上行 → 优先 SSE（drogon 用 chunked 流式响应实现）；双向实时（聊天/协同/行情）才用 WS。
3. `state=map` 时确认 `number_of_threads`：多事件循环下连接注册表必须加锁（见第 3 节）。

## 2. 控制器骨架（源码核对）

宏定义于 `lib/inc/drogon/WebSocketController.h:27-33`——是 `WS_PATH_LIST_BEGIN`/`WS_PATH_LIST_END`；**不存在** `WS_PATH_BEGIN`、`WS_LIST_END`、`WS_CONN_LIST_BEGIN`/`WS_CONN_END`（全库 grep 为空，禁止凭记忆编写）。

- `WS_PATH_ADD(path, ...)`：第 1 参 path，后续为握手请求的 HTTP 方法约束（如 `Get`）；**不加类名前缀**（内部直接 `app().registerWebSocketController(path, ...)`，与 `HttpController` 的 `METHOD_ADD` 相反）。
- 正则路由：`WS_ADD_PATH_VIA_REGEX(regExp, ...)`（同文件 :31）。

三个方法真实签名（`WebSocketController.h:45-55`）——注意消息参数是 `std::string &&`（右值，可 move），不是 `const std::string &`：

- `void handleNewConnection(const HttpRequestPtr &, const WebSocketConnectionPtr &)`
- `void handleNewMessage(const WebSocketConnectionPtr &, std::string &&, const WebSocketMessageType &)`
- `void handleConnectionClosed(const WebSocketConnectionPtr &)`

```cpp
#include <drogon/WebSocketController.h>
#include <drogon/PubSubService.h>
using namespace drogon;

class ChatWS : public drogon::WebSocketController<ChatWS>  // 第二模板参数 AutoCreation 默认 true（:71）
{
  public:
    void handleNewConnection(const HttpRequestPtr &, const WebSocketConnectionPtr &) override;
    void handleNewMessage(const WebSocketConnectionPtr &, std::string &&, const WebSocketMessageType &) override;
    void handleConnectionClosed(const WebSocketConnectionPtr &) override;
    WS_PATH_LIST_BEGIN
    WS_PATH_ADD("/chat", Get);       // 握手仅允许 GET；路径就是 /chat，无类名前缀
    WS_PATH_LIST_END
  private:
    PubSubService<std::string> rooms_;  // 线程安全（内部 shared_mutex）
};
```

注册方式：
- **自动注册（默认）**：`AutoCreation=true` 时静态 `registrator_` 在 main 前执行 `initPathRouting()`（`WebSocketController.h:113-126`），**禁止**再手动注册。
- **手动实例化**：仅构造带参数时用 `WebSocketController<T, false>` 并自建对象，宏路由仍生效；底层为 `app().registerWebSocketController(path, ctrlName, constraints)`（`HttpAppFramework.h:626-629`）。
- **禁止**手写 101 升级响应：`HttpResponse::newWebSocketResponse` 在 v1.9.13 **不存在**（HttpResponse.h 及全库核对）；握手由框架自动完成。

## 3. 连接管理

### per-连接状态（userId 绑定模式）

```cpp
struct WsSession { std::string userId; SubscriberID subId{0}; };

void ChatWS::handleNewConnection(const HttpRequestPtr &req, const WebSocketConnectionPtr &conn)
{
    std::string userId = req->getParameter("token");   // 握手是 HTTP：可取参数/头/Session 做鉴权
    conn->setContext(std::make_shared<WsSession>());   // WebSocketConnection.h:160-173
    conn->getContextRef<WsSession>().userId = std::move(userId);  // :193-197
}
```

- 三个 handler 都在**连接所属事件循环线程**上被调用，是修改该连接状态的唯一安全位置。
- `getContext<T>()` 返回 `shared_ptr<T>`，未 setContext 时为**空指针**（:181-185）；`getContextRef<T>()` 未设置时解引用**崩溃**——先 set 再 get。辅助：`hasContext()`（:200）/ `clearContext()`（:206）。

### 连接集合的线程安全（B 组纪律）

- `number_of_threads > 1` 时连接分散在不同循环：`std::unordered_map<userId, WebSocketConnectionPtr>` 这类跨连接注册表必须 `std::mutex` 保护，增删查全部走锁；更优是 `PubSubService<T>`（内部 `shared_mutex`，`PubSubService.h:144-160`），官方 `examples/websocket_server/WebSocketServer.cc` 即此写法。
- 公共 `WebSocketConnection` **不提供 `getLoop()`**（WebSocketConnection.h 全文核对；`getLoop()` 只在 `WebSocketClient.h:168`）——无法 `conn->getLoop()->runInLoop()` 派发。替代纪律：context 状态只在三个 handler 内改，跨连接共享结构加锁；跨线程发送见下。

### 广播模板（官方 PubSubService 模式）

```cpp
// handleNewConnection 里订阅（conn 按值捕获进 std::function）
auto &s = conn->getContextRef<WsSession>();
s.subId = rooms_.subscribe(roomName,
    [conn](const std::string &topic, const std::string &msg) {
        if (conn->connected()) conn->send(msg);   // 发送前检查，防向已断开连接写
    });
// 广播（任意线程）：rooms_.publish(roomName, message);
// handleConnectionClosed 里必须：rooms_.unsubscribe(roomName, s.subId);
```

- `conn->send` 跨线程安全：trantor `TcpConnection::send` 检测非本循环线程时 `queueInLoop` 派发（`trantor/net/inner/TcpConnectionImpl.cc:460-473`），官方示例依赖此行为。
- `publish` 在共享锁内遍历全部订阅者（`PubSubService.h:50-57`）：回调抛异常会中断本轮广播，广播 lambda 内自行 try/catch。

### 心跳 / Ping-Pong（源码核对：框架自动）

- **服务端无需手写 ping/pong**：默认每 30 秒自动发空 ping，收到 ping 自动回 pong（`WebSocketConnection.h:216-221` 注释；`WebSocketConnectionImpl.cc:442-445`）。
- 自定义：`conn->setPingMessage(msg, interval)`（:222-224，内部 `queueInLoop`，跨线程安全）；禁用：`conn->disablePing()`（:229）。控制帧（Ping/Pong/Close）载荷必须 ≤125 字节（RFC6455，断言于 `WebSocketConnectionImpl.cc:49-62`）。

## 4. 消息收发

send 重载（`WebSocketConnection.h:105-128`，type 默认 `Text`）：

- `send(const char *msg, uint64_t len, WebSocketMessageType type = Text)`——二进制/指定长度（:105-108）
- `send(std::string_view msg, WebSocketMessageType type = Text)`——文本（:116-118）
- `sendJson(const Json::Value &json, WebSocketMessageType type = Text)`——直接发 JSON（:126-128）

`WebSocketMessageType`（`HttpTypes.h:217-225`）：`Text`/`Binary`/`Ping`/`Pong`/`Close`/`Unknown`。分支模板：

```cpp
void ChatWS::handleNewMessage(const WebSocketConnectionPtr &conn, std::string &&message,
                              const WebSocketMessageType &type)
{
    switch (type)
    {
        case WebSocketMessageType::Text:    // 文本业务（JSON 在此解析）
        case WebSocketMessageType::Binary:  // 二进制业务
            rooms_.publish(room, std::move(message));  break;
        case WebSocketMessageType::Ping:    // 框架已自动回 Pong（cc:442-445），可不处理
        case WebSocketMessageType::Pong:    break;  // 心跳回执，通常忽略
        case WebSocketMessageType::Close:   break;  // 框架已 shutdown（cc:447-451）；清理放 handleConnectionClosed
        default: break;                     // Unknown 不递交（cc:452-455）
    }
}
```

- 大消息：消息**整条**驻留内存后才递交（parser 无应用层分片），且无消息大小上限配置（核对不存在 `setWebSocketMaxMessageSize` 类 API）；广播 N 连接 × 大消息会内存放大——大负载走应用层分片 + `Binary`。
- 主动关闭：`conn->shutdown(CloseCode, reason)`（优雅，发 Close 帧，:149-150；`CloseCode` 枚举 :27-86，如 `kNormalClosure`=1000、`kViolation`=1008）/ `conn->forceClose()`（:153）。

## 5. 禁止模式清单

1. **handler/连接回调里同步阻塞**（A.3/B.1）：三个 handler 在事件循环线程执行，同步 DB/`sleep`/长计算会拖死同循环所有连接；重活丢线程池或协程。
2. **裸存 `WebSocketConnectionPtr` 不处理生命周期**：`shared_ptr` 防悬空，但连接关闭后对象滞留内存、注册表无限增长；必须 `handleConnectionClosed` 里 unsubscribe/erase，发送前 `conn->connected()` 检查。
3. **跨线程直接改 conn 的 context**：公共 API 无 `getLoop()`，不能派发回归属循环；context 读写只在三个 handler（连接所属循环线程）内做，跨连接共享结构加锁。`conn->send` 是唯一可跨线程调用的操作（trantor 内部派发）。
4. **忘记处理 Close 清理**：Close 帧会以 `Close` 类型递交 `handleNewMessage`（cc:447-451 后 :458），且 `handleConnectionClosed` 必然触发——两处都不写清理才泄漏；PubSubService 订阅同理。
5. **使用不存在的 API**：`newWebSocketResponse`、`WS_CONN_LIST_BEGIN`、`conn->getLoop()`、`conn->setClosedCallBack()` 均不在 v1.9.13 公共接口（服务端关闭通知只有 `handleConnectionClosed`；`setCloseCallback` 是内部实现细节）。
6. **宏凭记忆写**：把 `WS_PATH_ADD` 当作有类名前缀、或混入 `HttpController` 的 `METHOD_LIST` 宏体系。

## 客户端（简述）

创建（`WebSocketClient.h:224-228`）：`newWebSocketClient(hostString, loop = nullptr, useOldTLS = false, validateCert = true)`——`hostString` 必须 `ws://`/`wss://` 前缀且**不含 path**（path 放请求对象，:203-221）；另有 `(ip, port, useSSL = false, loop = nullptr, ...)` 重载（:192-198）。

```cpp
auto wsPtr = WebSocketClient::newWebSocketClient("ws://127.0.0.1:8848");
auto req = HttpRequest::newHttpRequest();  req->setPath("/chat");   // path 在请求对象上（:203-221）
wsPtr->setMessageHandler([](std::string &&msg, const WebSocketClientPtr &,
                            const WebSocketMessageType &) { /* 分支同服务端 */ });  // :73-76
wsPtr->setConnectionClosedHandler([](const WebSocketClientPtr &) {});             // :86-87
wsPtr->connectToServer(req, [](ReqResult r, const HttpResponsePtr &,
                               const WebSocketClientPtr &wsPtr) {                 // :90-91
    if (r != ReqResult::Ok) { wsPtr->stop(); return; }   // 必查 Ok（HttpTypes.h:205-215）
    wsPtr->getConnection()->setPingMessage("", 2s);
    wsPtr->getConnection()->send("hello!");
});
app().run();  // loop=nullptr 复用 app 主循环（官方 examples/websocket_client 模式）
```

何时独立事件循环：程序不跑 `app().run()`（纯客户端线程、嵌入其他框架）时，自建 `trantor::EventLoop` 传入 `loop` 参数（`getLoop()` 在 :168 可取回）；服务端进程内常驻客户端也建议独立 loop，避免与 IO 循环互相拖累。
