# drogon-gen-session-auth Implementation

## Input parsing

Extract from user input:
- `route`: route path (required, e.g. `/login`, `/logout`)
- `auth_mode`: `login` / `logout` / `check` (required)
- `user_field`: session key for user id (optional, default `userId`)

## Forbidden APIs

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

## Key rules

1. Use `getOptional<T>` / `modify<T>` — never `operator[]`.
2. Call `changeSessionIdToClient()` after successful login.
3. Finish all session writes **before** `callback(resp)`.
4. `enableSession` must be in the startup chain.

## Error handling

- `route` empty: return error
- `auth_mode` invalid: list valid modes
