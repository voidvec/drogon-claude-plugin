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
| batch_insert | 线程池 + `execSqlSync` | 批量插入（遵循 G.5 规则） |

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
// 提示用户：批量操作需遵循 G.5 规则，使用线程池 + runInLoop
// 生成简化的线程池实现（不含复杂生命周期管理）
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