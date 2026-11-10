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
| select | `findByPrimaryKey` / `findOne` / `findBy` / `findAll` / `count` | 单主键 / 单条 / 多条 / 全表 / 计数 |
| insert | `insert` | 插入操作 |
| update | `update` / `updateBy` | 按实体更新 / 按列+条件更新 |
| delete | `deleteBy` / `deleteByPrimaryKey` | 删除操作 |
| batch_insert | 线程池 + `execSqlSync` | 批量插入（见下"纪律"小节） |

以上方法名逐个对照过 `orm_lib/inc/drogon/orm/Mapper.h`（声明跨 270-775 行；434-532 只覆盖 `findAll`/`count`/`findOne`/`findBy`，别拿这段当全表）。同步版真实行号：`findByPrimaryKey` 270、`findAll` 434、`count` 459、`findOne` 492、`findBy` 523、`insert` 552、`update` 581、`updateBy` 616、`deleteBy` 737、`deleteByPrimaryKey` 765；每个都另有回调式重载（如 `findByPrimaryKey` 322、`findAll` 442、`findOne` 501、`findBy` 532）与 `*Future` 变体（`countFuture` 481、`insertFuture` 572、`updateFuture` 603、`updateFutureBy` 649）。**没有** `findByCriteria` 这个东西（全树 0 命中），别照其它 ORM 的习惯写。 <!-- fact-guard-waived:findByCriteria -->

以上签名同时存在于回调式（末参传 `SingleRowCallback` / `MultipleRowsCallback`）与协程式（`CoroMapper<T>`，返回 `MapperAwaiter`）。**`CoroMapper<T>` 的方法名与 `Mapper<T>` 完全一致**（`findByPrimaryKey` / `findOne` / `findBy` / `insert` / `update` / `updateBy` / `deleteBy` / `deleteByPrimaryKey`，见 `orm_lib/inc/drogon/orm/CoroMapper.h:81,296,357,410,465,503,642,672`），**没有** `findByCoro` 之类后缀；`*Coro` 后缀只出现在 `DbClient::execSqlCoro`（`DbClient.h:222`）。

## 纪律（硬性规则）

- **禁止在事件循环线程用 `execSqlSync`**：handler 中**必须**用 `Mapper<T>` / `CoroMapper<T>` 异步方法，同步 `client->execSqlSync()` 会阻塞事件循环线程，拖死同一循环上所有连接。**唯一例外**是 batch_insert：把重活交给独立线程池，在池内可用 `execSqlSync`，完成后用 `runInLoop` / `queueInLoop` 派回连接所属循环再 `callback`。
- **异步回调完整性**：`execSqlAsync` 必须提供成功 + 失败两个回调；失败回调必须 `callback(错误响应)`，确保响应被发送。
- **协程优先**：启用协程（`USE_COROUTINE`）时用 `CoroMapper<T>` 的 `co_await` 方法，需**显式构造** `CoroMapper<T> mapper(client)`。
- **事务纪律**：`newTransaction()` 返回的事务在析构时**自动提交**（`TransactionImpl::~TransactionImpl`，drogon 源码 `orm_lib/src/TransactionImpl.cc:37-88`；第 41 行 `if (!isCommitedOrRolledback_)` → 第 51-52 行无条件 `conn->execSql("commit", ...)`）；`Transaction::commit()` 被注释掉了（`orm_lib/inc/drogon/orm/DbClient.h:423`），只有 `rollback()` 是纯虚可用接口（`:422`）。
  - ⚠️ **抛异常不会自动回滚**。异常只是让 `shared_ptr<Transaction>` 析构，而析构走的就是上面那条 **commit** 路径——中途失败的批量写会把已执行的那部分**提交**进库。回滚只有一个办法：在 catch 里显式调 `trans->rollback()`（它内部 `runInLoop`，可在任意线程调用）。
  - `newTransaction()` 是**阻塞**封装：内部 `std::promise` + `future.get()` 等 `newTransactionAsync` 回调（`orm_lib/src/DbClientImpl.cc:326-343`），拿不到连接时抛 `TimeoutError`。**禁止在事件循环线程调用它**——那等于把这条 IO 循环钉死到超时。循环线程里请用 `newTransactionAsync`。

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
// 提示用户：批量操作必须在独立线程池执行（不得在事件循环线程阻塞）。
// ⚠️ `req->getLoop()` 编译不过 <!-- fact-guard-waived:req->getLoop -->：HttpRequest 的公共接口（lib/inc/drogon/HttpRequest.h）
//    没有任何 loop 访问器，只有框架内部的 lib/src/HttpRequestImpl.h:107 有。
//    公开可用的是 app().getLoop()（HttpAppFramework.h:158，主循环）与
//    app().getIOLoop(id)（:168，第 id 个 IO 循环）。
//    注意代价：queueInLoop 到主循环 ≠ 连接所属的 IO 循环；若要求严格在同一 IO 循环上
//    发响应，请改用全异步方案（newTransactionAsync + 链式 execSql），压根不要起线程。
//    另：getEventLoopOfCurrentThread() 是无循环线程上的 nullptr 来源，别在它返回的值上解引用
//    （trantor/net/EventLoop.h:116，头文件在 net/ 不是 utils/）。
std::thread([callback, items, loop = app().getLoop()]() {
    std::shared_ptr<orm::Transaction> trans;   // 提到 try 外，catch 里才拿得到它做 rollback
    try {
        auto client = app().getDbClient();
        trans = client->newTransaction();
        for (const auto &item : items) {
            trans->execSqlSync("INSERT INTO table (...) VALUES (...)", ...);
        }
        trans.reset();   // 显式结束事务：析构走 commit 路径（见上"事务纪律"）

        loop->queueInLoop([callback]() {
            auto resp = HttpResponse::newHttpResponse();
            resp->setBody("batch insert success");
            callback(resp);
        });
    } catch (const orm::DrogonDbException &e) {
        // ⚠️ 必须显式 rollback：析构只会 commit，不 rollback 就是半截提交。
        //    newTransaction() 自身也可能抛 TimeoutError（也是 DrogonDbException），
        //    所以这里要先判空。
        if (trans)
            trans->rollback();
        loop->queueInLoop([callback]() {
            auto resp = HttpResponse::newHttpResponse();
            resp->setStatusCode(k500InternalServerError);
            resp->setBody("batch insert error");
            callback(resp);
        });
    }
}).detach();
// 提示：handler 签名为 (const HttpRequestPtr &req, std::function<void(const HttpResponsePtr &)> &&callback)。
// 生产环境应使用更健壮的线程池库，确保线程池在应用退出时清理
```

## 禁止模式清单

- **禁止**在事件循环线程调用 `execSqlSync` 等同步 SQL 接口——会拖死同一循环上的所有连接。
- **禁止**只写成功回调、漏掉失败回调；失败回调里必须 `callback(错误响应)`。
- **禁止**在单个 handler 中多次调用 `callback`（事务回滚路径与成功路径都要检查）。
- **禁止**手动拼接 SQL 字符串；`Mapper<T>` 的 `findBy` / `findOne` / `deleteBy` / `updateBy` 接收 `Criteria` 并已参数化。
- **禁止**把事务拆成一串互不检查结果的独立异步调用——中途失败要回滚，且只回调一次。
- **禁止**协程版本混用回调式 API 后 `co_await` 非协程类型；协程式直接用 `CoroMapper<T>` 的同名方法（`co_await mapper.findBy(...)`），它返回 `MapperAwaiter`。

## 错误处理

- 参数无效：返回具体的参数错误消息
- 操作类型不兼容：返回错误消息
- 生成失败：返回错误消息