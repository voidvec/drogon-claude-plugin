# drogon-gen-session-auth Implementation

## Input parsing

Extract from user input:
- `route`: route path (required, e.g. `/login`, `/logout`)
- `auth_mode`: `login` / `logout` / `check` (required)
- `user_field`: session key for user id (optional, default `userId`)

## 禁止模式清单

- `session->operator[](key)` — returns `std::any&`, needs `any_cast`, error-prone. Use `getOptional<T>()` or `modify<T>()`. (Session.h)
- Calling `req->session()` without `app().enableSession(...)` first — undefined.
- Writing session **after** `callback(resp)` — cookie won't be set on current response.
- Storing large blobs (file bytes, big JSON) in session — session is in-memory (`CacheMap`, SessionManager.cc:50).

## Key APIs (source-checked)

| API | Signature | Source |
|-----|-----------|--------|
| enable session | `app().enableSession(size_t timeout=0)` | HttpAppFramework.h |
| get session | `req->session()` → `SessionPtr` | HttpRequest.h |
| typed get | `session->getOptional<T>(key)` → `std::optional<T>` | Session.h |
| typed modify | `session->modify<T>(key, [](T&){})` | Session.h:107 |
| insert (no overwrite) | `session->insert(key, value)` | Session.h:155 |
| erase | `session->erase(key)` | Session.h:178 |
| anti-fixation | `session->changeSessionIdToClient()` | Session.h:220 |

Underlying map is `std::map<std::string, std::any>` (Session.h:34, **not** unordered_map).

## Code templates

### login

```cpp
app().registerHandler("/login",
    [](const HttpRequestPtr &req,
       std::function<void(const HttpResponsePtr &)> &&callback) {
        auto user = req->getParameter("user");
        auto passwd = req->getParameter("passwd");
        if (checkCredentials(user, passwd)) {
            req->session()->insert("userId", userId);          // M.3 typed insert
            req->session()->changeSessionIdToClient();          // M.4 anti-fixation
            auto resp = HttpResponse::newHttpResponse();
            resp->setBody("ok");
            callback(resp);                                     // session written before callback
        } else {
            auto resp = HttpResponse::newHttpResponse();
            resp->setStatusCode(k401Unauthorized);
            callback(resp);
        }
    },
    {Post});
```

### logout

```cpp
app().registerHandler("/logout",
    [](const HttpRequestPtr &req,
       std::function<void(const HttpResponsePtr &)> &&callback) {
        req->session()->erase("userId");
        auto resp = HttpResponse::newHttpResponse();
        resp->setBody("logged out");
        callback(resp);
    },
    {Post});
```

### check (gate)

```cpp
app().registerHandler("/profile",
    [](const HttpRequestPtr &req,
       std::function<void(const HttpResponsePtr &)> &&callback) {
        auto loggedIn = req->session()->getOptional<bool>("loggedIn").value_or(false);
        if (!loggedIn) {
            auto resp = HttpResponse::newHttpResponse();
            resp->setStatusCode(k401Unauthorized);
            callback(resp);
            return;
        }
        auto resp = HttpResponse::newHttpResponse();
        resp->setBody("profile");
        callback(resp);
    },
    {Get});
```

### Startup chain reminder

```cpp
app().enableSession(1200)   // M.1 — required before any req->session() works
    .addListener("0.0.0.0", 8080)
    .run();
```

## Cookie 安全（v1.9.13 源码核对）

### Cookie 构造与 addCookie 重载

`Cookie` 构造签名是 `Cookie(std::string key, std::string value)`（`Cookie.h:39-42`，还有 `Cookie() = default`）。`HttpResponse::addCookie` 有三个重载（`HttpResponse.h:272-277`）：

```cpp
virtual void addCookie(const std::string &key, const std::string &value);  // :272
virtual void addCookie(const Cookie &cookie) = 0;                          // :276
virtual void addCookie(Cookie &&cookie) = 0;                               // :277
```

**禁止手工拼 Set-Cookie 字符串**（`resp->addHeader("Set-Cookie", "k=v; Path=/; ...")`）：
- 值里的 `;`、`,`、空格、非 ASCII 字节不会按 RFC 6265 转义，产生格式错误的 cookie；
- 多属性拼接顺序/大小写易错，`Cookie::cookieString()`（`Cookie.h:174`，实现 `Cookie.cc`）已处理各属性的空格/分号序列化。
- 同一响应要发多个 cookie 时，**必须**分别 `addCookie(Cookie)`，**禁止**拼接成一个 header。
- 两参 `addCookie(key, value)` 只适合无属性的临时 cookie；带安全属性的登录态 cookie **必须**用 `Cookie` 对象三参形式。

### 属性设置器与默认值（源码核对）

| 方法 | 签名 | 默认值（成员初始化） | Source |
|------|------|---------------------|--------|
| setHttpOnly | `void setHttpOnly(bool only)` | **`httpOnly_{true}` — 默认即 HttpOnly** | Cookie.h:66, :418 |
| setSecure | `void setSecure(bool secure)` | `secure_{false}` | Cookie.h:74, :419 |
| setSameSite | `void setSameSite(SameSite sameSite)` | `sameSite_{SameSite::kNull}` | Cookie.h:154, :426 |
| setPartitioned | `void setPartitioned(bool partitioned)` | `partitioned_{false}` | Cookie.h:162, :420 |
| setMaxAge | `void setMaxAge(int value)` | `maxAge_{}`（nullopt，不输出 Max-Age） | Cookie.h:146, :425 |
| setExpiresDate | `void setExpiresDate(const trantor::Date &date)` | `expiresDate_` = int64 最大值（不过期） | Cookie.h:58, :417 |
| setPath | `void setPath(const std::string &)` / `void setPath(std::string &&)` | 空 | Cookie.h:98/:106 |
| setDomain | `void setDomain(const std::string &)` / `void setDomain(std::string &&)` | 空 | Cookie.h:82/:90 |

注意：过期方法名是 **`setExpiresDate`**（接 `trantor::Date`），没有 `setExpires`。

### SameSite 枚举与 Secure 联动（源码行为）

```cpp
enum class SameSite { kNull, kLax, kStrict, kNone };   // Cookie.h:45-51
```

三条源码级联动，生成代码时直接依赖：
1. **`SameSite=None` 序列化时自动追加 `Secure`**（`Cookie.cc:60-64`，注释原意 "Cookies with SameSite=None must now also specify the Secure"）——现代浏览器拒绝不带 Secure 的 None。
2. **`setPartitioned(true)` 自动 `setSecure(true)`**（`Cookie.h:162-169`，CHIPS 分区 cookie 必须 Secure）。
3. `Secure` 属性输出条件：`secure_ && sameSite_ != kNone`，或 `partitioned_`（`Cookie.cc:72-74`）。
4. 字符串转枚举用 `Cookie::convertString2SameSite("Lax")`（大小写不敏感，`Cookie.h:376-393`）——`config.json` 的 `app.session_same_site` 就走它（`"Null"`/`"Lax"`/`"Strict"`/`"None"`，`ConfigLoader.cc:270-274`）。

纪律：
- 公网登录态 cookie **必须** `setSecure(true)`（仅 HTTPS 发送）+ `setSameSite(kLax)`（防 CSRF 的默认平衡）；跨站 iframe 场景才用 `kNone`（自动带 Secure）。
- `setHttpOnly(false)` 是**收紧为放宽**的操作——只有明确需要 JS 读 cookie（如前端自读非敏感标识）才关，登录态**禁止**关。
- `kStrict` 会断开从外部链接跳入的登录态携带，一般仅超敏感后台使用。

### 登录态 cookie 完整模板（Secure + HttpOnly + SameSite=Lax + MaxAge）

```cpp
#include <drogon/Cookie.h>
#include <drogon/HttpResponse.h>

// 登录成功后（session 写入、changeSessionIdToClient 之后，callback 之前）：
drogon::Cookie cookie("remember_token", token);
cookie.setHttpOnly(true);                  // 默认即 true，显式写出表意
cookie.setSecure(true);                    // 仅 HTTPS 发送
cookie.setSameSite(drogon::Cookie::SameSite::kLax);
cookie.setMaxAge(7 * 24 * 3600);           // 7 天
cookie.setPath("/");
// cookie.setDomain("example.com");        // 仅跨子域共享时设置
resp->addCookie(std::move(cookie));        // 右值重载，避免拷贝

// 登出/失效：同 key、MaxAge=0（立即过期）+ 空/旧值
drogon::Cookie kill("remember_token", "");
kill.setPath("/");                          // Path 必须与签发时一致才能覆盖
kill.setMaxAge(0);
resp->addCookie(std::move(kill));
```

补充：
- session cookie 本身的属性不手写——由启动链 `app().enableSession(timeout, sameSite, cookieKey, maxAge)`（`HttpAppFramework.h`；配置键 `app.session_same_site`/`session_cookie_key`/`session_max_age`，`ConfigLoader.cc:266-276`）控制。
- cookie 值**禁止**放用户可控的原始输入（含 `\r\n`/`;` 的值经 cookieString 会产生 header 注入面）；需要放就先编码（base64/urlencode）。

## Key rules

1. Use `getOptional<T>` / `modify<T>` — never `operator[]`.
2. Call `changeSessionIdToClient()` after successful login.
3. Finish all session writes **before** `callback(resp)`.
4. `enableSession` must be in the startup chain.
5. Set-Cookie 一律走 `addCookie(Cookie)`，**禁止**手工拼 Set-Cookie 字符串。
6. 登录态 cookie 模板：`Secure + HttpOnly + SameSite=Lax + MaxAge`；`SameSite::kNone` 自动带 Secure（源码行为），`setPartitioned(true)` 自动带 Secure。

## Error handling

- `route` empty: return error
- `auth_mode` invalid: list valid modes
