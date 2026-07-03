# drogon-gen-csp-view Implementation

## Input parsing

Extract from user input:
- `view_name`: View name (required)
- `layout`: Parent layout name (optional)
- `has_cpp_logic`: Whether C++ logic is needed (default `false`)
- `variables`: Template variable list (format: `name:type,name2:type2`)

## CSP syntax quick reference

| Syntax | Location | Meaning |
|--------|----------|---------|
| `<%c++ ... %>` | Anywhere | C++ code block |
| `@@` | Inside `<%c++ %>` only | HttpViewData reference；两种用法：`@@.get<T>("key")` 取值，`@@["key"]` 下标取 `std::any` |
| `$$` | Inside `<%c++ %>` only | Output stream |
| `[[ key ]]` | Outside `<%c++ %>` | Inline variable output |
| `{% key %}` | Anywhere | Alias for `[[ key ]]` |
| `<%layout name %>` | .csp file header | Parent layout |
| `<%view name %>` | Anywhere | Include a sub-view (传入 HttpViewData) |
| `<%inc #include "file" %>` | Anywhere | Insert code (C preprocessor-style include) |

## `drogon_ctl create view` 编译管线

CSP 视图的完整流程（用户须知晓）：
- **输入**：手写的 `.csp` 文件
- **输出**：`drogon_ctl create view <Name>.csp` 生成 `<Name>.h` + `<Name>.cc` 两个 C++ 源文件（编译进二进制，运行期不再解析 CSP）
- **参数**：`-o <dir>` 指定输出目录，`-n <namespace>` 指定命名空间
- viewName 在 `newHttpViewResponse("Name", data)` 中**不带 `.csp` 后缀**

## HttpViewData API 要点

- `insert(key, any)` / `operator[]` 写入；`get<T>(key)` 取值。
- `insertAsString(key, str)`：以字符串类型插入（区别于 `insert` 的 `std::any`）。
- **键名大小写敏感**：`data["UserId"]` 与 `data["userid"]` 是两个键，CSP 里 `[[ UserId ]]` 必须大小写完全匹配。
- `htmlTranslate(str)`：手动 HTML 转义（CSP 无自动转义，见下）。

## Handler 纪律

- **禁止在 handler 里手工拼接 HTML 字符串返回**：HTML 页面必须通过 CSP 视图（`newHttpViewResponse`）渲染。手工拼 HTML 易出 XSS 且无法复用布局。

## Forbidden syntax

- `@@key@@` — wrapping syntax does not exist, `@@` is a standalone token
- `{{ key }}` — Jinja2/Mustache template engine syntax, not supported by drogon
- `{% if %}...{% endif %}` — block-level control flow tags, not supported (single-value `{% key %}` is valid for variable interpolation only)
- `<%viewpath %>` — does not exist, use `<%view name %>`
- `<%raw%>...<%/raw%>` — does not exist
- `.csp` file extensions in `viewName` parameters — do not include `.csp` suffix

## Code generation

### Basic template (no C++ logic)

```html
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>[[ title ]]</title>
</head>
<body>
    <h1>[[ title ]]</h1>
    <p>[[ content ]]</p>
</body>
</html>
```

### Template with layout (child)

```html
<%layout ${layout} %>
<h1>[[ title ]]</h1>
<div>[[ content ]]</div>
```

### Parent layout template

When a layout is specified, also generate the parent layout `.csp` file. The child's rendered content is stored under the empty-string key `""` (see `create_view.cc:551`: `data[""] = std::move(str)`). The parent uses `[[ ]]` (a single space between brackets, which the parser trims to the empty string) to output the child content.

```html
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>[[ title ]]</title>
</head>
<body>
    <header>
        <h1>Site Header</h1>
    </header>
    <main>
        [[ ]]  <!-- empty key = child content -->
    </main>
    <footer>
        <hr>
        <p>&copy; 2026</p>
    </footer>
</body>
</html>
```

> **Critical**: `[[ ]]` must be exactly a single space between brackets. `[[##]]`, `[[content]]` or any other key will never match — the parser reads the space, trims it, and looks up the empty key `""` in HttpViewData, which only the layout mechanism populates.

> **⚠️ `[[ ]]` only belongs in parent layouts**, never in child templates. In a child template (a `.csp` file that declares `<%layout ... %>`), `[[ ]]` would look up `viewData[""]` from user code, which is usually empty. Child templates must use named keys like `[[ users ]]` or `<%c++ %>` loops to render their data.

### Template with C++ logic

```html
<!DOCTYPE html>
<html>
<%c++
    auto items = @@.get<std::vector<std::string>>("items");
%>
<head>
    <meta charset="UTF-8">
    <title>[[ title ]]</title>
</head>
<body>
    <h1>[[ title ]]</h1>
    <ul>
    <%c++
        for (const auto &item : items) {
            $$ << "<li>" << item << "</li>";
        }
    %>
    </ul>
</body>
</html>
```

### Controller rendering code

```cpp
HttpViewData data;
data["title"] = "My Page";
data["content"] = "Hello, World";
auto resp = HttpResponse::newHttpViewResponse("${view_name}", data);
callback(resp);
```

## HTML escaping reminder

CSP does **not** auto-escape HTML. User input should be manually escaped with `HttpViewData::htmlTranslate()`:

```html
<%c++
    auto safe = HttpViewData::htmlTranslate(@@.get<std::string>("userInput"));
    $$ << safe;
%>
```

## Error handling

- `view_name` is empty: return error message
- `variables` format is invalid: return error message
- Generation fails: return error message
