# drogon-gen-test Implementation

## Input parsing

Extract from user input:
- `test_name`: Test name (required)
- `test_type`: Test type (`unit`/`integration`/`async_db`, default `unit`)
- `assertions`: Assertion description (e.g. `status=200, body contains "success"`)

## 禁止模式清单

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

## 自定义 test main 模式（pay-plugin 实战，源码核对）

### DROGON_TEST_MAIN 的真相

`lib/inc/drogon/drogon_test.h`（739 行）里**没有** `DROGON_TEST_MAIN` 这个宏——定义它不会展开出任何 main。pay-plugin（`tests/main.cc:1`）与 drogon 官方示例（`examples/redis_cache/test/test_main.cc:1`）文件开头的 `#define DROGON_TEST_MAIN` 是不被消费的残留写法。结论：
- 测试 main **必须手写**；
- 生成代码时**不要**依赖（也不要生成）`#define DROGON_TEST_MAIN` 产生任何行为——它只是历史装饰。

`test::run` 真实签名（`drogon_test.h:383`）：

```cpp
namespace drogon { namespace test {
DROGON_EXPORT int run(int argc, char **argv);   // 返回值直接作为进程退出码
} }
```

### 手写 main 骨架（跑完整 app 的集成测试）

需要加载配置/起真实监听时，用 drogon 官方模式（`examples/redis_cache/test/test_main.cc`，pay-plugin `tests/main.cc:56-74` 同构）：把 `app().run()` 放到工作线程，主线程等待事件循环就绪后跑测试，最后优雅退出：

```cpp
#include <drogon/drogon_test.h>
#include <drogon/drogon.h>
#include <future>
#include <thread>

int main(int argc, char **argv)
{
    // ---- 前置准备区：test::run 之前做完 ----
    // (1) 加载配置（含环境变量占位符替换）
    // (2) 改写监听端口，避免与 dev server 冲突（见下 PAY_TEST_PORT 模式）
    // drogon::app().loadConfigJson(std::move(processedConfig));

    std::promise<void> p1;
    std::future<void> f1 = p1.get_future();

    // Start the main loop on another thread
    std::thread thr([&]() {
        app().getLoop()->queueInLoop([&p1]() { p1.set_value(); });  // loop 就绪信号
        app().run();
    });

    f1.get();                                // 只在事件循环真正启动后继续
    int status = test::run(argc, argv);      // 主线程跑全部 DROGON_TEST

    app().getLoop()->queueInLoop([]() { app().quit(); });  // 优雅退出
    thr.join();
    return status;
}
```

### PAY_TEST_PORT 端口隔离模式（pay-plugin `tests/main.cc:26-46` + `TestConfigHelper.h:31-42`）

config.json 常是宿主示例的直拷（端口 5566）；测试二进制与本地 dev server 同端口时，drogon 的 `reuse_port` 会让两个进程**随机互相劫持请求**。测试 main 载入配置后**必须**改写端口：

```cpp
inline int testPort()
{
    if (const char *env = std::getenv("PAY_TEST_PORT"))
    {
        const int port = std::atoi(env);
        if (port > 0 && port < 65536)
            return port;
    }
    return 5567;   // 默认测试端口，避开 dev server 的 5566
}

// loadConfigJson 之前，遍历改写所有 listener：
for (auto &listener : processedConfig["listeners"])
{
    listener["port"] = testPort();
}
```

**连带纪律**：`custom_config` 里凡是指向"本进程自己"的 URL（如 `metrics_base_url`）也要同步改写成测试端口——否则测试会静默读到 dev server 的数据（pay-plugin `tests/main.cc:34-46` 记录的实测坑）。

### 防 ctest 挂死：future 只在 ready 后 get

drogon 的 `CHECK` 失败**不会中止**测试——`CHECK(fut.wait_for(5s) == ready)` 失败后紧跟的 `fut.get()` 会无超时永久阻塞，挂死整个 ctest。用守卫函数把"等待"变成可失败的断言（pay-plugin `TestConfigHelper.h:116-163`）：

```cpp
template <typename T, typename Rep, typename Period>
inline bool waitForFutureReady(
    std::future<T> &fut,
    const std::chrono::duration<Rep, Period> &timeout)
{
    return fut.wait_for(timeout) == std::future_status::ready;
}

// 用法：先 REQUIRE 就绪，再 get
REQUIRE(waitForFutureReady(fut, std::chrono::seconds(5)));
auto value = fut.get();   // 只有已知 ready 才会执行到这里
```

## CMake 接线（pay-plugin `tests/CMakeLists.txt` 模式）

```cmake
cmake_minimum_required(VERSION 3.21)
project(MyAppTests CXX)
set(CMAKE_CXX_STANDARD 17)

add_executable(${PROJECT_NAME}
    main.cc
    unit/FooTest.cc
    integration/BarTest.cc
)
# 测试复用宿主代码：链接宿主的 OBJECT/STATIC 库目标
# （pay-plugin 链接 pay_core pay_host_core，tests/CMakeLists.txt:46）
target_link_libraries(${PROJECT_NAME} PRIVATE my_core my_host_core Drogon::Drogon)

# config.json / .env 必须出现在测试二进制旁（运行时 CWD 解析）
add_custom_command(
    TARGET ${PROJECT_NAME} POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
            "${CMAKE_CURRENT_SOURCE_DIR}/../app/config.json"
            "$<TARGET_FILE_DIR:${PROJECT_NAME}>/config.json"
)
# .env 不入库：仅在存在时复制（CI 干净 checkout 没有 .env，不能让构建失败）
if(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/../app/.env")
    add_custom_command(
        TARGET ${PROJECT_NAME} POST_BUILD
        COMMAND ${CMAKE_COMMAND} -E copy_if_different
                "${CMAKE_CURRENT_SOURCE_DIR}/../app/.env"
                "$<TARGET_FILE_DIR:${PROJECT_NAME}>/.env"
    )
endif()

if(MSVC)
    target_compile_options(${PROJECT_NAME} PRIVATE
        /bigobj   # 大量模板实例化（drogon handler/测试宏）超出 MSVC 段数上限
        /utf-8)   # 与库目标同源码编码契约
endif()

# 单进程跑全部 DROGON_TEST；退出码原样传给 CTest。
# WORKING_DIRECTORY 钉在二进制目录，./config.json ./.env 才能解析。
add_test(NAME MyAppTests COMMAND ${PROJECT_NAME}
         WORKING_DIRECTORY $<TARGET_FILE_DIR:${PROJECT_NAME}>)
```

与「CMake 扫描」节的 `ParseAndAddDrogonTests` 二选一：
- `ParseAndAddDrogonTests(target)`：每个 `DROGON_TEST` 一个 ctest 条目（`-r Name` 单跑），失败定位细，但每条目起一次完整进程（重复加载配置/建连接）。
- 单 `add_test` 全跑（pay-plugin 模式，`tests/CMakeLists.txt:89-97`）：一个进程顺序跑全部用例，启动开销一次付清；隔离需求靠端口/DB 名解决（见下节）。

## 并行/串行注意（端口与数据库隔离）

- **端口冲突**：
  - 测试监听端口**必须**与 dev server、与同时跑的其他测试二进制错开（PAY_TEST_PORT 环境变量可覆盖，默认取专用端口）；`reuse_port` 开启时同端口进程会互相劫持请求，症状是"随机失败"而非"启动失败"，极难排查。
  - 集成测试内 `HttpClient::newHttpClient("http://127.0.0.1:<port>")` 的 port 取同一个测试端口常量，**禁止**把 dev 端口硬编码进用例。
- **数据库隔离**：
  - 测试**必须**连独立数据库（独立 `dbname`，或 sqlite `:memory:`），**禁止**指向 dev/prod 库——测试数据会污染真实数据。多环境配置里用 `config.ci.json` 单独声明测试库（authforge 实践：CI 配置用内存存储/禁用持久化）。
  - 需要清理状态时优先**事务回滚**（每用例开事务、断言后 rollback），次选 TRUNCATE 重置脚本；重置脚本**禁止**进生产迁移版本链（pay-plugin 把 `sql/000_*.sql` 测试重置助手放在版本链外，部署器自动跳过）。
  - ctest 并行（`ctest -j`）时同库用例会互相踩：要么库按 worker 隔离（库名带序号），要么该套测试声明为串行（ctest 资源/标签约束）。
- **配置联动**：改监听端口时同步检查 `custom_config` 内的自身 URL（见 PAY_TEST_PORT 节）。

## Key rules

1. **Async tests use `queueInLoop` + assertions in callbacks**, not `done()` or `async/await`
2. **`CHECK` vs `REQUIRE`**: use `CHECK` for non-fatal (continues), `REQUIRE` for fatal (stops test)
3. **Database tests assert inside callbacks** (`execSqlAsync` success/failure callbacks)
4. **`addDbClient` is called in `main()`**, not inside test cases
5. 测试 main 手写（drogon 无 `DROGON_TEST_MAIN` 宏），集成测试用「工作线程 `app().run()` + `test::run` + `queueInLoop(quit)`」骨架。
6. 测试端口与 dev server 隔离（PAY_TEST_PORT 模式），`custom_config` 里的自身 URL 一并改写。
7. future 等待先 `REQUIRE(waitForFutureReady(...))` 再 `.get()`，**禁止**裸 `get()`（ctest 挂死根因）。
8. 测试连独立 DB/事务回滚；CMake POST_BUILD 复制 config.json/.env（.env 条件复制）；MSVC 加 `/bigobj /utf-8`。

## Error handling

- `test_name` is empty: return error message
- `test_type` is invalid: return error message listing valid types
- Generation fails: return error message
