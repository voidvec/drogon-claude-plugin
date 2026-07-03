# drogon-gen-file-upload Implementation

## Input parsing

Extract from user input:
- `route`: upload route (required, e.g. `/upload`)
- `max_files`: allowed file count (default `1`)
- `save_dir`: destination dir (optional; default = `app().getUploadPath()`)
- `max_body_size`: body size cap string (optional, e.g. `"20M"`)

## Forbidden APIs

- Assuming `MultiPartParser::parse()` returns bool / throws — it returns **int, 0 = success** (MultiPart.h:175).
- Using client-controlled filename to build `saveAs()` path — path traversal risk. Use server-generated name or `getMd5()`.
- Forgetting `app().setClientMaxBodySize(bytes)` — default cap rejects large uploads (file_upload.cc:42).
- Treating `save("uploads")` == `save("./uploads")` — former becomes `getUploadPath()/uploads/`, latter is CWD `uploads/` (MultiPart.h:68-72).

## Key APIs (source-checked)

| API | Signature | Source |
|-----|-----------|--------|
| parse | `int MultiPartParser::parse(const HttpRequestPtr&)` 0=ok | MultiPart.h:175 |
| get files | `const std::vector<HttpFile>& getFiles()` | MultiPart.h:131 |
| save (default path) | `int HttpFile::save() const` → getUploadPath() | MultiPart.h:64 |
| save (subpath) | `int HttpFile::save(const std::string &path) const` | MultiPart.h:73 |
| save as | `int HttpFile::saveAs(const std::string &fileName) const` | MultiPart.h:81 |
| md5 | `std::string HttpFile::getMd5() const` | MultiPart.h:111 |
| body size | `app().setClientMaxBodySize(size_t)` | HttpAppFramework.h |
| upload path | `app().setUploadPath(const std::string&)` | HttpAppFramework.h |

## Path prefix semantics (MultiPart.h:68-80)

- `save(path)` / `saveAs(name)`: if path/name starts with `/`, `./`, `../`, or is `.`/`..` → treated as root/relative path; otherwise appended under `getUploadPath()`.

## Code template

```cpp
app().registerHandler("/upload",
    [](const HttpRequestPtr &req,
       std::function<void(const HttpResponsePtr &)> &&callback) {
        MultiPartParser parser;
        if (parser.parse(req) != 0 || parser.getFiles().size() != 1) {   // N.1 0=success, N.2 validate first
            auto resp = HttpResponse::newHttpResponse();
            resp->setStatusCode(k403Forbidden);
            resp->setBody("Must only be one file");
            callback(resp);
            return;
        }
        auto &file = parser.getFiles()[0];
        // N.6: don't trust client filename — save under server-generated name
        std::string safeName = file.getMd5() + std::string(file.getFileExtension());
        file.saveAs(safeName);
        auto resp = HttpResponse::newHttpResponse();
        resp->setBody("saved as " + safeName);
        callback(resp);
    },
    {Post});
```

### Startup chain reminder

```cpp
app().setClientMaxBodySize(20 * 1024 * 1024)   // N.5 required for large uploads
    .setUploadPath("./uploads")
    .addListener("0.0.0.0", 8080)
    .run();
```

## Key rules

1. `parse()` returns int; check `!= 0` for failure.
2. Validate count/size **before** saving.
3. Never trust client filename for the on-disk path — use md5 or server-generated name.
4. Always set `setClientMaxBodySize` in the startup chain.

## Error handling

- `route` empty: return error
- `max_files` not a positive integer: return error
