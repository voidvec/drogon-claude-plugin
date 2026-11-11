# 设计：私有仓库坐标内联化

- 日期：2026-11-10
- 基线：drogon v1.9.13（不抬到 1.9.14）
- 状态：待用户评审
- 前序：`docs/BASELINE-V1.9.13-FACT-ERRORS.md` 的 B30 已去掉"伪装成 drogon 公开仓库"的私有坐标；本轮处理**如实署名私有仓库、但仍把私有 `文件:行号` 当可复核证据**的落点。

## 1. 问题

插件随附 22 个技能，用户拿不到 `pay-plugin` / `authforge` 这两个私有仓库。但 9 个技能文件里，部分技术结论用私有仓库的 `文件:行号` 坐标作证据（例如 `PayPlugin.cc:107`、`tests/CMakeLists.txt:46`、`apps/server/config/config.json:127-134`）。用户照坐标去翻——翻不到，于是把整段结论一起弃用。

目标：让每条技术结论**对插件用户可自证**——要么紧跟内联最小样例，要么引用用户手里就有的 drogon/trantor/jsoncpp 源坐标；私有仓库名只作"落地经验"的非正式署名保留，不再伪装成可复核坐标。

## 2. 用户已定的两个决策

1. 手法 = **去坐标 + 保留必要署名**：剥离私有 `文件:行号`；技术结论交内联样例或 drogon 源坐标自证；仓库名作非正式署名保留；不改打包（不新增 `examples/` 资产、不动 `sync-assets.py`）。
2. 守卫 = **加坐标型守卫（两层）**：①扫描 49 个事实文件，凡私有仓库名与"非 drogon 源的 `文件:行号`"同行即红（allowlist 放行可验证源）；②特征私有文件名 `PayPlugin.cc` / `TestConfigHelper.h` / `PayAuthMetrics.cc` / `PayAuthMetrics.h` 带坐标 **anywhere** 即红（denylist，drogon 无同名文件、无歧义），兜住同行无仓库名的裸坐标。纯署名放行。第二层是 writing-plans 阶段发现 **4 处裸私有坐标**（plugin:228/238 的 `PayPlugin.cc:NN`、monitoring:97 的 `PayAuthMetrics.h:20-23`/`PayAuthMetrics.cc:9-56`）后追加的；denylist 由最初确认的 2 个 basename 扩到 4 个，以覆盖 monitoring:97 这两处同型裸坐标（用户已定的"特征私有名 denylist"机制的自然延伸，非新范围）。

## 3. 范围与逐文件清单

扫描面 = `tests/test_skills_facts.py` 的 `SCAN_GLOBS`（49 文件）。私有坐标落点全在 `skills/**/references/code-guide.md` 与个别 `SKILL.md`。实测 inventory（`grep pay-plugin|authforge`）：

| 文件 | 私有名命中 | 有私有 `文件:行号`？ | 本轮动作 |
|------|-----------|---------------------|----------|
| `drogon-gen-plugin/references/code-guide.md` | 15 | 是（`PayPlugin.cc:107/113-125/90-101/205-233/338-370/20-30/235-237`、`main.cc:223-226/210-217/236`、`docs/development/plugin_integration.md:46-48`；**另 2 处裸坐标** `:228` `PayPlugin.cc:358-361`、`:238` `PayPlugin.cc:20-30` 同行无仓库名） | 剥坐标；保留同 line 的 drogon 坐标 `HttpAppFrameworkImpl.cc:631-686` 等 |
| `drogon-gen-test/references/code-guide.md` | 11 | 是（`tests/main.cc:1/56-74/26-46/34-46`、`TestConfigHelper.h:31-42/116-163`、`tests/CMakeLists.txt:46/89-97`） | 剥坐标；保留官方示例 `examples/redis_cache/test/test_main.cc:1` |
| `drogon-gen-cmake/references/code-guide.md` | 8 | 是（`libs/drogon-pay/CMakeLists.txt:26-62/47-58`、`CMakeLists.txt:82-85/8`、`tests/CMakeLists.txt:68-73/71`） | 剥坐标；OBJECT 库隔离 / `/bigobj` / `/utf-8` / force-include 结论已有内联样例自证 |
| `drogon-gen-orm-model/references/code-guide.md` | 6 | **否**（仅私有文件名 + 署名，无行号） | 坐标目标下已合规，本轮基本不动；仅复核"不新增坐标"，不做编辑性重写（避免范围 creep） |
| `drogon-gen-monitoring/references/code-guide.md` | 5 | 是（`:35` `apps/server/config/config.json:127-134`；**另 2 处裸坐标** `:97` `PayAuthMetrics.h:20-23`、`PayAuthMetrics.cc:9-56` 同行无仓库名）；`:99/:103` 是 drogon 坐标 + 纯署名（已合规） | 剥 `:35` 与 `:97` 坐标；`:3` 已有免责声明保留 |
| `drogon-gen-monitoring/SKILL.md` | 1 | 否（`pay-plugin 模式` 署名） | 复核，基本不动 |
| `drogon-setup-config/references/code-guide.md` | 5 | 是（`:303` `deploy/docker/Dockerfile:84`、`main.cc:162-166`）；`:231` 已免责 | 剥 `:303` 坐标；多环境布局结论交内联样例 |
| `drogon-gen-rate-limiter/references/code-guide.md` | 4 | 是（`:48` `main.cc:249-271`）；`:69` 是 drogon 坐标 `Hodor.cc:184-189` + 署名（已合规） | 剥 `:48` 私有坐标；保留 `Hodor.cc:76-80` |
| `drogon-gen-redis-config/references/code-guide.md` | 1 | 是（`:72` `PayPlugin.cc:114-117`） | 剥坐标；`operator[]` 插空指针坑结论已有源码机理自证 |

合计需剥私有坐标的文件 = **7**，坐标 token 共 **34**（30 处与仓库名同行 + 4 处裸坐标：plugin:228/238 的 `PayPlugin.cc:NN` 与 monitoring:97 的 `PayAuthMetrics.h:20-23`/`PayAuthMetrics.cc:9-56`，后者由 denylist 兜住）；`orm-model` 与 `monitoring/SKILL.md` 无行号坐标，本轮基本不动、仅复核不新增坐标。

> **inventory 校正（writing-plans 阶段全扫描面重测）**：本表早期稿写 32 处、monitoring 仅 1 处，漏了 monitoring:97 的 2 处裸 `PayAuthMetrics` 坐标（该行无仓库名，故"私有名同行"测量抓不到）。改用"全坐标 token 分类（drogon 源 vs 私有）"重测后定稿 **34**：30 署名 + 4 裸。通用名裸坐标（`CMakeLists.txt:374`、`config.example.json:91`、`main.cc:5` 等）经逐条核对均为 **drogon 自身文件**（cmake:31 上下文"drogon CMakeLists.txt:374/429/456"实证），不在剥离范围。

## 4. 整改手法（逐坐标）

对每一处私有 `文件:行号`：

1. **结论已有内联样例自证** → 直接删坐标，仓库名降为"（pay-plugin 落地经验）"式署名。例：cmake 的 OBJECT 库隔离、`/bigobj`、`/utf-8`、force-include 都紧跟代码块。
2. **结论真正由 drogon 源 backing** → 删私有坐标，保留/补上 drogon 源坐标。例：`plugin:52` 的"initAndStart 内可取客户端"由 `HttpAppFrameworkImpl.cc:631-632`/`:663` 证明，删 `PayPlugin.cc:107`。
3. **结论是私有踩坑、无 drogon 坐标可换** → 删坐标，改写成"私有仓库实测坑"署名 + 把机理讲清楚（机理本身可自证）。例：redis-config 的 `getRedisClient` 空指针坑，机理是 manager `operator[]` 插入空项，讲清机理即可，不需私有行号。

**保留**：仓库名 `pay-plugin`/`authforge` 作非正式署名；私有文件名**不带行号**且明确框定为经验叙述的（如"authforge CMake 注释原话"）可保留，但不得伪装成"去读某行"的可复核坐标。

**禁止**：新增任何私有 `文件:行号`；把私有坐标伪装成 drogon 公开坐标（B30 已处理，本轮不复发）。

## 5. 守卫设计（两层：可验证源 allowlist + 特征私有名 denylist）

### 5.1 为什么不是邻近正则

实测邻近正则 `(?:pay-plugin|authforge)\s*[`（(]?\s*[\w./-]+\.\w+:\d` 在 49 文件上 23 红 / 33 放行，但放行里含真私有坐标（`monitoring:35`、`test:222`、`test:259` 的坐标与仓库名被词语隔开）——**漏报**。故守卫必须抓"私有名行上的任意位置坐标"，再区分 drogon 源（放行）与私有（红）。

**方案 A 已对 HEAD 实测验证**（宽正则 `[\w./-]+:\d+` + 6 条 allowlist，扫 49 文件）：56 条私有名行 → **30 红 / 9 放行**。30 红全是私有坐标（含无扩展名 `deploy/docker/Dockerfile:84`、含邻近正则漏报的 `monitoring:35`/`test:222`/`test:259`），分布在 7 个文件；9 放行恰好是 6 条 allowlist 覆盖的 drogon 源（`Counter.h:53`、`Collector.h:74`、`PromExporter.cc:18`、`HttpAppFrameworkImpl.cc:631/631/675`、`Hodor.cc:76/184`、`examples/redis_cache/test/test_main.cc:1`）。**对当前"私有名同行"的坐标零误报、零漏报**。整改剥掉 30 红后，守卫对 HEAD 应 0 命中。

**裸坐标缺口与闭合（writing-plans 阶段发现）**：上面 30 红只覆盖"同行有仓库名"的坐标。全扫描面重测另有 **4 处裸私有坐标**——`plugin:228` `PayPlugin.cc:358-361`、`plugin:238` `PayPlugin.cc:20-30`、`monitoring:97` `PayAuthMetrics.h:20-23` 与 `PayAuthMetrics.cc:9-56`，同行**没有** pay-plugin/authforge，allowlist 守卫抓不到。故追加**第二层 denylist**：`PayPlugin.cc` / `TestConfigHelper.h` / `PayAuthMetrics.cc` / `PayAuthMetrics.h` 带 `:行号` anywhere 即红（这 4 个 basename 已对 tag clone `find -iname` 核实 drogon 全树 0 命中，无歧义、无碰撞）。两层合计覆盖全部 **34** 处私有坐标。整改后两层对 HEAD 均 0 命中。

**收窄后的残余边界（如实登记）**：denylist 只收录**无歧义**的私有 basename。一个**通用名**私有坐标若同行既无仓库名、 basename 又与 drogon 文件同名（例如裸写 `main.cc:223` 且不带 authforge），两层都抓不到——这是"通用名无法与 drogon 同名文件区分"的固有边界。实测当前所有通用名私有坐标都与仓库名同行（被第一层覆盖），故此边界**当前 0 落点**；不为 hypothetical 写法预设计（沿用 B 批次拒绝理由）。

### 5.2 机制

新增纯函数 + 测试，挂在 `tests/test_skills_facts.py`：

- 对每个扫描面文件的每一物理行，若 `re.search(r'pay-plugin|authforge', line)`：
  - 提取该行所有坐标 token：`re.findall(r'[\w./-]+:\d+', line)`。**故意不要求点扩展名**——私有落点含无扩展名文件 `deploy/docker/Dockerfile:84`（setup-config:303），要求 `\.\w+` 会漏掉它。宽正则 + allowlist 才是精度闸门：正则负责"抓全"，allowlist 负责"放行可验证源"。`文件:起-止` 的止段不被 `:\d+` 捕获，但文件部分已取到，不影响判定。bare 续行 ref（如 `（`:663`）`）因冒号前无 `[\w./-]` 字符而不匹配，忽略。
  - 对每个 token 取文件部分（`:` 前），判定是否"可验证 drogon 源"：
    - basename 命中 `DROGON_SOURCE_BASENAMES`，**或**
    - 文件路径等于 / 以 `DROGON_SOURCE_PATHS` 某条结尾。
  - 任一坐标不可验证 → 收集为 problem（文件:行号 + 该坐标）。
- 测试断言 problems 为空。

**第二层：特征私有名 denylist**（兜裸坐标）

```
PRIVATE_SOURCE_BASENAMES = {"PayPlugin.cc", "TestConfigHelper.h", "PayAuthMetrics.cc", "PayAuthMetrics.h"}
_PRIVATE_COORD = re.compile(r"\b(?:PayPlugin\.cc|TestConfigHelper\.h|PayAuthMetrics\.cc|PayAuthMetrics\.h):\d+")
```

- 对每个扫描面文件的每一物理行（**不要求**同行有仓库名），若 `_PRIVATE_COORD.search(line)` → problem。
- 只匹配带 `:行号` 的坐标；裸文件名（`PayPlugin.cc` 无冒号数字）放行——它是署名/叙述，不是可复核坐标。
- 这 4 个 basename 已对 tag clone 核实 drogon 全树 0 命中，故 denylist 无碰撞、不会误伤 drogon 源。
- 测试断言全扫描面 0 命中。

### 5.3 allowlist（实测 6 条，已对 tag clone 核实存在）

```
DROGON_SOURCE_BASENAMES = {
    "Counter.h", "Collector.h", "PromExporter.cc",
    "HttpAppFrameworkImpl.cc", "Hodor.cc",
}
DROGON_SOURCE_PATHS = {
    "examples/redis_cache/test/test_main.cc",
}
```

- 这 6 条是整改后私有名行上**合法保留**的全部 drogon 坐标的文件部分（monitoring `Counter.h:53`/`Collector.h:74`/`PromExporter.cc:18-36`；plugin `HttpAppFrameworkImpl.cc:631-686`；rate-limiter `Hodor.cc:76-80`/`:184-189`；test 官方示例 `examples/redis_cache/test/test_main.cc:1`）。实现时对 `C:/Users/vilas/tmp-audit/drogon1913`（tag v1.9.13）逐条 `-f` 核实。
- **碰撞避免**：通用名 `main.cc`/`CMakeLists.txt`/`config.json`/`Dockerfile` **故意不进** basename allowlist——私有仓库也用这些名，进了就会漏报。官方示例按**全路径**收录（`examples/redis_cache/test/test_main.cc`），其 basename `test_main.cc` 与私有 `tests/main.cc` 不同名，无碰撞。
- **fail-closed**：陌生文件即红。未来若新增合法 drogon 坐标触发误报，开发者核实后加进 allowlist（与 REQUIRED needle 同维护模型）。
- **allowlist 整改后重测定稿（自评审 Finding A）**：上面 6 条是 **HEAD 实测基线**，不是冻结终值。整改必须**外科手术式**删私有坐标短语、不重排段落，否则可能把*非* allowlist 的 drogon 坐标（如 REQUIRED needle `DrogonConfig.cmake.in:14-20`、`ParseAndAddDrogonTests.cmake:74-79`、`ConfigLoader.cc:168-184`）合并到私有署名行，**误报自己的整改**。落地后再跑一次 §5.1 的测量脚本，确认私有名行上剩余的 drogon 坐标恰好被 allowlist 覆盖；若有合法新增，核实后补进 allowlist 并同步改 §5.4 的数量 canary。

### 5.4 canary 与正反对照（沿用既有守卫纪律）

- **数量 canary**：`test_coord_allowlist_has_declared_size` 写死 `len(BASENAMES)==5`、`len(PATHS)==1`、`len(PRIVATE_SOURCE_BASENAMES)==4`，且条目非空、无重复——删一条只是少放行/少拦一条、不会变红，故需 canary 锁死。
- **合成正对照**（应放行）：`pay-plugin 实测（Counter.h:53）`、`authforge 模式，Hodor.cc:76-80`、`官方示例 examples/redis_cache/test/test_main.cc:1，pay-plugin 同构`、纯署名 `pay-plugin 落地经验`（无坐标）、`PayPlugin.cc 是私有插件类名`（裸文件名无坐标，denylist 放行）。
- **合成反对照**（应红）：`pay-plugin PayPlugin.cc:107`、`authforge main.cc:223-226`、`pay-plugin tests/CMakeLists.txt:46`、坐标与名隔词 `authforge 只配 path（apps/server/config/config.json:127-134）`（专治邻近正则漏报）、`pay-plugin CMakeLists.txt:82-85`（通用名碰撞）、`authforge deploy/docker/Dockerfile:84`（无扩展名文件，专治"要求点扩展名"漏报）、**裸坐标** `排水哨兵（PayPlugin.cc:358-361）`（同行无仓库名，专治第一层漏报，由 denylist 红）、`TestConfigHelper.h:116-163`（denylist）、**裸坐标** `汇总导出（PayAuthMetrics.h:20-23、PayAuthMetrics.cc:9-56）`（monitoring:97 同型，denylist 红）。
- **宽正则的误报面**：`[\w./-]+:\d+` 也会匹配 `host:8080`/`12:30` 这类非文件冒号数字。实测整改后私有名行上除 drogon 坐标外无此类 token；若未来出现合法非文件 `:数字`，需重构该行或登记，不在本轮预设计。
- **先见 RED**：反对照用例在写守卫前/对 HEAD 文本必须先红；整改后对 HEAD 复验私有坐标 0 命中。

### 5.5 与既有守卫的关系

- 坐标型守卫是**新增独立检查**，不改 FORBIDDEN(33)/REQUIRED(46)/FILE_SCOPE(3) 三表，也不改其数量 canary（33/46/3 保持）。
- 私有仓库名本身**不进** FORBIDDEN（署名合法）；只禁"私有名 + 非 drogon 源坐标"的共现结构。
- 豁免沿用 `<!-- fact-guard-waived:TOKEN -->` 点名机制若需要；本守卫预期整改后 0 命中，无需豁免。
- **无重叠（自评审 Finding E，已逐条核实）**：46 条 REQUIRED needle 与 33 条 FORBIDDEN token **无一条**是本轮被剥的私有坐标（REQUIRED 全是 drogon 源坐标或正确结论，FORBIDDEN 全是假 API/键/反向禁令）。故剥私有坐标不会触发既有守卫——**前提是外科手术式编辑保住 needle**。
- **具体外科 hazard（Finding F，已定位）**：`cmake:221` 一行同含 REQUIRED needle `find_package(Drogon CONFIG REQUIRED)` + 私有坐标 `CMakeLists.txt:8` + `pay-plugin`。删 `CMakeLists.txt:8` 时**必须保留** `find_package(Drogon CONFIG REQUIRED)`；删后该行仍含 pay-plugin 但无 `:NN` 坐标 → 坐标守卫放行、REQUIRED 仍绿。同类共享行落地时逐行核对 needle。

## 6. 交付（按评审轮 cadence）

1. 写本轮报告 `docs/PRIVATE-COORDS-INLINE.md`：逐坐标处置表（删/换 drogon/降署名）、守卫机制与 allowlist 取证、正反对照实测、残余缺口如实登记。
2. CHANGELOG `[Unreleased]` 新增本轮小节。
3. **资产传播（自评审 Finding D）**：`skills/` 经两个脚本同步到两个镜像——先跑 `python scripts/sync-assets.py`（→ `src/drogon_plugin/drogon_plugin_assets/`，PyPI）与 `node scripts/sync-assets.mjs`（→ npm 资产），把改动传播过去；**不能只跑 `--check`**（那只校验、不传播，改完源直接 check 必红）。
4. 全门禁：`gen-host-artifacts.py --check`（CLAUDE.md 本轮不改，应仍绿）、`check-consistency.py`、`sync-assets.py --check` + `sync-assets.mjs --check`、`pytest tests/`。
5. 多评审子代理对撞（守卫方向 / 文档声明对撞 / 坐标取证），处置发现。
6. commit + push 分支 + 开 PR。**合并归用户**；不推 tag、不发 PyPI/npm。

## 7. 明确不做（YAGNI / 范围纪律）

- 不抬基线到 1.9.14。
- 不新增 `examples/` 资产、不动 `sync-assets.py` 打包面。
- 不把私有仓库名进 FORBIDDEN（署名合法）。
- 不为"未来可能出现的任意私有变量名写法"引入同行多 token 相与机制（沿用 B 批次已论证的拒绝理由）。
- 守卫只抓 `文件:行号` 坐标；私有文件名**不带行号**的叙述由编辑判断 + 既有 REQUIRED/FORBIDDEN 兜底，不在本守卫范围。

## 8. 验收

- 7 个文件的私有 `文件:行号` 全部剥离（共 34 处，含 4 处裸坐标：2 `PayPlugin.cc:NN` + 2 `PayAuthMetrics`）；技术结论内联自证或 drogon 源 backing。
- 两层坐标守卫对 HEAD 文本均 0 命中；反对照先红后绿；数量 canary 锁死 allowlist(5+1) 与 denylist(4)。
- 既有三表（33/46/3）与全门禁不变绿。
- 报告 + CHANGELOG 声明逐条与代码/测试证据对撞，无过头陈述。