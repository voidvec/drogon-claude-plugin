---
name: drogon-gen-stream
description: 需要流式处理大文件上传/GB级上传/流式下载/chunked 响应时，生成基于 RequestStream 与 newAsyncStreamResponse 的流式 handler 代码。
version: 0.2.0
---

# drogon-gen-stream

生成 drogon 流式请求与流式响应 handler 代码（大文件上传流式处理 + chunked 流式下载）。

## 使用场景

当上传体预估超过 10MB、达 GB 级或内存敏感，不能让 MultiPartParser 全量缓冲进内存时，或需要 chunked 流式响应/大文件下载时，使用此技能。普通小文件上传走 drogon-gen-file-upload。

## 输入参数

- `direction`: 方向，`upload`（流式上传）/ `download`（流式下载），二选一或都要
- `route`: 路由（如 `/stream_upload`）
- `size_hint`: 预估大小（如 `"2G"`，用于 setClientMaxBodySize 提示，可选）
- `multipart`: 上传是否为 multipart/form-data（默认 `true`）
- `save_dir`: 落盘目录（上传方向，默认 `./uploads`，可选）

## 输出

1. 上传方向：`RequestStreamPtr` 判空 + `newMultipartReader`/`newReader` 三回调 handler，流式落盘不占内存
2. 下载方向：`newAsyncStreamResponse`/`newStreamResponse` chunked 响应，分块发送
3. 启动链 `enableRequestStream` + `setClientMaxBodySize` 提示

## 示例

```
/drogon-gen-stream direction=upload route=/stream_upload size_hint=2G multipart=true
/drogon-gen-stream direction=download route=/stream_download
```

## 参考文件

详细实现指南见 `references/code-guide.md`（含 API 源码核对表、回调签名、背压策略、禁止模式清单、最小示例）。生成代码前先读取该文件。
