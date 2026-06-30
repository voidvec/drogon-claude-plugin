# drogon-gen-csp-view

生成 drogon CSP 视图模板（`.csp` 文件）及对应的控制器渲染代码。

## When to use

When a page with HTML rendering is needed, use this skill to quickly generate view templates that follow drogon CSP conventions.

## Input parameters

- `view_name`: View name (e.g. `UserList`)
- `layout`: Parent layout name (optional, e.g. `main`)
- `has_cpp_logic`: Whether C++ logic is needed (`true`/`false`, default `false`)
- `variables`: Template variable list (e.g. `name:string, age:int`)

## Output

1. `.csp` template file (using correct `@@`, `$$`, `[[ ]]`, `<%c++ %>` syntax)
2. Controller view rendering code snippet
3. HttpViewData population code

## Example

```
/drogon-gen-csp-view view_name=UserList layout=main variables=title:string,users:vector
```

Generates a user list view template with main layout.
