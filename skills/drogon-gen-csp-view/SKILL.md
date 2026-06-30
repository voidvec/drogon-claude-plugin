---
name: drogon-gen-csp-view
description: 生成 drogon CSP 视图模板（.csp 文件）及对应的控制器渲染代码，支持布局模板、C++ 逻辑嵌入、HttpViewData 填充。
version: 0.1.0
---

# drogon-gen-csp-view

生成 drogon CSP 视图模板（`.csp` 文件）及对应的控制器渲染代码。

## 使用场景

当需要 HTML 页面渲染时，使用此技能快速生成符合 drogon CSP 约定的视图模板。

## 输入参数

- `view_name`: View name (e.g. `UserList`)
- `layout`: Parent layout name (optional, e.g. `main`)
- `has_cpp_logic`: Whether C++ logic is needed (`true`/`false`, default `false`)
- `variables`: Template variable list (e.g. `name:string, age:int`)

## 输出

1. `.csp` 模板文件（使用正确的 `@@`、`$$`、`[[ ]]`、`<%c++ %>` 语法）
2. 控制器中渲染视图的代码片段
3. HttpViewData 填充代码

## 示例

```
/drogon-gen-csp-view view_name=UserList layout=main variables=title:string,users:vector
```

生成一个基于 main 布局的用户列表视图模板。
