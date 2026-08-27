# drogon-claude-plugin v0.2.0 升级迭代实施计划

> 本文档规划了 drogon-claude-plugin 升级至 v0.2.0 的迭代实施步骤、排期和验收用例。本实施计划基于 [PRD/upgrade_review.md](file:///D:/work/development/Repos/drogon-claude-plugin/PRD/upgrade_review.md) 的评审意见制定。

---

## 1. 实施步骤与排期计划 (Implementation Plan)

为降低升级对现有规则的影响，建议采用迭代开发模式，具体排期如下：

### 阶段一：规则层 (CLAUDE.md) 与 钩子层 (posttooluse.py) 升级 [优先级：高 (P0)]
1.  **修改 [CLAUDE.md](file:///D:/work/development/Repos/drogon-claude-plugin/CLAUDE.md)**：
    *   在现有 A–L 组末尾，追加新增的 M–V 组规则，并融入 [upgrade_review.md](file:///D:/work/development/Repos/drogon-claude-plugin/PRD/upgrade_review.md) 中的补充规范（协程传值、Advice 回调规范、RequestStream 正确 API）。
    *   修订 A.6、B、C.2、D.1、K.3、E.4 等现有条目，完成双向引用与语义补正。
2.  **修改 [posttooluse.py](file:///D:/work/development/Repos/drogon-claude-plugin/hooks/posttooluse.py) —— 修复 v0.1.0 遗留缺陷**：
    *   **修复回调正则冲突**：修改 `CPP_VIOLATIONS` 中针对 `HttpResponsePtr` 异步回调的正则定义，兼容 `cb`、`callback` 甚至 `callbackPtr` 等写法，并支持换行/折行情况，消除由于缩写或换行引起的误报。
    *   **优化忽略大小写策略**：为规则字典引入 per-rule 的大小写控制。对于大小写敏感的 C++ 标识符（如 `done()` 误报检测、`createDbClient`），采用精确匹配；对于其他纯文本或配置项关键字保持忽略大小写。
    *   **追加 v0.2.0 新匹配项**：增加协程、中间件、HttpClient 死锁和配置格式相关的正则匹配规则。
3.  **升级配置文件与基础文档**：
    *   修改项目版本（如 `plugin.json` 中的 `version` 字段）。
    *   修改 [README.md](file:///D:/work/development/Repos/drogon-claude-plugin/README.md) 中关于技能数和钩子数的统计信息。

### 阶段二：新增 8 个技能的创建与验证 [优先级：中 (P1)]
1.  **创建以下技能子目录**，每个目录包含 `SKILL.md` 与 `references/code-guide.md`：
    *   [drogon-gen-session-auth](file:///D:/work/development/Repos/drogon-claude-plugin/skills/drogon-gen-session-auth)
    *   [drogon-gen-file-upload](file:///D:/work/development/Repos/drogon-claude-plugin/skills/drogon-gen-file-upload)
    *   [drogon-gen-advice](file:///D:/work/development/Repos/drogon-claude-plugin/skills/drogon-gen-advice)
    *   [drogon-gen-coroutine-handler](file:///D:/work/development/Repos/drogon-claude-plugin/skills/drogon-gen-coroutine-handler)
    *   [drogon-gen-http-client](file:///D:/work/development/Repos/drogon-claude-plugin/skills/drogon-gen-http-client)
    *   [drogon-gen-rate-limiter](file:///D:/work/development/Repos/drogon-claude-plugin/skills/drogon-gen-rate-limiter)
    *   [drogon-gen-monitoring](file:///D:/work/development/Repos/drogon-claude-plugin/skills/drogon-gen-monitoring)
    *   [drogon-gen-lambda-handler](file:///D:/work/development/Repos/drogon-claude-plugin/skills/drogon-gen-lambda-handler)
2.  **编写模板代码**：确保生成的模板全面符合 CLAUDE.md 新增的 M-V 组安全规范。

---

## 2. 关键验证用例与验收指标

为了保证升级后插件的稳定性和误报率在合理范围，需要对以下用例进行测试验证：

1.  **钩子误报测试**：
    *   验证 `re.IGNORECASE` 优化后，正常编写的 C++ 变量（如 `int isDone = 0;` 或 `void myDone()`）是否不会误触发 `done()`（TEST.1 规则）的告警。
    *   验证回调写为 `std::function<void(const HttpResponsePtr &)> &&cb` 时，钩子是否正常通过，不误报回调变量丢失。
2.  **协程与 Client 死锁扫描验证**：
    *   输入包含 `client->sendRequest(...)` 且无 `callback` 的同步调用，确认钩子能成功发出 Q.2 警告。
    *   输入包含 `Task<void>` 且有 `co_await` 但无 `try/catch` 的协程，确认能成功发出 P.2 警告。
3.  **流式上传 API 签名验证**：
    *   如果在 handler 中直接调用 `req->setStreamReader(...)`，钩子能检测到这一无法编译的错误，并给出使用 `drogon::internal::createRequestStream` 的警示。
4.  **技能调用演示验证**：
    *   通过测试脚本或 AI 模拟调用新技能（如 `/drogon-gen-coroutine-handler`），验证生成的代码是否自动使用了按值传递的 `HttpRequestPtr`。
