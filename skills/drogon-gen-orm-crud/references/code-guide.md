# drogon-gen-orm-crud Implementation

## 输入解析

从用户输入中提取：
- `db_type`: 数据库类型（必需）
- `table_name`: 表名（必需）
- `operation_type`: 操作类型（必需）
- `use_coroutine`: 是否使用协程（默认 `true`）

## 参数映射

| operation_type | Mapper 方法 | 说明 |
|---------------|-------------|------|
| select | `findByCriteria` / `findByPrimaryKey` | 查询操作 |
| insert | `insert` | 插入操作 |
| update | `update` | 更新操作 |
| delete | `deleteBy` | 删除操作 |
| batch_insert | 线程池 + `execSqlSync` | 批量插入（见下"纪律"小节） |

## 纪律（硬性规则）

- **禁止在事件循环线程用 `execSqlSync`**：handler 中**必须**用 `Mapper<T>` / `CoroMapper<T>` 异步方法，同步 `client->execSqlSync()` 会阻塞事件循环线程，拖死同一循环上所有连接。**唯一例外**是 batch_insert：把重活交给独立线程池，在池内可用 `execSqlSync`，完成后用 `runInLoop` / `queueInLoop` 派回连接所属循环再 `callback`。
- **异步回调完整性**：`execSqlAsync` 必须提供成功 + 失败两个回调；失败回调必须 `callback(错误响应)`，确保响应被发送。
- **协程优先**：启用协程（`USE_COROUTINE`）时用 `CoroMapper<T>` 的 `co_await` 方法，需**显式构造** `CoroMapper<T> mapper(client)`。
- **事务纪律**：`newTransaction()` 返回的事务在析构时**自动提交**；**禁止**手动调用 `Transaction::commit()`（该方法已注释/禁用）。需要回滚时用异常或显式 rollback：抛异常进 catch 即触发回滚，或在事务存活期间调用其 rollback 接口。batch_insert 模板即事务用法的参考实现。

## 代码生成

根据 `operation_type` 和 `use_coroutine` 生成不同的代码模板：

**select + 协程**：
```cpp
drogon::Task<HttpResponsePtr> Ctrl::get${Table}(const HttpRequestPtr &req,
                                                       std::function<void(const HttpResponsePtr &)> &&callback,
                                                       int id) {
    try {
        auto client = app().getDbClient();
        CoroMapper<${Table}> mapper(client);
        auto result = co_await mapper.findByPrimaryKey(id);
        auto resp = HttpResponse::newHttpResponse();
        resp->setBody(/* 序列化 result */);
        co_return resp;
    } catch (const orm::DrogonDbException &e) {
        LOG_ERROR << "DB error: " << e.base().what();
        co_return HttpResponse::newHttpResponse();
    }
}
```

**select + 回调**：
```cpp
void Ctrl::get${Table}(const HttpRequestPtr &req,
                      std::function<void(const HttpResponsePtr &)> &&callback,
                      int id) {
    auto client = app().getDbClient();
    Mapper<${Table}> mapper(client);
    mapper.findByPrimaryKey(
        id,
        [callback](const ${Table} &result) {
            auto resp = HttpResponse::newHttpResponse();
            resp->setBody(/* 序列化 result */);
            callback(resp);
        },
        [callback](const orm::DrogonDbException &e) {
            LOG_ERROR << "DB error: " << e.base().what();
            auto resp = HttpResponse::newHttpResponse();
            resp->setStatusCode(k500InternalServerError);
            resp->setBody("DB error");
            callback(resp);
        });
}
```

**batch_insert**：
```cpp
// 提示用户：批量操作必须在独立线程池执行（不得在事件循环线程阻塞），
// 完成后用 runInLoop/queueInLoop 派回连接所属循环再 callback。
std::thread([callback, items]() {
    try {
        auto client = app().getDbClient();
        auto trans = client->newTransaction();
        for (const auto &item : items) {
            trans->execSqlSync("INSERT INTO table (...) VALUES (...)", ...);
        }
        // 析构时自动提交
        
        trantor::EventLoop::getEventLoopOfCurrentThread()->queueInLoop([callback]() {
            auto resp = HttpResponse::newHttpResponse();
            resp->setBody("batch insert success");
            callback(resp);
        });
    } catch (const orm::DrogonDbException &e) {
        trantor::EventLoop::getEventLoopOfCurrentThread()->queueInLoop([callback]() {
            auto resp = HttpResponse::newHttpResponse();
            resp->setStatusCode(k500InternalServerError);
            resp->setBody("batch insert error");
            callback(resp);
        });
    }
}).detach();
// 提示：生产环境应使用更健壮的线程池库，确保线程池在应用退出时清理
```

## 错误处理

- 参数无效：返回具体的参数错误消息
- 操作类型不兼容：返回错误消息
- 生成失败：返回错误消息