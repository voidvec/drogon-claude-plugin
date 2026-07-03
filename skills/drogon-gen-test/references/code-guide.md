# drogon-gen-test Implementation

## Input parsing

Extract from user input:
- `test_name`: Test name (required)
- `test_type`: Test type (`unit`/`integration`/`async_db`, default `unit`)
- `assertions`: Assertion description (e.g. `status=200, body contains "success"`)

## Forbidden APIs

- `done()` — **does not exist**, drogon has no async completion callback
- `ASSERT_*` — Google Test macros, not used by drogon
- `EXPECT_*` — Google Test macros, not used by drogon
- `app().createDbClient(...)` — deprecated, use `addDbClient(...)`

## Assertion macro quick reference

| Purpose | Non-fatal | Fatal | Die |
|---------|-----------|-------|-----|
| Expression true | `CHECK(expr)` | `REQUIRE(expr)` | `MANDATE(expr)` |
| Expect exception | `CHECK_THROWS(expr)` | `REQUIRE_THROWS(expr)` | `MANDATE_THROWS(expr)` |
| No exception | `CHECK_NOTHROW(expr)` | `REQUIRE_NOTHROW(expr)` | `MANDATE_NOTHROW(expr)` |
| Specific type | `CHECK_THROWS_AS(expr, T)` | `REQUIRE_THROWS_AS(expr, T)` | `MANDATE_THROWS_AS(expr, T)` |
| Unconditional fail | `FAIL(msg)` / `FAULT(msg)` | — | — |
| Compile-time | `STATIC_REQUIRE(expr)` | — | — |
| Nested sub-test | `SUBSECTION("name"){...}` / `SUBTEST("name"){...}` | — | — |
| Explicit success | `SUCCESS()` | — | — |

## 测试组织约定

- **目录约定**：测试用例放 `tests/` 目录（源文件用 `.cc`）。
- **CMake 扫描**：在 `CMakeLists.txt` 中 `include(ParseAndAddDrogonTests.cmake)` 后调用 `ParseAndAddDrogonTests(${PROJECT_NAME})`，该脚本递归扫描 `tests/` 下含 `DROGON_TEST` 宏的 `.cc` 文件并自动注册为单独的测试目标——**无需手写 `add_test`**。
- **自动注册**：每个 `DROGON_TEST(MyTest)` 宏生成一个 `DrObject` 子类，框架通过 `DrClassMap` 在静态初始化期自动登记，`drogon::test::run()` 时枚举执行。

## Code generation

### unit type

```cpp
#include <drogon/drogon_test.h>

DROGON_TEST(${test_name}) {
    // Arrange
    auto resp = drogon::HttpResponse::newHttpResponse();

    // Act
    resp->setStatusCode(drogon::k200OK);
    resp->setBody("{\"status\":\"ok\"}");

    // Assert
    CHECK(resp->getStatusCode() == drogon::k200OK);
    CHECK(resp->body() == "{\"status\":\"ok\"}");
}
```

### integration type

```cpp
#include <drogon/drogon_test.h>

DROGON_TEST(${test_name}) {
    auto loop = drogon::app().getLoop();
    loop->queueInLoop([]() {
        auto client = drogon::HttpClient::newHttpClient("http://127.0.0.1:8080");
        auto req = drogon::HttpRequest::newHttpRequest();
        req->setPath("/api/endpoint");

        client->sendRequest(req, [](drogon::ReqResult result,
                                     const drogon::HttpResponsePtr &resp) {
            REQUIRE(result == drogon::ReqResult::Ok);
            CHECK(resp->getStatusCode() == drogon::k200OK);
        });
    });
}
```

### async_db type

```cpp
#include <drogon/drogon_test.h>

DROGON_TEST(${test_name}) {
    auto loop = drogon::app().getLoop();
    loop->queueInLoop([]() {
        auto client = drogon::app().getDbClient();
        client->execSqlAsync(
            "SELECT 1 AS result",
            [](const drogon::orm::Result &r) {
                CHECK(r.size() == 1);
                CHECK(r[0]["result"].as<int>() == 1);
            },
            [](const drogon::orm::DrogonDbException &e) {
                FAIL("DB query failed: " + std::string(e.base().what()));
            });
    });
}
```

### Test main()

```cpp
int main(int argc, char *argv[]) {
    drogon::app().setLogLevel(trantor::Logger::kDebug);

    // For DB tests, configure before run():
    // drogon::app().addDbClient(
    //     drogon::orm::Sqlite3Config{.filename = ":memory:"});

    return drogon::test::run(argc, argv);
}
```

## Key rules

1. **Async tests use `queueInLoop` + assertions in callbacks**, not `done()` or `async/await`
2. **`CHECK` vs `REQUIRE`**: use `CHECK` for non-fatal (continues), `REQUIRE` for fatal (stops test)
3. **Database tests assert inside callbacks** (`execSqlAsync` success/failure callbacks)
4. **`addDbClient` is called in `main()`**, not inside test cases

## Error handling

- `test_name` is empty: return error message
- `test_type` is invalid: return error message listing valid types
- Generation fails: return error message
