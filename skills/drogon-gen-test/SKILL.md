---
name: drogon-gen-test
description: 生成 drogon DROGON_TEST 测试用例，支持单元测试、集成测试、异步数据库测试等类型。
version: 0.1.0
---

# drogon-gen-test

生成 drogon DROGON_TEST 测试用例。

## 使用场景

当需要为 drogon 应用编写测试用例时，使用此技能快速生成符合 drogon 测试框架约定的测试代码。

## 输入参数

- `test_name`: Test name
- `test_type`: Test type (`unit`, `integration`, `async_db`)
- `assertions`: Assertion description (e.g. `status=200, body contains "success"`)

## 输出

1. `DROGON_TEST(TestName)` 测试用例
2. 合适的断言（`CHECK` vs `REQUIRE` vs `MANDATE`）
3. 异步测试模式（若需要）
4. 测试数据准备和清理代码

## 示例

```
/drogon-gen-test test_name=UserLogin test_type=integration assertions="status=200, body contains token"
```

生成用户登录集成测试。

## 参考文件
详细实现指南见 `references/code-guide.md`（含参数验证、代码模板、禁止模式清单）。生成代码前先读取该文件。
