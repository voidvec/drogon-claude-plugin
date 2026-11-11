# 私有仓库坐标内联化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 剥离 7 个技能文件里 34 处用户无法复核的私有仓库（pay-plugin/authforge）`文件:行号` 坐标，技术结论改由内联样例或 drogon 源坐标自证，并加两层坐标守卫防回流。

**Architecture:** 在既有 `tests/test_skills_facts.py` 上**新增独立**坐标守卫（不动 FORBIDDEN/REQUIRED/FILE_SCOPE 三表）：第一层抓"私有名同行 + 非 drogon 源坐标"（allowlist 放行可验证源），第二层抓"特征私有 basename 带坐标 anywhere"（denylist 兜裸坐标）。整改是外科手术式删坐标短语、保留仓库名署名与同行 drogon 坐标，不重排段落。

**Tech Stack:** Python 3.9+ / pytest / 纯函数 + 合成文本正反对照；Markdown 技能文档；`scripts/sync-assets.py` + `scripts/sync-assets.mjs` 双镜像传播。

**Spec:** `docs/superpowers/specs/2026-11-10-private-coords-inline-design.md`（已校正：34 坐标 / denylist 4 条）。

**基线纪律：** drogon v1.9.13，不抬 1.9.14。tag clone 在 `C:/Users/vilas/tmp-audit/drogon1913`（trantor 子模块未 checkout）。合并归用户；不推 tag、不发 PyPI/npm。

---

## File Structure

| 文件 | 责任 | 动作 |
|------|------|------|
| `tests/test_skills_facts.py` | 事实守卫；新增坐标守卫常量 + 纯函数 + 4 个测试 | Modify（追加，不改三表） |
| `skills/drogon-gen-plugin/references/code-guide.md` | 剥 13 处私有坐标 | Modify |
| `skills/drogon-gen-test/references/code-guide.md` | 剥 8 处私有坐标 | Modify |
| `skills/drogon-gen-cmake/references/code-guide.md` | 剥 6 处私有坐标 | Modify |
| `skills/drogon-gen-monitoring/references/code-guide.md` | 剥 3 处私有坐标（含 2 裸 PayAuthMetrics） | Modify |
| `skills/drogon-gen-redis-config/references/code-guide.md` | 剥 1 处私有坐标 | Modify |
| `skills/drogon-gen-rate-limiter/references/code-guide.md` | 剥 1 处私有坐标 | Modify |
| `skills/drogon-setup-config/references/code-guide.md` | 剥 2 处私有坐标（同一行） | Modify |
| `docs/PRIVATE-COORDS-INLINE.md` | 本轮证据报告 | Create |
| `CHANGELOG.md` | `[Unreleased]` 新增小节 | Modify |
| `src/drogon_plugin/drogon_plugin_assets/**`、`npm/assets/**` | 两个资产镜像 | 由 sync 脚本传播 |

**坐标 inventory（34 = 30 署名 + 4 裸）：** plugin 13、test 8、cmake 6、monitoring 3、redis-config 1、rate-limiter 1、setup-config 2。裸坐标 4 处：plugin:228 `PayPlugin.cc:358-361`、plugin:238 `PayPlugin.cc:20-30`、monitoring:97 `PayAuthMetrics.h:20-23` 与 `PayAuthMetrics.cc:9-56`。

**外科 hazard（必须保住）：**
- `cmake:221` 同行含 REQUIRED needle `find_package(Drogon CONFIG REQUIRED)`——删 `CMakeLists.txt:8` 时**保留**该 needle。
- `plugin:52`/`:277`、`rate-limiter:48`、`test:119` 同行含 drogon 坐标（`HttpAppFrameworkImpl.cc:631-632`/`:675`、`Hodor.cc:76-80`、`examples/redis_cache/test/test_main.cc:1`）——**保留**。
- `monitoring:3` 免责声明 needle `不在源码核对范围内`、`monitoring:99/:103` 的 drogon 坐标——**不动**。

---

## Task 1: 坐标守卫机制（常量 + 纯函数 + canary + 合成正反对照）

**Files:**
- Modify: `tests/test_skills_facts.py`（顶部 import 区 + REQUIRED 列表之后追加常量/函数；文件末尾追加 3 个测试）
- Test: `tests/test_skills_facts.py`

- [ ] **Step 1: 写失败测试（canary + 正对照 + 反对照）**

在 `tests/test_skills_facts.py` **文件末尾**追加：

```python
def test_coord_allowlist_has_declared_size():
    """数量 canary：删一条 allowlist/denylist 只是少放行/少拦一条、不会变红，故锁死数量。"""
    assert len(DROGON_SOURCE_BASENAMES) == 5, DROGON_SOURCE_BASENAMES
    assert len(DROGON_SOURCE_PATHS) == 1, DROGON_SOURCE_PATHS
    assert len(PRIVATE_SOURCE_BASENAMES) == 4, PRIVATE_SOURCE_BASENAMES
    for name in DROGON_SOURCE_BASENAMES | DROGON_SOURCE_PATHS | PRIVATE_SOURCE_BASENAMES:
        assert name and name.strip(), f"坐标守卫登记表有空白条目 {name!r}"
    assert not (PRIVATE_SOURCE_BASENAMES & DROGON_SOURCE_BASENAMES), \
        "denylist 与 allowlist 相交：私有 basename 不可能同时是可验证 drogon 源"


def test_coord_guard_positive_controls():
    """正向对照：可验证 drogon 源坐标 + 纯署名 + 裸文件名（无坐标）必须放行。"""
    assert _coord_problems("x.md", "pay-plugin 实测（Counter.h:53）") == []
    assert _coord_problems("x.md", "authforge 模式，Hodor.cc:76-80") == []
    assert _coord_problems(
        "x.md", "官方示例 examples/redis_cache/test/test_main.cc:1，pay-plugin 同构") == []
    assert _coord_problems("x.md", "pay-plugin 落地经验") == []
    assert _coord_problems("x.md", "PayPlugin.cc 是私有插件类名") == []
    assert _coord_problems(
        "x.md", "pay-plugin 用 HttpAppFrameworkImpl.cc:631-686 证明时序") == []


def test_coord_guard_negative_controls():
    """反向对照：私有坐标（署名/裸/通用名/无扩展名）必须红。"""
    assert _coord_problems("x.md", "pay-plugin PayPlugin.cc:107")
    assert _coord_problems("x.md", "authforge main.cc:223-226")
    assert _coord_problems("x.md", "pay-plugin tests/CMakeLists.txt:46")
    assert _coord_problems(
        "x.md", "authforge 只配 path（apps/server/config/config.json:127-134）")
    assert _coord_problems("x.md", "pay-plugin CMakeLists.txt:82-85")
    assert _coord_problems("x.md", "authforge deploy/docker/Dockerfile:84")
    assert _coord_problems("x.md", "排水哨兵（PayPlugin.cc:358-361）")
    assert _coord_problems("x.md", "TestConfigHelper.h:116-163")
    assert _coord_problems(
        "x.md", "汇总导出（PayAuthMetrics.h:20-23、PayAuthMetrics.cc:9-56）")
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_skills_facts.py::test_coord_guard_positive_controls tests/test_skills_facts.py::test_coord_guard_negative_controls tests/test_skills_facts.py::test_coord_allowlist_has_declared_size -v`
Expected: FAIL/ERROR — `NameError: name '_coord_problems' is not defined`（函数与常量尚未定义）。

- [ ] **Step 3: 加 import 与常量 + 纯函数**

在 `tests/test_skills_facts.py` 顶部 `from pathlib import Path` 之前加一行：

```python
import re
```

在 `REQUIRED = [...]` 列表**结束之后**、`def _scanned_files():` **之前**插入：

```python
# ── 坐标型守卫（私有仓库坐标内联化，2026-11-10）──────────────────────────
# 两层：①私有名同行 + 非 drogon 源坐标 → 红；②特征私有 basename 带坐标 anywhere → 红。
# 设计见 docs/superpowers/specs/2026-11-10-private-coords-inline-design.md。
_PRIVATE_REPO_NAMES = re.compile(r"pay-plugin|authforge")
# 故意不要求点扩展名：私有落点含无扩展名 deploy/docker/Dockerfile:84。
_COORD_TOKEN = re.compile(r"[\w./-]+:\d+")

# 第二层 denylist：特征私有 basename（drogon 全树 0 命中，无碰撞），带坐标 anywhere 即红。
PRIVATE_SOURCE_BASENAMES = {
    "PayPlugin.cc", "TestConfigHelper.h", "PayAuthMetrics.cc", "PayAuthMetrics.h",
}
_PRIVATE_COORD = re.compile(
    r"\b(?:PayPlugin\.cc|TestConfigHelper\.h|PayAuthMetrics\.cc|PayAuthMetrics\.h):\d+"
)

# 第一层 allowlist：整改后私有名行上合法保留的全部 drogon 源坐标的文件部分。
DROGON_SOURCE_BASENAMES = {
    "Counter.h", "Collector.h", "PromExporter.cc",
    "HttpAppFrameworkImpl.cc", "Hodor.cc",
}
DROGON_SOURCE_PATHS = {
    "examples/redis_cache/test/test_main.cc",
}


def _is_verifiable_drogon_source(file_part):
    basename = file_part.rsplit("/", 1)[-1]
    if basename in DROGON_SOURCE_BASENAMES:
        return True
    return any(file_part == p or file_part.endswith("/" + p)
               for p in DROGON_SOURCE_PATHS)


def _coord_problems(rel_path, text):
    """返回私有坐标问题列表（纯函数，便于合成文本正反对照）。

    层②不要求同行有仓库名（兜裸坐标）；层①只在私有名行上判坐标可验证性。
    同一坐标可能被两层各报一次——守卫是布尔判定，重复不影响"0 命中"结论。
    """
    problems = []
    for line_no, line in enumerate(text.splitlines(), 1):
        for m in _PRIVATE_COORD.finditer(line):
            problems.append(f"{rel_path}:{line_no} 私有源坐标 {m.group(0)}（denylist）")
        if _PRIVATE_REPO_NAMES.search(line):
            for token in _COORD_TOKEN.findall(line):
                file_part = token.rsplit(":", 1)[0]
                if not _is_verifiable_drogon_source(file_part):
                    problems.append(
                        f"{rel_path}:{line_no} 私有名行上的不可验证坐标 {token}")
    return problems
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_skills_facts.py::test_coord_guard_positive_controls tests/test_skills_facts.py::test_coord_guard_negative_controls tests/test_skills_facts.py::test_coord_allowlist_has_declared_size -v`
Expected: 3 PASS。

- [ ] **Step 5: 跑既有守卫确认未破坏三表**

Run: `python -m pytest tests/test_skills_facts.py -v`
Expected: 既有用例全 PASS（FORBIDDEN 33 / REQUIRED 46 / FILE_SCOPE 3 不变），新增 3 个 PASS。此时**还没有** HEAD 回归用例（Task 2 才加），故私有坐标存量不会让本步骤红。

- [ ] **Step 6: Commit**

```bash
git add tests/test_skills_facts.py
git commit -m "test: 两层私有坐标守卫机制（allowlist 5+1 / denylist 4）+ 合成正反对照"
```

---

## Task 2: HEAD 回归用例（RED）+ 外科剥离 34 处坐标（GREEN）

**Files:**
- Modify: `tests/test_skills_facts.py`（末尾追加 HEAD 回归用例）
- Modify: 7 个 `skills/**/references/code-guide.md`（见下逐条编辑）

- [ ] **Step 1: 写 HEAD 回归用例（先见 RED）**

在 `tests/test_skills_facts.py` **文件末尾**追加：

```python
def test_no_private_coords_in_fact_sources():
    """全扫描面不许有私有仓库坐标（两层守卫对 HEAD 文本 0 命中）。

    用户拿不到 pay-plugin/authforge，私有 文件:行号 是不可复核证据；
    技术结论必须内联自证或换 drogon/trantor/jsoncpp 源坐标。
    """
    bad = []
    for path in _scanned_files():
        rel = path.relative_to(REPO_ROOT).as_posix()
        bad += _coord_problems(rel, path.read_text(encoding="utf-8"))
    assert not bad, (
        "以下私有坐标用户无法复核，应内联自证或换 drogon 源坐标: " + str(bad)
    )
```

- [ ] **Step 2: 跑回归用例确认 RED**

Run: `python -m pytest tests/test_skills_facts.py::test_no_private_coords_in_fact_sources -v`
Expected: FAIL — 断言列出 34 处私有坐标（部分被两层各报一次，条目数 ≥ 34），含 `plugin:228 PayPlugin.cc:358`、`monitoring:97 PayAuthMetrics.h:20` 等裸坐标。

- [ ] **Step 3: 剥离 plugin 的 13 处坐标**

文件 `skills/drogon-gen-plugin/references/code-guide.md`，逐条 Edit（old → new）：

1. `（pay-plugin `PayPlugin.cc:107` 实测）` → `（pay-plugin 落地经验）`
2. `//    解引用崩溃（pay-plugin PayPlugin.cc:113-125 实测坑）` → `//    解引用崩溃（pay-plugin 实测坑）`
3. `（pay-plugin `PayPlugin.cc:90-101` 的 legacy key 模式）` → `（pay-plugin 的 legacy key 模式）`
4. `（pay-plugin `PayPlugin.cc:205-233`）` → `（pay-plugin 落地经验）`
5. `（pay-plugin `PayPlugin.cc:338-370` 实测）` → `（pay-plugin 实测）`
6. `（`PayPlugin.cc:358-361`）` → `（pay-plugin 落地经验）`
7. `（pay-plugin `docs/development/plugin_integration.md:46-48`）` → `（pay-plugin 落地经验）`
8. `对策（pay-plugin `PayPlugin.cc:20-30`）：` → `对策（pay-plugin 落地经验）：`
9. `// 插件库内（PayPlugin.cc:20-30 模式）` → `// 插件库内（pay-plugin 模式）`
10. `（pay-plugin `PayPlugin.cc:235-237` 注释 + `registerHttpHandlers()`）` → `（pay-plugin 落地经验：注释 + `registerHttpHandlers()`）`
11. `（authforge `main.cc:223-226` 注释：` → `（authforge 注释：`
12. `（authforge `main.cc:210-217`：` → `（authforge：`
13. `（authforge `main.cc:236` 注释；` → `（authforge 注释；`

**保住**：第 1 条同行的 `HttpAppFrameworkImpl.cc:631-632`/`:663`、第 13 条同行的 `HttpAppFrameworkImpl.cc:675` 不动。

- [ ] **Step 4: 剥离 test 的 8 处坐标**

文件 `skills/drogon-gen-test/references/code-guide.md`：

1. `pay-plugin（`tests/main.cc:1`）与 drogon 官方示例` → `pay-plugin 与 drogon 官方示例`
2. `，pay-plugin `tests/main.cc:56-74` 同构）` → `，pay-plugin 同构）`
3. `### PAY_TEST_PORT 端口隔离模式（pay-plugin `tests/main.cc:26-46` + `TestConfigHelper.h:31-42`）` → `### PAY_TEST_PORT 端口隔离模式（pay-plugin 实测）`
4. `（pay-plugin `tests/main.cc:34-46` 记录的实测坑）` → `（pay-plugin 记录的实测坑）`
5. `（pay-plugin `TestConfigHelper.h:116-163`）` → `（pay-plugin 实测）`
6. `# （pay-plugin 链接 pay_core pay_host_core，tests/CMakeLists.txt:46）` → `# （pay-plugin 链接 pay_core pay_host_core）`
7. `单 `add_test` 全跑（pay-plugin 模式，`tests/CMakeLists.txt:89-97`）` → `单 `add_test` 全跑（pay-plugin 模式）`

**保住**：第 1 条同行的官方 `examples/redis_cache/test/test_main.cc:1`、第 2 条的 `examples/redis_cache/test/test_main.cc`（无行号）不动；REQUIRED needle `ParseAndAddDrogonTests.cmake:74-79`、`enable_testing()` 不在这些行，不受影响。

- [ ] **Step 5: 剥离 cmake 的 6 处坐标**

文件 `skills/drogon-gen-cmake/references/code-guide.md`：

1. `（pay-plugin `libs/drogon-pay/CMakeLists.txt:26-62` 实测模式）` → `（pay-plugin 实测模式）`
2. `# 私有 helper 目标因此不必进 install(EXPORT)（pay-plugin CMakeLists.txt:82-85）` → `# 私有 helper 目标因此不必进 install(EXPORT)（pay-plugin 模式）`
3. `；pay-plugin 根 `CMakeLists.txt:8` 实测）` → `；pay-plugin 实测）`
4. `（pay-plugin `tests/CMakeLists.txt:68-73`）` → `（pay-plugin 实测）`
5. `（pay-plugin `libs/drogon-pay/CMakeLists.txt:47-58`，shim 放在模型目录` → `（pay-plugin 实测，shim 放在模型目录`
6. `与库目标同契约，pay-plugin `tests/CMakeLists.txt:71`）` → `与库目标同契约，pay-plugin 实测）`

**保住（Finding F）**：第 3 条所在行（:221）开头的 `find_package(Drogon CONFIG REQUIRED)` 是 REQUIRED needle，**只删 `CMakeLists.txt:8` 短语，needle 原样保留**。`DrogonConfig.cmake.in:14-20` needle 不在这些行。

- [ ] **Step 6: 剥离 monitoring 的 3 处坐标**

文件 `skills/drogon-gen-monitoring/references/code-guide.md`：

1. `authforge 只配 `"path": "/metrics"`（apps/server/config/config.json:127-134），指标全在代码内注册。` → `authforge 只配 `"path": "/metrics"`，指标全在代码内注册。`
2. `汇总导出（PayAuthMetrics.h:20-23、PayAuthMetrics.cc:9-56），由独立的低频 handler` → `汇总导出（pay-plugin PayAuthMetrics 模式），由独立的低频 handler`

**保住**：`:3` 免责声明 needle `不在源码核对范围内`、`:99` 的 `Counter.h:53`/`Collector.h:74`、`:103` 的 `PromExporter.cc:18-36` 全不动（均在 allowlist）。第 2 条把裸坐标行降为署名行（新增 pay-plugin 名，但该行剥后无 `:NN`，守卫放行）。

- [ ] **Step 7: 剥离 redis-config / rate-limiter / setup-config 的 4 处坐标**

文件 `skills/drogon-gen-redis-config/references/code-guide.md`：
1. `（pay-plugin `PayPlugin.cc:114-117` 注释记录的实测坑）` → `（pay-plugin 注释记录的实测坑）`

文件 `skills/drogon-gen-rate-limiter/references/code-guide.md`：
2. `生产做法（authforge main.cc:249-271）：` → `生产做法（authforge 模式）：`
   **保住**：同行 `Hodor.cc:76-80` 不动。

文件 `skills/drogon-setup-config/references/code-guide.md`（同一行 :303 含 2 坐标，整行替换）：
3. old:
   `- **加载方式**：部署期选择，不做运行时 if/else——Dockerfile 里 `COPY config.prod.json ./config.json`（authforge `deploy/docker/Dockerfile:84`），程序永远只找 `./config.json`；main 里只做候选路径回退（`./config.json` → `../config.json`，authforge `main.cc:162-166`）。`
   new:
   `- **加载方式**：部署期选择，不做运行时 if/else——Dockerfile 里 `COPY config.prod.json ./config.json`（authforge 模式），程序永远只找 `./config.json`；main 里只做候选路径回退（`./config.json` → `../config.json`，authforge 模式）。`

- [ ] **Step 8: 跑回归用例确认 GREEN + 全守卫绿**

Run: `python -m pytest tests/test_skills_facts.py -v`
Expected: 全 PASS——`test_no_private_coords_in_fact_sources` 0 命中；REQUIRED 46 条全绿（needle 保住）；FORBIDDEN 33 条全绿；新增 4 个坐标用例全绿。

- [ ] **Step 9: 重测 allowlist 完整性（Finding A）**

Run（纯测量，确认私有名行上剩余 drogon 坐标恰好被 allowlist 覆盖）：

```bash
python - <<'PY'
import re
from pathlib import Path
ROOT=Path(".")
COORD=re.compile(r"[\w./-]+:\d+"); REPO=re.compile(r"pay-plugin|authforge")
BASE={"Counter.h","Collector.h","PromExporter.cc","HttpAppFrameworkImpl.cc","Hodor.cc"}
PATHS={"examples/redis_cache/test/test_main.cc"}
def ok(fp):
    b=fp.rsplit("/",1)[-1]
    return b in BASE or any(fp==p or fp.endswith("/"+p) for p in PATHS)
left=[]
for g in ("skills/**/*.md","CLAUDE.md","README*.md","AGENTS.md","GEMINI.md"):
    for p in sorted(ROOT.glob(g)):
        if not p.is_file(): continue
        rel=p.relative_to(ROOT).as_posix()
        for n,line in enumerate(p.read_text(encoding="utf-8").splitlines(),1):
            if REPO.search(line):
                for tok in COORD.findall(line):
                    fp=tok.rsplit(":",1)[0]
                    left.append((fp,tok,f"{rel}:{n}",ok(fp)))
print("私有名行上剩余坐标（应全部 ok=True）:")
for fp,tok,loc,v in left:
    print(f"  {'OK ' if v else 'BAD'} {tok}  @ {loc}")
assert all(v for *_,v in left), "有非 allowlist 坐标落在私有名行——需核实后补 allowlist"
print("allowlist 完整性 OK，共", len(left), "处 drogon 坐标")
PY
```

Expected: 剩余约 9 处 drogon 坐标全 `OK`（`Counter.h:53`、`Collector.h:74`、`PromExporter.cc:18`、`HttpAppFrameworkImpl.cc:631`×2/`:675`、`Hodor.cc:76`/`:184`、`examples/redis_cache/test/test_main.cc:1`），无 `BAD`。若出现 `BAD`，核实该坐标确属 drogon 源后补进 allowlist 并同步改 Task 1 canary 数量。

- [ ] **Step 10: Commit**

```bash
git add tests/test_skills_facts.py skills/drogon-gen-plugin/references/code-guide.md skills/drogon-gen-test/references/code-guide.md skills/drogon-gen-cmake/references/code-guide.md skills/drogon-gen-monitoring/references/code-guide.md skills/drogon-gen-redis-config/references/code-guide.md skills/drogon-gen-rate-limiter/references/code-guide.md skills/drogon-setup-config/references/code-guide.md
git commit -m "fix: 剥离 34 处私有仓库坐标，技术结论内联自证/换 drogon 源 + HEAD 回归守卫"
```

---

## Task 3: 证据报告 + CHANGELOG 登记

**Files:**
- Create: `docs/PRIVATE-COORDS-INLINE.md`
- Modify: `CHANGELOG.md`（`[Unreleased]` 末尾、`## [0.5.0]` 之前插入新小节）

- [ ] **Step 1: 写报告 `docs/PRIVATE-COORDS-INLINE.md`**

内容必须含（用实测数据，不得把意图当事实）：

```markdown
# 私有仓库坐标内联化（drogon v1.9.13 基线）

- 日期：2026-11-11
- 前序：B30 已去"伪装成 drogon 公开仓库"的私有坐标；本轮处理"如实署名私有仓库、但仍把私有 文件:行号 当可复核证据"的落点。
- 设计：docs/superpowers/specs/2026-11-10-private-coords-inline-design.md

## 1. 问题与目标
插件用户拿不到 pay-plugin/authforge。私有 文件:行号 是不可复核证据——用户照坐标翻不到，会连结论一起弃用。目标：每条技术结论内联自证或换 drogon/trantor/jsoncpp 源坐标；仓库名降为非正式署名。

## 2. 逐坐标处置表（34 处 = 30 署名 + 4 裸）
| 文件 | 坐标 | 处置 | 自证方式 |
|------|------|------|----------|
（按 Task 2 的 31 条编辑逐行列：删坐标 / 保留同行 drogon 坐标 / 降署名；plugin 13、test 8、cmake 6、monitoring 3、redis-config 1、rate-limiter 1、setup-config 2）

## 3. 守卫机制与取证
- 两层：①私有名同行 + 非 drogon 源坐标（allowlist 5 basename + 1 path）；②特征私有 basename 带坐标 anywhere（denylist 4：PayPlugin.cc/TestConfigHelper.h/PayAuthMetrics.cc/PayAuthMetrics.h）。
- allowlist 6 条已对 tag clone 逐条 -f 核实存在；denylist 4 条已 find -iname 核实 drogon 全树 0 命中（无碰撞）。
- 数量 canary：5/1/4；合成正对照 6 条放行、反对照 9 条红（含 2 裸坐标）。

## 4. 实测
- 整改前 HEAD：第一层 30 红 / 9 放行；第二层 12 命中；并集 34 distinct（4 裸由第二层兜）。
- 整改后 HEAD：两层均 0 命中；allowlist 完整性重测剩余 9 处 drogon 坐标全 OK。
- 既有三表 33/46/3 不变绿。

## 5. 残余边界（如实登记）
- 通用名私有坐标若同行既无仓库名、basename 又与 drogon 同名（如裸 main.cc:223 不带 authforge），两层都抓不到——固有边界，当前 0 落点（所有通用名私有坐标都与仓库名同行）。
- 宽正则 [\w./-]+:\d+ 也匹配 host:8080/12:30 这类非文件冒号数字；整改后私有名行上无此类 token。
- 私有文件名不带行号的叙述不在本守卫范围，由编辑判断 + 既有 REQUIRED/FORBIDDEN 兜底。

## 6. 明确不做
不抬 1.9.14；不新增 examples/ 资产、不动 sync-assets.py 打包面；私有仓库名不进 FORBIDDEN（署名合法）；不为 hypothetical 写法预设计。
```

- [ ] **Step 2: CHANGELOG `[Unreleased]` 新增小节**

在 `CHANGELOG.md` 的 `## [Unreleased]` 区块末尾（`### Documentation — v0.5.0 发版实况与 npm 凭证尾项` 小节之后、`## [0.5.0] - 2026-11-07` 之前）插入：

```markdown
### Fixed — 私有仓库坐标内联化（报告 PRIVATE-COORDS-INLINE）

- **用户翻不到的私有坐标当证据**：7 个技能文件里 34 处技术结论用 pay-plugin/authforge 的 `文件:行号` 作可复核证据（如 `PayPlugin.cc:107`、`tests/CMakeLists.txt:46`、`apps/server/config/config.json:127-134`），用户拿不到这两个私有仓库，照坐标翻不到会把整段结论一起弃用。现外科手术式剥离全部 34 处（30 处与仓库名同行 + 4 处裸坐标：plugin:228/238 的 `PayPlugin.cc:NN`、monitoring:97 的 `PayAuthMetrics.h/.cc`），技术结论交内联样例或同行 drogon 源坐标自证，仓库名降为"落地经验"署名；同行的 drogon 坐标（`HttpAppFrameworkImpl.cc:631-686`、`Hodor.cc:76-80`、官方 `examples/redis_cache/test/test_main.cc:1`）与 REQUIRED needle（`find_package(Drogon CONFIG REQUIRED)` 等）原样保留。
- **新增两层坐标守卫**（`tests/test_skills_facts.py`，独立于既有 33/46/3 三表）：①私有名同行 + 非 drogon 源坐标即红（allowlist 放行 5 basename + 1 官方示例全路径）；②特征私有 basename `PayPlugin.cc`/`TestConfigHelper.h`/`PayAuthMetrics.cc`/`PayAuthMetrics.h` 带坐标 anywhere 即红（denylist，已对 tag clone 核实 drogon 全树 0 命中、无碰撞），兜住同行无仓库名的裸坐标。数量 canary 锁死 5/1/4，合成正对照 6 条放行、反对照 9 条红；整改后对 HEAD 两层均 0 命中。通用名裸坐标（无仓库名且与 drogon 同名）的固有边界如实登记在报告 §5（当前 0 落点）。
```

- [ ] **Step 3: Commit（含设计与计划文档）**

```bash
git add docs/PRIVATE-COORDS-INLINE.md CHANGELOG.md docs/superpowers/specs/2026-11-10-private-coords-inline-design.md docs/superpowers/plans/2026-11-10-private-coords-inline.md
git commit -m "docs: 私有坐标内联化证据报告 + CHANGELOG [Unreleased] 登记 + 设计/计划"
```

---

## Task 4: 资产传播 + 全门禁

**Files:**
- Modify（由脚本传播）: `src/drogon_plugin/drogon_plugin_assets/skills/**`、`npm/assets/skills/**`

- [ ] **Step 1: 传播资产到两个镜像（不能只跑 --check）**

Run:
```bash
python scripts/sync-assets.py
node scripts/sync-assets.mjs
```
Expected: 两脚本把改动的 7 个技能文件同步进 `src/drogon_plugin/drogon_plugin_assets/`（PyPI）与 `npm/assets/`（npm），无报错。

- [ ] **Step 2: 全门禁**

Run（逐条，全部应绿）：
```bash
python scripts/gen-host-artifacts.py --check
python scripts/check-consistency.py
python scripts/sync-assets.py --check
node scripts/sync-assets.mjs --check
python -m pytest tests/
```
Expected:
- `gen-host-artifacts.py --check`：绿（CLAUDE.md 本轮不改，宿主产物无需重生成）。
- `check-consistency.py`：绿（含 CHANGELOG 归档项；[Unreleased] 新小节不影响"当前版本已归档"）。
- 两个 `sync-assets --check`：绿（Step 1 已传播）。
- `pytest tests/`：全绿（含新增 4 个坐标用例 + HEAD 回归）。

- [ ] **Step 3: 若有门禁红，修复后重跑；全绿后 Commit**

```bash
git add src/drogon_plugin/drogon_plugin_assets npm/assets
git commit -m "chore: 同步私有坐标整改到 PyPI/npm 资产镜像，全门禁绿"
```

（若 Step 2 暴露需改源文件的问题，先修源、重跑 Step 1 传播，再 commit；不得只改镜像。）

---

## Task 5: 多评审子代理对撞 + 交付

**Files:** 无新改动（评审）；交付 = push 分支 + 开 PR。

- [ ] **Step 1: 派 3 个评审子代理（并行）**

按用户 PR 节奏，推分支/开 PR 前先跑多评审子代理对撞，三个维度：
1. **守卫方向**：allowlist/denylist 是否真能抓私有坐标、放行 drogon 源；canary 是否锁死；正反对照是否覆盖裸坐标/通用名/无扩展名；有无"删一条只是少拦一条不变红"的退化。
2. **文档声明对撞**：报告 §2 处置表 / §4 实测数字 / CHANGELOG 文案逐条与代码/测试证据对撞（34 坐标、30+4、allowlist 5+1、denylist 4、9 放行），不得把意图当事实。
3. **坐标取证**：保留的 drogon 坐标是否真在 tag v1.9.13 存在；被剥的是否确属私有；denylist 4 basename 是否 drogon 全树 0 命中；REQUIRED needle 是否全保住。

处置每条发现（修代码/修文档/登记残余），重跑 Task 4 门禁确认仍绿。

- [ ] **Step 2: 推分支 + 开 PR（合并归用户）**

```bash
git push -u origin <branch>
gh pr create --title "fix: 私有仓库坐标内联化 + 两层坐标守卫" --body "$(cat <<'EOF'
## Summary
- 剥离 7 个技能文件 34 处私有仓库（pay-plugin/authforge）文件:行号 坐标，技术结论内联自证或换 drogon 源坐标，仓库名降为署名。
- 新增两层坐标守卫（allowlist 5+1 / denylist 4），独立于既有 33/46/3 三表；整改后对 HEAD 0 命中。
- 报告 docs/PRIVATE-COORDS-INLINE.md + CHANGELOG [Unreleased]；资产双镜像已传播，全门禁绿。

## Test plan
- [x] python -m pytest tests/（含新增 4 坐标用例 + HEAD 回归）
- [x] gen-host-artifacts.py --check / check-consistency.py / sync-assets.py --check / sync-assets.mjs --check
- [x] 多评审子代理对撞（守卫方向 / 声明对撞 / 坐标取证）
EOF
)"
```

**纪律**：合并归用户；任何 `--admin` 绕过评审需用户每次显式点名授权。**不推 tag、不发 PyPI/npm**（不可逆，需单独显式确认）。

---

## Self-Review（写计划后自查，已执行）

**1. Spec coverage：**
- §2 两决策 → Task 1（守卫）+ Task 2（去坐标保署名）。✓
- §3 逐文件 34 坐标 → Task 2 Step 3–7 逐条编辑（plugin 13/test 8/cmake 6/monitoring 3/redis 1/rate 1/setup 2 = 34）。✓
- §4 三整改手法 → 编辑里"删坐标/保 drogon/降署名"逐条体现。✓
- §5.2 机制 + §5.3 allowlist + §5.4 canary/正反对照 → Task 1 代码与测试。✓
- §5.5 三表不变 + Finding F needle → Task 1 Step 5 + Task 2 Step 5/8。✓
- §6 交付 6 步 → Task 3（报告/CHANGELOG）+ Task 4（传播/门禁）+ Task 5（评审/PR）。✓
- §8 验收 → Task 2 Step 8/9 + Task 4 Step 2。✓

**2. Placeholder scan：** 无 TBD/TODO；每个代码步给完整代码；31 条编辑给精确 old→new；报告骨架标明"按实测填表"是渲染指令而非占位（数据已在 Task 2 测量步骤产出）。✓

**3. Type consistency：** `_coord_problems`/`_is_verifiable_drogon_source`/`PRIVATE_SOURCE_BASENAMES`/`DROGON_SOURCE_BASENAMES`/`DROGON_SOURCE_PATHS`/`_PRIVATE_COORD`/`_COORD_TOKEN`/`_PRIVATE_REPO_NAMES` 在 Task 1 定义、Task 2 回归用例与测量脚本一致引用；canary 数量 5/1/4 与常量定义一致。✓