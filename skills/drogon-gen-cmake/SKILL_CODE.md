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

## 错误处理

- `project_name` 为空：返回错误消息
- `cxx_standard` 不是 `17` 或 `20`：返回错误消息
- 文件写入失败：返回错误消息