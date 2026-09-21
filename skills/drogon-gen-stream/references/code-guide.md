# drogon-gen-stream 实现指南

所有 API 均对照 drogon v1.9.13 源码核对，引用格式「文件:行号」，基准目录为 drogon 仓库根（lib/、trantor/、examples/）。

## 1. 参数验证

- 输入：`direction`（upload/download）、`route`、`size_hint`、`multipart`、`save_dir`；缺 `direction` 或 `route` 报错。满足任一条才走流式，否则改用 drogon-gen-file-upload（MultiPartParser 全量进内存）：body 预估 > 10MB 或 GB 级；内存敏感（多路并发上传）；需边收边处理（落盘/转存/哈希）。
- 流式上传前提：启动链调用 `app().enableRequestStream()`（HttpAppFramework.h:1637），否则拿不到流。
- Content-Length 预校验：框架解析头部后即用声明长度对照 `getClientMaxBodySize()`，超限直接 413，流式同样生效（HttpRequestParser.cc:267-272）；handler 内可用 `req->getRealContentLength()`（HttpRequest.h:190-195）提前拒绝超大上传。

## 2. 流式上传

### 2.1 拿到流对象

- 流式 handler 多一个 `RequestStreamPtr &&stream` 形参，由框架经 `internal::createRequestStream(req)` 注入（HttpBinder.h:354-359）。
- `internal::createRequestStream(req)`（RequestStream.h:47）在未开启 enableRequestStream 时返回 **nullptr**（RequestStream.cc:84-93），必须判空后再 `stream->setStreamReader(reader)`（RequestStream.h:40）。
- **`req->setStreamReader()` 不存在**：HttpRequest.h 没有任何流式接口（已通查无此声明），reader 只能挂在 RequestStreamPtr 上；直接调用 `req->setStreamReader(...)` 是编译错误。

### 2.2 三回调模型

`newReader(dataCb, finishCb)`（RequestStream.h:102-103）：dataCb 即 onStreamData，签名 `void(const char*, size_t)`（RequestStream.h:95）；finishCb 即 onStreamFinish，签名 `void(std::exception_ptr)`（RequestStream.h:96），恰好触发一次，ex 非空即失败。

`newMultipartReader(req, headerCb, dataCb, finishCb)`（RequestStream.h:110-114）：headerCb 签名 `void(MultipartHeader)`，每个 part 开始时触发（字段 name/filename/contentType，RequestStream.h:29-34）；dataCb 中 **length==0 表示当前文件结束**（MultipartStreamParser.cc:215）；finishCb 在 multipart 数据非法/不完整时收到 runtime_error 异常（RequestStream.cc:155-190）。

### 2.3 纪律

- dataCb/headerCb 运行在事件循环线程，禁止同步阻塞（fsync、长锁、sleep）。
- finishCb 的成功与异常两条路径都必须**恰好调用一次 callback**（A.1 纪律），范例 examples/async_stream/main.cc:65-92。
- 异常分支 catch `StreamError` 按 `code()` 区分：kBadRequest=解析失败（HttpServer.cc:198-199）、kConnectionBroken=客户端断连（HttpServer.cc:148-151），枚举定义 RequestStream.h:50-55。
- setStreamReader 仅首次调用生效（RequestStream.cc:44-49）；从不设置则析构时挂 NullReader 丢弃全部数据（RequestStream.cc:30-42）。

## 3. 流式下载 / chunked 响应

源码核对结论：HttpResponse.h 有且仅有两个流式构造 API；不存在 beginChunkedResponse、CallbackHandler 之类的其他入口。

### 3.1 newStreamResponse——同步拉取式（HttpResponse.h:526-531）

callback 签名 `std::size_t(char *buf, std::size_t len)`：向 buf 写至多 len 字节并返回实际字节数，**返回 0 即流结束**；结束后 drogon 再以 nullptr 调用一次供清理（HttpResponse.h:510-516）。keep-alive 且未设 Content-Length 时自动 Transfer-Encoding: chunked（HttpResponse.h:511-512）。适合按需从文件/管道读。

### 3.2 newAsyncStreamResponse——异步推送式（HttpResponse.h:547-549）

- callback 签名 `void(ResponseStreamPtr)`（unique_ptr，HttpResponse.h:114），拿到流对象后可在任意线程发送。
- `send(const std::string&) -> bool`：自动拼 chunked 帧（HttpResponse.h:87-97），返回 false=连接已关应停止；`close()` 发送终止块 `0\r\n\r\n` 并关闭（HttpResponse.h:99-108），发完应主动调用，勿依赖析构（HttpResponse.h:82-85）。
- 始终 chunked；慢客户端长传输传 disableKickoffTimeout=true（HttpResponse.h:543-545）。

### 3.3 头与内存

- Content-Type 用 `setContentTypeCode` / `setContentTypeCodeAndCustomString`（examples/async_stream/main.cc:44-45）；大文件应 `resp->setAllowCompression(false)`（HttpResponse.h:165），压缩会引入整段缓冲。

## 4. 背压与限速

源码无显式暂停/恢复背压 API：底层 AsyncStream::send 仅在连接关闭时返回 false，写满靠 TCP 拥塞控制间接反压（trantor/net/AsyncStream.h:36-41）。应用层策略：

- 分块 64KB-1MB：过小 chunked 帧开销大，过大占用事件循环时间片；每次 send 检查返回值，false 立即停止并 close()。
- 用 `runEvery`（trantor EventLoop.h:194）定时分批发送实现限速，结束用 `invalidateTimer`（EventLoop.h:222）取消；上传侧 dataCb 只做顺序写盘，勿每片 fsync。

## 5. 禁止模式清单

1. `req->setStreamReader(...)`：API 不存在，编译错误；只能 `stream->setStreamReader(reader)`。
2. finish 异常分支不 callback、或在 dataCb 中提前 callback：违反恰好一次纪律。
3. onStreamData/dataCb 里同步阻塞（fsync、sleep、长锁）：阻塞事件循环，拖垮同 loop 全部连接。
4. GB 级上传依赖 MultiPartParser：整个 body 缓冲进内存。
5. 流式下载 readFileSync 全量进内存再 setBody；忘记 `enableRequestStream()` 且不判空 stream（空指针崩溃）。

## 最小示例 A：multipart 流式上传落盘

```cpp
app().registerHandler(  // 流式上传：multipart 边收边落盘
    "/stream_upload",
    [](const HttpRequestPtr &req,
       RequestStreamPtr &&stream,  // 开启 enableRequestStream 后由框架注入
       std::function<void(const HttpResponsePtr &)> &&callback) {
        if (!stream)  // 未开启时 createRequestStream 返回 nullptr，必须判空
        {
            auto resp = HttpResponse::newHttpResponse();
            resp->setStatusCode(k400BadRequest);
            return callback(resp);  // 空流路径也恰好一次 callback
        }
        auto isFile = std::make_shared<bool>(false);
        auto file = std::make_shared<std::ofstream>(  // 服务端随机名，防路径穿越
            "uploads/" + drogon::utils::genRandomString(32),
            std::ios::trunc | std::ios::binary);
        stream->setStreamReader(RequestStreamReader::newMultipartReader(req,
            [isFile](MultipartHeader &&h) { *isFile = !h.filename.empty(); },
            [file, isFile](const char *data, size_t length) {
                if (length == 0)  // 当前文件结束（MultipartStreamParser.cc:215）
                {
                    file->flush();
                    file->close();
                    return;
                }
                if (*isFile)  // 跳过普通表单字段
                    file->write(data, length);  // 顺序写，禁止 fsync/阻塞事件循环
            },
            [file, cb = std::move(callback)](std::exception_ptr ex) {
                auto resp = HttpResponse::newHttpResponse();
                if (ex)  // 异常路径同样恰好一次 callback（A.1）
                {
                    try { std::rethrow_exception(std::move(ex)); }
                    catch (const StreamError &e) { LOG_ERROR << e.what(); }
                    resp->setStatusCode(k400BadRequest);
                }
                else { resp->setBody("saved\n"); }
                cb(resp);
            }));
    },
    {Post});
```

## 最小示例 B：流式文件下载（chunked、定时器限速）

```cpp
app().registerHandler(  // 流式下载：64KB 分块，不整读进内存
    "/stream_download",
    [](const HttpRequestPtr &,
       std::function<void(const HttpResponsePtr &)> &&callback) {
        auto resp = HttpResponse::newAsyncStreamResponse(
            [](ResponseStreamPtr ptr) {
                auto stream = std::shared_ptr<ResponseStream>(std::move(ptr));  // 转 shared 供定时器持有
                auto file = std::make_shared<std::ifstream>("uploads/big.bin", std::ios::binary);
                auto loop = app().getLoop();
                auto id = std::make_shared<trantor::EventLoop::TimerId>(0);
                *id = loop->runEvery(0.02, [stream, file, loop, id] {  // ≈3MB/s 限速
                    std::string chunk(64 * 1024, '\0');  // 64KB（建议 64KB-1MB）
                    file->read(chunk.data(), chunk.size());
                    chunk.resize(file->gcount());
                    if (chunk.empty() || !stream->send(chunk))  // EOF 或连接断开
                    {
                        stream->close();  // 发送 0\r\n\r\n 终止（HttpResponse.h:99）
                        loop->invalidateTimer(*id);  // EventLoop.h:222
                    }
                });
            },
            true);  // disableKickoffTimeout=true：长传输防踢（HttpResponse.h:543）
        resp->setContentTypeCode(CT_APPLICATION_OCTET_STREAM);
        resp->setAllowCompression(false);  // 禁压缩（HttpResponse.h:165）
        resp->addHeader("Content-Disposition", "attachment; filename=\"big.bin\"");
        callback(resp);
    });
```
