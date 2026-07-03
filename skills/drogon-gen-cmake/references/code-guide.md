# drogon-gen-cmake Implementation

## 输入解析

从用户输入中提取：
- `project_name`: 项目名称（必需）
- `enable_orm`: 是否启用 ORM（默认 `false`）
- `enable_redis`: 是否启用 Redis（默认 `false`）
- `enable_websocket`: 是否启用 WebSocket（默认 `false`）
- `cxx_standard`: C++ 标准（默认 `20`）
- `use_coroutine`: 是否启用协程（默认 `false`）

## CMakeLists.txt 模板

```cmake
cmake_minimum_required(VERSION 3.15)
project(${project_name} CXX)

set(CMAKE_CXX_STANDARD ${cxx_standard})
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(drogon REQUIRED)

add_executable(${project_name} src/main.cc)
target_link_libraries(${project_name} PRIVATE drogon::drogon)

if(${enable_orm})
    target_link_libraries(${project_name} PRIVATE drogon::orm_lib)
endif()

if(${enable_redis})
    # ⚠️ Redis 库名称需验证：当前 drogon 版本可能未导出独立的 Redis 库目标
    # 实施前需检查 build/CMakeFiles/DrogonConfig.cmake 中的库名定义
    # 若不存在，Redis 客户端可能已包含在 drogon::drogon 中
    # target_link_libraries(${project_name} PRIVATE drogon::redis_client)  # 待验证
endif()

if(${enable_websocket})
    # WebSocket 支持已包含在 drogon::drogon 中
    # 无需额外链接
endif()

if(${use_coroutine})
    target_compile_definitions(${project_name} PRIVATE USE_COROUTINE)
endif()
```

## 文件生成

1. 将模板中的 `${project_name}`、`${cxx_standard}`、`${enable_orm}` 等变量替换为实际值
2. 生成 `CMakeLists.txt` 文件到项目根目录

## 构建纪律（禁止项）

- **依赖发现**：用 `find_package(drogon REQUIRED)` + `target_link_libraries(... drogon::drogon)`。**禁止**手动 `include_directories()`（头文件路径经 INTERFACE_INCLUDE_DIRECTORIES 自动传递），**禁止**链接 `libdrogon.a`（硬编码路径不可移植）。
- **ORM 集成**：用 ORM 时显式 `target_link_libraries(... drogon::drogon drogon::orm_lib)`。**禁止**假设 `drogon::drogon` 已含 ORM（可能编译时禁用），**禁止**链接 `libdrogon_orm.a`。
- **Conan 安装**：通过 Conan 安装时用 `conan_basic_setup()` 生成的 `drogon_CONAN_TARGETS`；手动编译时检查 `BUILD_ORM` 等选项。**禁止**硬编码 drogon 安装路径（如 `/usr/local/include/drogon`），**禁止**假设特定安装方式。
- **插件/过滤器编译**：用户写的 `HttpPlugin` / `HttpFilter` 需链接 `drogon::drogon`，头文件用 `#include <drogon/HttpController.h>` 形式。**禁止**遗漏 `drogon::drogon` 依赖，**禁止**误用 `target_include_directories()`（头文件已由 `drogon::drogon` 传递）。

## 错误处理

- `project_name` 为空：返回错误消息
- `cxx_standard` 不是 `17` 或 `20`：返回错误消息
- 文件写入失败：返回错误消息