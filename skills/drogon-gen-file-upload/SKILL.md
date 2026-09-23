---
name: drogon-gen-file-upload
description: 需要处理文件上传（multipart 解析、类型与大小校验、落盘、路径穿越防护）时生成 drogon handler。
license: MIT
---

# drogon-gen-file-upload

生成基于 `MultiPartParser` 的文件上传 handler 代码。

## 使用场景

当需要接收 multipart/form-data 文件上传时，使用此技能生成符合 N 组纪律的代码（解析返回值、路径前缀语义、大小校验、路径穿越防护）。

## 输入参数

- `route`: 上传路由（如 `/upload`）
- `max_files`: 允许的文件数（默认 `1`）
- `save_dir`: 落盘目录（可选；默认走 `getUploadPath()`）
- `max_body_size`: 请求体上限字符串（如 `"20M"`，可选）

## 输出

1. `MultiPartParser` 解析 handler（正确判断返回值 0=成功）
2. 文件数量/大小校验
3. 落盘调用（`save()` 或服务端重命名 `saveAs`）
4. 启动链 `setClientMaxBodySize` + `setUploadPath` 提示

## 示例

```
/drogon-gen-file-upload route=/upload max_files=1 max_body_size=20M
```

## 参考文件
详细实现指南见 `references/code-guide.md`（含参数验证、代码模板、禁止模式清单）。生成代码前先读取该文件。
