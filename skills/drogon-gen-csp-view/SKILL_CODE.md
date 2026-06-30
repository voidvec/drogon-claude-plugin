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
| `@@` | Inside `<%c++ %>` only | HttpViewData reference |
| `$$` | Inside `<%c++ %>` only | Output stream |
| `[[ key ]]` | Outside `<%c++ %>` | Inline variable output |
| `{% key %}` | Anywhere | Alias for `[[ key ]]` |
| `<%layout name %>` | .csp file header | Parent layout |

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
