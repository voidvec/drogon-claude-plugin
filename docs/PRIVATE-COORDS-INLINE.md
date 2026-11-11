# 私有仓库坐标内联化（drogon v1.9.13 基线）

- 日期：2026-11-11
- 基线：drogon v1.9.13（不抬 1.9.14）；tag clone `C:/Users/vilas/tmp-audit/drogon1913`（trantor 子模块未 checkout）。
- 前序：`docs/BASELINE-V1.9.13-FACT-ERRORS.md` 的 B30 已去掉"伪装成 drogon 公开仓库"的私有坐标；本轮处理**如实署名私有仓库、但仍把私有 `文件:行号` 当可复核证据**的落点。
- 设计：`docs/superpowers/specs/2026-11-10-private-coords-inline-design.md`；计划：`docs/superpowers/plans/2026-11-10-private-coords-inline.md`。
- 提交：守卫机制 `f70d3fb` + 评审修复 `c908c5b`；剥坐标 `803f73d`；评审 Minor 修复 `8aae5a0`。

## 1. 问题与目标

插件随附 22 个技能，用户拿不到 `pay-plugin` / `authforge` 这两个私有仓库。但 7 个技能文件里，部分技术结论用私有仓库的 `文件:行号` 坐标作证据（如 `PayPlugin.cc:107`、`tests/CMakeLists.txt:46`、`apps/server/config/config.json:127-134`）。用户照坐标去翻——翻不到，于是把整段结论一起弃用。

目标：让每条技术结论**对插件用户可自证**——要么紧跟内联最小样例，要么引用用户手里就有的 drogon/trantor/jsoncpp 源坐标；私有仓库名只作"落地经验"的非正式署名保留，不再伪装成可复核坐标。

## 2. 逐坐标处置表（34 处 = 30 署名行 + 4 裸；31 条编辑）

处置手法三类：**删**（删坐标短语，结论已有内联样例自证）／**换**（删私有坐标、保留同行 drogon 源坐标）／**降**（裸坐标降为署名行）。"自证方式"列：(a) 内联样例 / (b) 幸存 drogon 源坐标 / (c) 明述机制。

### drogon-gen-plugin（13 处）

| # | 坐标 | 署名行? | 处置 | 自证方式 |
|---|------|--------|------|----------|
| 1 | `PayPlugin.cc:107` | 是 | 降署名 | (b) 同行 `HttpAppFrameworkImpl.cc:631-632`/`:663` 证 initAndStart 时序 |
| 2 | `PayPlugin.cc:113-125` | 是 | 删 | (c) operator[] 插空项→析构解引用因果链 + (a) 内联守卫代码 |
| 3 | `PayPlugin.cc:90-101` | 是 | 删 | (a) legacy key 内联样例 |
| 4 | `PayPlugin.cc:205-233` | 是 | 降署名 | (a) EventLoopThread 内联骨架 |
| 5 | `PayPlugin.cc:338-370` | 是 | 删 | (a) 排水哨兵内联骨架 |
| 6 | `PayPlugin.cc:358-361` | **裸** | 降署名 | (a) 排水哨兵内联；denylist 兜 |
| 7 | `docs/development/plugin_integration.md:46-48` | 是 | 降署名 | (a) 内联样例 |
| 8 | `PayPlugin.cc:20-30`（对策） | 是 | 降署名 | (a) ensureLinked 内联 |
| 9 | `PayPlugin.cc:20-30`（插件库内注释） | **裸** | 降署名 | (a) 内联；denylist 兜 |
| 10 | `PayPlugin.cc:235-237` | 是 | 删 | (c) 链接器裁剪机制明述（Minor 修复去掉悬空"注释+"残片） |
| 11 | `main.cc:223-226`（authforge） | 是 | 删 | (b) 同节 drogon 时序坐标 |
| 12 | `main.cc:210-217`（authforge） | 是 | 删 | (c) 机制明述 |
| 13 | `main.cc:236`（authforge） | 是 | 删 | (b) 同行 `HttpAppFrameworkImpl.cc:675` |

### drogon-gen-test（8 处，7 条编辑）

| # | 坐标 | 署名行? | 处置 | 自证方式 |
|---|------|--------|------|----------|
| 1 | `tests/main.cc:1` | 是 | 删 | (b) 同行官方 `examples/redis_cache/test/test_main.cc:1` |
| 2 | `tests/main.cc:56-74` | 是 | 删 | (b) 官方示例坐标 |
| 3 | `tests/main.cc:26-46` + `TestConfigHelper.h:31-42` | 是 | 删（标题，2 坐标） | (a) testPort 内联代码；TestConfigHelper.h denylist 兜 |
| 4 | `tests/main.cc:34-46` | 是 | 删 | (c) reuse_port 劫持机制明述 |
| 5 | `TestConfigHelper.h:116-163` | 是 | 删 | (a) 守卫函数内联；denylist 兜 |
| 6 | `tests/CMakeLists.txt:46` | 是 | 删 | (a) 内联 CMake |
| 7 | `tests/CMakeLists.txt:89-97` | 是 | 删 | (a) 内联 CMake |

### drogon-gen-cmake（6 处）

| # | 坐标 | 署名行? | 处置 | 自证方式 |
|---|------|--------|------|----------|
| 1 | `libs/drogon-pay/CMakeLists.txt:26-62` | 是 | 删 | (a) OBJECT library 内联 CMake |
| 2 | `CMakeLists.txt:82-85` | 是 | 删 | (a) 内联 |
| 3 | `CMakeLists.txt:8`（:221） | 是 | 删 | (a) Conan2 内联链 + (c) find_package config 语义；**保住 needle `find_package(Drogon CONFIG REQUIRED)`** |
| 4 | `tests/CMakeLists.txt:68-73` | 是 | 删 | (a) 内联 |
| 5 | `libs/drogon-pay/CMakeLists.txt:47-58` | 是 | 删 | (c) shim 机制 + orm-model 技能内联承接 |
| 6 | `tests/CMakeLists.txt:71` | 是 | 删 | (a) 内联 |

### drogon-gen-monitoring（3 处，2 条编辑）

| # | 坐标 | 署名行? | 处置 | 自证方式 |
|---|------|--------|------|----------|
| 1 | `apps/server/config/config.json:127-134`（:35） | 是 | 删 | (a) 内联最小配置 `"path":"/metrics"` + (b) 邻行 `PromExporter.cc` 解析坐标 |
| 2 | `PayAuthMetrics.h:20-23` + `PayAuthMetrics.cc:9-56`（:97） | **裸** | 降署名（2 坐标） | (b) `Counter.h:53`/`Collector.h:74` 证两次加锁结论；denylist 兜 |

### drogon-gen-redis-config（1 处）

| # | 坐标 | 署名行? | 处置 | 自证方式 |
|---|------|--------|------|----------|
| 1 | `PayPlugin.cc:114-117`（:72） | 是 | 删 | (c) manager operator[] 插空项→崩溃因果链明述；denylist 兜 |

### drogon-gen-rate-limiter（1 处）

| # | 坐标 | 署名行? | 处置 | 自证方式 |
|---|------|--------|------|----------|
| 1 | `main.cc:249-271`（authforge，:48） | 是 | 删 | (b) 同行 `Hodor.cc:76-80` + (a) setRejectResponseFactory 内联（Minor 修复删行内重复署名） |

### drogon-setup-config（2 处，1 条编辑）

| # | 坐标 | 署名行? | 处置 | 自证方式 |
|---|------|--------|------|----------|
| 1 | `deploy/docker/Dockerfile:84` + `main.cc:162-166`（authforge，:303） | 是 | 删（整行，2 坐标） | (a) `COPY config.prod.json ./config.json` 本身即内联微样例 + (c) 候选路径回退顺序明述（Minor 修复删两处行内重复署名） |

**合计 34 处**（plugin 13 / test 8 / cmake 6 / monitoring 3 / redis-config 1 / rate-limiter 1 / setup-config 2）；**4 处裸坐标**（plugin #6/#9、monitoring #2 的 2 个）由第二层 denylist 兜住。`orm-model` 与 `monitoring/SKILL.md` 无行号坐标，本轮未动。

## 3. 守卫机制与取证

新增独立坐标守卫挂在 `tests/test_skills_facts.py`，**不动**既有 FORBIDDEN(33)/REQUIRED(46)/FILE_SCOPE(3) 三表及其数量 canary。

- **第一层**（私有名同行）：对匹配 `pay-plugin|authforge` 的行，提取所有 `[\w./-]+:\d+` 坐标，文件部分不在 drogon 源 allowlist 即红。宽正则**故意不要求点扩展名**——私有落点含无扩展名 `deploy/docker/Dockerfile:84`，要求 `\.\w+` 会漏掉它；精度由 allowlist 闸门负责。
  - `DROGON_SOURCE_BASENAMES`（5）：`Counter.h`、`Collector.h`、`PromExporter.cc`、`HttpAppFrameworkImpl.cc`、`Hodor.cc`。
  - `DROGON_SOURCE_PATHS`（1，全路径）：`examples/redis_cache/test/test_main.cc`（basename `test_main.cc` 与私有 `tests/main.cc` 不同名，无碰撞；通用名 `main.cc`/`CMakeLists.txt`/`config.json`/`Dockerfile` 故意不进 basename allowlist，避免私有同名漏报）。
- **第二层**（denylist 兜裸坐标）：`PRIVATE_SOURCE_BASENAMES`（4）= `PayPlugin.cc`、`TestConfigHelper.h`、`PayAuthMetrics.cc`、`PayAuthMetrics.h`，带 `:行号` anywhere 即红（不要求同行有仓库名）。正则 `_PRIVATE_COORD` **由集合派生**（`"|".join(re.escape(n) for n in sorted(...))`，单一事实源，评审 I1 修复，避免集合与正则手工双源静默失同步）。裸文件名（无 `:数字`）放行——它是署名/叙述，不是可复核坐标。

**取证（本轮对 tag v1.9.13 clone 实跑）**：
- denylist 4 basename `find -iname` 全树 **0 命中**（无碰撞、不会误伤 drogon 源）。
- allowlist 5 basename 各 **1 命中**、全路径 `examples/redis_cache/test/test_main.cc` **存在**。
- 数量 canary `test_coord_allowlist_has_declared_size` 锁死 5/1/4，条目非空白、denylist∩allowlist=∅。
- 合成正对照 7 条放行（含可验证 drogon 坐标、纯署名、裸文件名、以及"drogon 自身 `main.cc:5`"锁第一层仓库名闸门——评审 M1 修复，删闸门即红）；反对照 9 条红（含署名/裸/通用名碰撞/无扩展名/坐标与名隔词）。
- HEAD 回归 `test_no_private_coords_in_fact_sources` 扫全 `_scanned_files()` 面，复用 `_coord_problems` 纯函数，0 命中。

## 4. 实测（本轮独立重测，非引用计划估算）

对剥坐标前提交 `c908c5b` 的旧 blob 与 HEAD 逐文件重算：

| 文件 | 整改前 L1 红 | 整改前 L1 放行(drogon) | 整改前 L2 命中 | 整改后 L1 红 | 整改后 L2 |
|------|------|------|------|------|------|
| plugin | 11 | 3 | 9 | 0 | 0 |
| test | 8 | 1 | 2 | 0 | 0 |
| cmake | 6 | 0 | 0 | 0 | 0 |
| monitoring | 1 | 3 | 2 | 0 | 0 |
| redis-config | 1 | 0 | 1 | 0 | 0 |
| rate-limiter | 1 | 2 | 0 | 0 | 0 |
| setup-config | 2 | 0 | 0 | 0 | 0 |
| **合计** | **30** | **9** | **14** | **0** | **0** |

- **34 处私有坐标按出现次数计**（30 署名行 + 4 裸）；按 (文件,坐标 token) 去重为 **33 distinct**——`PayPlugin.cc:20-30` 在 plugin 出现两次（一处在署名行、一处裸），故去重少 1。报告与 CHANGELOG 统一用"34 处"口径。
- 第二层 14 命中 = 10 处与第一层红重叠（denylist basename 恰在署名行）+ 4 处裸坐标仅第二层抓到。**计划骨架曾估算"12 命中"，本轮重测纠正为 14**（如实登记，不沿用估算）。
- 整改后：两层均 0 命中；全扫描面（49 文件）`_coord_problems` 0 问题；allowlist 完整性重测——私有名行上剩余 **9 处 drogon 坐标全 OK**（`Counter.h:53`、`Collector.h:74`、`PromExporter.cc:18`、`HttpAppFrameworkImpl.cc:631`×2/`:675`、`Hodor.cc:76`/`:184`、`examples/redis_cache/test/test_main.cc:1`），无 BAD。
- 既有三表 33/46/3 不变绿；`pytest tests/test_skills_facts.py` **90 passed**（含新增 4 个坐标用例）。
- 评审：Task 2 经 spec 合规子代理（34 剥除/分布/保针/无重排逐条独立复核 ✅）+ 代码质量子代理（APPROVED，31 编辑行结论全部保有 a/b/c 至少一种支撑、无悬空断言）；3 项 Minor 中 2 项已顺手修复（`8aae5a0`：去悬空"注释+"残片、删 rate-limiter/setup-config 同行重复署名），第 3 项（monitoring §4 补内联样例）属可选增强，留待后续轮次。

## 5. 残余边界（如实登记）

- **通用名裸坐标**：私有坐标若同行既无仓库名、basename 又与 drogon 同名（如裸写 `main.cc:223` 不带 authforge），两层都抓不到——"通用名无法与 drogon 同名文件区分"的固有边界。当前所有通用名私有坐标都与仓库名同行（被第一层覆盖），此边界**当前 0 落点**；不为 hypothetical 写法预设计（沿用 B 批次拒绝理由）。
- **坐标变体绕过**（代码质量评审 M2 登记）：denylist 与宽正则都只认半角冒号紧跟数字的形态。全角冒号 `PayPlugin.cc：107`、冒号后带空格 `PayPlugin.cc: 107` 这类变体两层都抓不到。当前扫描面 0 落点；若未来出现需重构该行或扩展正则，不在本轮预设计。
- **宽正则误报面**：`[\w./-]+:\d+` 也匹配 `host:8080`/`12:30` 这类非文件冒号数字。整改后私有名行上除 drogon 坐标外无此类 token；若未来出现合法非文件 `:数字`，需重构该行或登记。
- **私有文件名不带行号的叙述**不在本守卫范围，由编辑判断 + 既有 REQUIRED/FORBIDDEN 兜底。
- **扫描面盲区**（沿用既有守卫的登记）：`references/*.md` 中没有任何 REQUIRED needle 的文件改名不会让坐标守卫红（坐标守卫按 `SCAN_GLOBS` 扫描，改名后文件仍被扫到则不影响；但若改扩展名脱离 glob 则脱离扫描）——与既有事实守卫同边界。

## 6. 明确不做（YAGNI / 范围纪律）

- 不抬基线到 1.9.14。
- 不新增 `examples/` 资产、不动 `sync-assets.py` 打包面。
- 不把私有仓库名进 FORBIDDEN（署名合法）；只禁"私有名 + 非 drogon 源坐标"共现结构与特征私有 basename 带坐标。
- 不为"未来可能出现的任意私有变量名写法"引入同行多 token 相与机制。
- 守卫只抓 `文件:行号` 坐标；私有文件名不带行号的叙述不在本守卫范围。

## 7. 验收对照

- 7 个文件 34 处私有 `文件:行号` 全部剥离（含 4 裸）；技术结论内联自证或 drogon 源 backing。✓（§2/§4）
- 两层坐标守卫对 HEAD 文本均 0 命中；反对照先红后绿；数量 canary 锁死 allowlist(5+1) 与 denylist(4)。✓（§3/§4）
- 既有三表（33/46/3）与全门禁不变绿。✓（§4；资产传播与全门禁见 Task 4）
- 报告 + CHANGELOG 声明逐条与代码/测试证据对撞，无过头陈述（层 2 命中数由估算 12 纠正为实测 14）。✓