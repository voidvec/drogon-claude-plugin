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
- **目标名大小写（v1.9.13 源码核对）**：drogon 实际安装导出的目标是 **`Drogon::Drogon`**（`add_library(Drogon::Drogon ALIAS ...)`，drogon `CMakeLists.txt:137`；`install(EXPORT DrogonTargets ... NAMESPACE Drogon::)`，`:825-826`）。`drogon_ctl create project` 生成的官方模板同样用 `Drogon::Drogon`（drogon 源码 `drogon_ctl/templates/cmake.csp:32`）。上方模板里的 `drogon::drogon` 为旧版历史写法，**生成新 CMakeLists 时应统一用 `Drogon::Drogon`**；二者不可混用（CMake 目标名大小写敏感）。

## drogon_create_views（CSP 视图编译接入，源码核对）

drogon 随包安装 `cmake/DrogonUtilities.cmake`（drogon 源码 `CMakeLists.txt:819-821` 将其装入 `INSTALL_DROGON_CMAKE_DIR`），`find_package(drogon)` 后即可用其中的唯一导出函数。

真实签名为**位置参数**（`DrogonUtilities.cmake:2-4` 头注释，实现 `:5-72`）：

```cmake
drogon_create_views(<target> <source_path> <output_path>
                    [TRUE use_path_as_namespace] [<prefixed namespace>])
```

- 第 1 参：目标（视图生成的 `.cc` 经 `target_sources(target PRIVATE ...)` 并入，`DrogonUtilities.cmake:71`）
- 第 2 参：`.csp` 文件所在目录（内部 `file(GLOB_RECURSE ... *.csp)`，`:11`）
- 第 3 参：输出目录（`.h/.cc` 生成到这里，先 `file(MAKE_DIRECTORY)`，`:10`）
- 第 4 参：传字面 `TRUE` 时启用 `--path-to-namespace`（路径转命名空间，`:31-33`）
- 第 5 参：命名空间前缀（`::` 会被替换为 `_` 拼进类名，`:34-40`）

```cmake
find_package(drogon REQUIRED)   # 已 include DrogonUtilities.cmake

add_executable(web src/main.cc)
drogon_create_views(web ${CMAKE_CURRENT_SOURCE_DIR}/views
                        ${CMAKE_CURRENT_BINARY_DIR}/generated_views TRUE)
```

注意：该函数**没有** `SOURCE_DIR`/`PATH` 之类的关键字参数（常见误写）；参数少于 3 个直接静默返回（`:6-9`）。

## DROGON_TEST 接入（源码核对）

- **`DROGON_TEST_MAIN` 宏不存在**：`lib/inc/drogon/drogon_test.h`（739 行）里没有该宏的定义；测试 main **必须手写**。drogon 官方示例（`examples/redis_cache/test/test_main.cc:1`）文件开头的 `#define DROGON_TEST_MAIN` 是不被任何头消费的残留写法，照抄无副作用但**不**会自动生成 main。main 骨架见 `drogon-gen-test` 技能（`test::run(argc, argv)` 声明于 `drogon_test.h:383`）。
- **`drogon_discover_tests` 不存在**：drogon 的 cmake 目录（`cmake/DrogonUtilities.cmake`、`cmake/Packages.cmake`）只导出 `drogon_create_views` 一个函数。批量注册测试用的是 `ParseAndAddDrogonTests.cmake:74` 的 `ParseAndAddDrogonTests(<target>)`（同样随 drogon 安装，drogon `CMakeLists.txt:820-821`），它扫描目标 SOURCES 里的 `DROGON_TEST(Name)` 并逐个 `add_test(NAME Name COMMAND target -r Name)`（`ParseAndAddDrogonTests.cmake:68`）。

```cmake
enable_testing()
add_executable(my_tests tests/main.cc tests/user_test.cc)
target_link_libraries(my_tests PRIVATE Drogon::Drogon)

include(ParseAndAddDrogonTests)        # 或指向 drogon 安装目录里的该文件
ParseAndAddDrogonTests(my_tests)
```

## drogon_ctl 生成模型的 CMake 接入（OBJECT library 隔离）

`drogon_ctl create model` 生成的 `.h/.cc` **禁止手改**，因此 pay-plugin/authforge 都把它们隔离到独立 OBJECT library：不进一等目标的 WERROR 警戒线、可单独设置 MSVC 兼容选项（pay-plugin `libs/drogon-pay/CMakeLists.txt:26-62` 实测模式）：

```cmake
# 生成代码专用 OBJECT library：drogon_ctl 输出，永不手改，不挂 -Werror
add_library(xxx_models OBJECT
    src/models/Order.cc
    src/models/User.cc
)
target_include_directories(xxx_models PRIVATE src/models)
target_link_libraries(xxx_models PRIVATE Drogon::Drogon)

if(MSVC)
    target_compile_options(xxx_models PRIVATE /FI"orm_compat.h" /utf-8)
    target_compile_definitions(xxx_models PRIVATE
        _SILENCE_CXX17_CODECVT_HEADER_DEPRECATION_WARNING)
else()
    target_compile_options(xxx_models PRIVATE -include orm_compat.h)
endif()

# 主目标用 $<TARGET_OBJECTS> 吸入目标文件——不用 target_link_libraries，
# 私有 helper 目标因此不必进 install(EXPORT)（pay-plugin CMakeLists.txt:82-85）
target_sources(${project_name} PRIVATE $<TARGET_OBJECTS:xxx_models>)
```

## Conan 2 + find_package 完整链（pay-plugin 模式）

conanfile.py（节选自 pay-plugin `conanfile.py`，drogon/1.9.13）：

```python
from conan import ConanFile
from conan.tools.cmake import CMake, CMakeDeps, CMakeToolchain, cmake_layout

class MyAppConan(ConanFile):
    settings = "os", "compiler", "build_type", "arch"

    def requirements(self):
        # transitive_headers/transitive_libs：直接使用 drogon 头/符号的目标必须可见
        self.requires("drogon/1.9.13", transitive_headers=True, transitive_libs=True)

    def layout(self):
        cmake_layout(self)
        # 把 generators 目录钉在 config 无关的稳定路径，CMakePresets 才能引用
        # （否则单配置生成器会放到 build/<build_type>/generators）
        self.folders.generators = "build/generators"

    def generate(self):
        CMakeToolchain(self).generate()
        CMakeDeps(self).generate()
```

CMakePresets.json 与之配合（每 preset 独立 binaryDir + 指向稳定 toolchain 路径 + 平台条件）：

```json
{
  "version": 3,
  "cmakeMinimumRequired": { "major": 3, "minor": 21, "patch": 0 },
  "configurePresets": [
    {
      "name": "linux-release",
      "generator": "Unix Makefiles",
      "binaryDir": "${sourceDir}/build/linux-release",
      "cacheVariables": {
        "CMAKE_BUILD_TYPE": "Release",
        "CMAKE_TOOLCHAIN_FILE": "${sourceDir}/build/linux-release/build/generators/conan_toolchain.cmake"
      },
      "condition": { "type": "equals", "lhs": "${hostSystemName}", "rhs": "Linux" }
    },
    {
      "name": "windows-msvc",
      "generator": "Visual Studio 17 2022",
      "architecture": { "value": "x64", "strategy": "set" },
      "binaryDir": "${sourceDir}/build/windows-msvc",
      "cacheVariables": {
        "CMAKE_TOOLCHAIN_FILE": "${sourceDir}/build/windows-msvc/build/generators/conan_toolchain.cmake"
      },
      "condition": { "type": "equals", "lhs": "${hostSystemName}", "rhs": "Windows" }
    }
  ],
  "buildPresets": [
    { "name": "linux-release", "configurePreset": "linux-release" },
    { "name": "windows-msvc", "configurePreset": "windows-msvc", "configuration": "Release" }
  ]
}
```

命令链（preset 名与 output-folder 一一对应）：

```bash
conan install . --output-folder=build/linux-release -s build_type=Release -s compiler.cppstd=17 --build=missing
cmake --preset linux-release
cmake --build --preset linux-release
```

CMakeLists 侧用 `find_package(Drogon CONFIG REQUIRED)`（Conan CMakeDeps 生成的小写包名 `drogon` 亦兼容；pay-plugin 根 `CMakeLists.txt:8` 实测）。**禁止**在 Conan 2 工作流里再手写 `CMAKE_PREFIX_PATH` 指向旧版 Conan（v1）的 `conanbuildinfo.cmake`。

## MSVC 专项

- `/bigobj`：drogon 模板 + ORM 生成代码常超 MSVC 单目标段数上限，宿主与测试目标都要加（pay-plugin `tests/CMakeLists.txt:68-73`）。
- `/FI"orm_compat.h"`（MSVC）与 `-include orm_compat.h`（GCC/Clang）：force-include 一个兼容 shim 头，为生成的模型代码补 codecvt/弃用面（pay-plugin `libs/drogon-pay/CMakeLists.txt:47-58`，shim 放在模型目录 `src/models/orm_compat.h`）。
- `/utf-8`：源码按 UTF-8 解析（无 BOM 中文注释必需，与库目标同契约，pay-plugin `tests/CMakeLists.txt:71`）。
- `_SILENCE_CXX17_CODECVT_HEADER_DEPRECATION_WARNING`、`_CRT_SECURE_NO_WARNINGS`：压制生成代码的弃用告警。

## 三平台编译差异速查

| 项 | GCC | Clang | MSVC |
|----|-----|-------|------|
| force-include | `-include file.h` | `-include file.h` | **`/FI"file.h"`** |
| 大对象文件 | 无需 | 无需 | **`/bigobj` 必加** |
| 源码编码 | 默认 UTF-8 | 默认 UTF-8 | **`/utf-8` 显式加** |
| 警告基线 | `-Wall -Wextra` | `-Wall -Wextra` | `/W4` |
| 生成器 | 单配置 | 单配置 | VS 多配置（`CMAKE_BUILD_TYPE` 无效，用 build preset 的 `configuration`） |

## 错误处理

- `project_name` 为空：返回错误消息
- `cxx_standard` 不是 `17` 或 `20`：返回错误消息
- 文件写入失败：返回错误消息
