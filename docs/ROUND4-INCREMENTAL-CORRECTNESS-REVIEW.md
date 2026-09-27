# 第四轮评审报告 — v0.4.0 增量对抗审查与回归对撞

- 日期：2026-09-27 · 对象：master `7d0bce0`（v0.4.0 后 10 提交，12 文件 +1029/-108：批次④、L7/codex/V6-V8 文档）
- 方法：四维度并行只读子代理（规范性 A / 宿主兼容 B / 平台兼容 C / 功能正确 D）+ 主代理逐条实证（复现命令/代码路径核对/独立计时）。
- 纪律：第三轮已结案项（matcher NotebookEdit、`onTimeout` 误报、L4 静默跳过、残余 TOCTOU、`--target=DIR` 等号形态）不炒冷饭；本报告**只诊断，不整改**。

## 0. 上轮闭环裁定

批次①–⑤ + PR #3/#4 的声称项全部复核成立（版本 13 处一致、资产双 `--check` 绿、CHANGELOG [Unreleased] 逐条能在代码/测试中找到锚点：130 回滚、bundle 改名备份、账本原样、退码 2、`_escapes_workspace`、裸 timeout 正负例、"(包残缺)"、codex `add` 漂移守卫）。套件 185 passed / 2 skipped 复跑绿。**但增量新代码本身引入 4 项高危**（见 §1），且 **V7 结案结论被部分动摇**（§2-F8）。

## 1. 新发现（按严重度）

### 高（可用性/数据安全，建议第一批全修）

**F1 — CPP.007 / CSP.001 二次回归放大（ReDoS）** `hooks/posttooluse.py:88-90,121`
主代理独立复现：`"->sendRequest("×20000`（280KB 无闭合括号）→ `re.search` **42.1s**；`"{{"×50000`（100KB）→ **61.5s**。根因：L6 加的 `[^,)]+` 放行 `(`，每个锚点位独立 O(n) 回溯 → 整体 O(n·k) 平方级。钩子虽 never-blocks，但会把每次 Edit 卡死、`--scan` CI 同死。方向：`[^,()]` 并加长度上界（如 `{1,500}`）；CSP 内容类同样加上界；补计时守卫测试（阈值 1s）。
（来源 D=N4D-1，实证复现。）

**F2 — rename 失败时回滚反而摧毁在用旧 bundle** `cli.py:508-517,443-444`
主代理 monkeypatch `os.replace` 抛 WinError 32 复现：`bundle_touched=True` 在改名**之前**置位；另一进程 cwd 位于 `.drogon-plugin/`（Windows 常态）→ 改名失败、备份不存在 → 回滚仍无条件 `rmtree(root)` → 在用旧 bundle 哨兵文件消失，"失败原样恢复"承诺落空。方向：改名失败即整体失败返回（root 未动过，无须清）；仅当 `bundle_backup is not None`（改名确实成功）才 rmtree 半成品 root。
（来源 C=N4C-1，实证复现。）

**F3 — 恢复失败时回滚销毁唯一备份** `cli.py:445-452`
代码核对：恢复分支 `os.replace(backup→root)` 抛错走 `except: pass` 后，末尾"清理残留备份"的 `rmtree(bundle_backup)` 恰好在**恢复失败**时到达——把最后一份旧 bundle 也删了，双目录皆失。方向：恢复失败保留备份并打印路径告警；仅恢复成功或从未改名才删。
（来源 D=N4C-1 次生/D=N4D-3，代码路径确认。）

**F4 — 技能目录重装半途失败：用户自有内容丢失 + 半成品孤儿** `cli.py:537-549`
代码核对 + D 实测：`dest.exists()→rmtree(dest)→copytree` ——①同名 `drogon-*` 目录里用户手改内容先删无备份，失败后回滚只删不还原；②copytree 中途失败（磁盘满）时 dest **不在 written**（append 在 copytree 之后），半成品目录残留成孤儿——正是 L5 要消灭的形态，现有 flaky 注入在 real copytree 前抛，恰好绕开这两个通道。方向：dest 先记入 written 再 copytree；旧 dest 走与 bundle 同款的改名备份。
（来源 D=N4D-2。）

### 中

**F5 — npm uninstall 先删 bundle 后判混合（顺序反了）** `npm/bin/cli.js cmdUninstall`
代码核对：混合宿主项目（py 装 claude+agents）跑 npm uninstall → `.drogon-plugin` 已删，v3 戳却保留且 hosts 仍含 claude/zcode → 戳与产物互相说谎，py verify 返回 0。方向：先判 pureBundle——纯 bundle 才连 bundle+戳一起清；混合则 bundle 也不动、只警告交 PyPI CLI。（L1 正向对照测试需同步改造。）
（来源 D=N4D-4。）

**F6 — py `upgrade` 对 npm 装的项目退化为全宿主安装** `cli.py:736-752`
代码核对：R4 收敛范围只看 v3 戳；npm 装的项目无 v3 戳 → `stamped=[]` → ALL_HOSTS 落下 8 家产物（B 实测 66+ 文件）。方向：无 v3 戳但检出 bundle 布局（v2 戳 `source:npm`）时，范围收敛为 claude,zcode。
（来源 B=N4B-1。）

**F7 — 非 UTF-8 用户文件仍有三处泄漏** `cli.py:290-300(legacy)、322-327(_write_instruction_file)、633-641(_host_artifact_ok)`
代码核对：上轮只修了卸载剥段路径；GBK 化的 `AGENTS.md`/`CLAUDE.md` 可让 ①verify 直接 traceback ②legacy uninstall 崩溃 ③install 整批失败 rc=1。方向：统一 `(OSError, UnicodeDecodeError)` → 判"不可读，保守跳过/告警"。
（来源 C=N4C-3。）

**F8 — V7 重开：PyPI 链路 Linux 执行位存疑** `src/drogon_plugin/_copy_assets`/发布链
C 声称构造 0o755 wheel 条目经 pip 系安装后丢位。**主代理部分存疑**：pip 用 `zipfile.extractall`（保留 external_attr 权限），与 `installer`/distlib 行为不同，且 C 在 Windows 上无法真验。ubuntu CI 构建 wheel 时 git 100755 是否贯穿到 site-packages→项目落地，必须**在 ubuntu runner 上实证**而非渠道推断。方向：ci.yml 既有 `pip install dist/*.whl` 集成作业后加一步断言三个钩子文件 x 位（POSIX），实证即结案、失败即补 `_copy_assets` chmod 对齐 npm P2。
（来源 C=N4C-4，登记为 V9。）

**F9 — 崩溃孤儿 `.drogon-plugin.old-<pid>` 永不回收** `cli.py:514`
全仓唯一引用点，install/uninstall/verify 均不扫。kill -9/断电后残留永驻，verify 全绿无人知晓。方向：install 开头回收 mtime 超阈值的 `*.old-*`，或 verify 提示。
（来源 C=N4C-2。）

**F10 — README.zh-CN 宿主矩阵未随 N4/N5 同步** `README.zh-CN.md:28-29,74`
EN 已写 `.qoder/skills`+`.codebuddy/skills`，zh 仍写"落 AGENTS.md｜规则"；CHANGELOG"README 已标注"仅半真。双语矩阵无对拍门禁，14 项 consistency 拦不住。方向：同步三处 + check-consistency 加关键单元格对拍。
（来源 A=N4A-1。）

### 低

**F11 — skipped 记录使 v3 戳永不收敛** `cli.py _prune_stamp/cmd_uninstall`：主代理经 `main()` 复现——用户自有 AGENTS.md 上 codex 装(skipped)→卸载后戳以 `hosts:[],files:[],instruction_files:{AGENTS.md:"skipped"}` 残留在项目里。prune 判据把 skipped 当资产。（B=N4B-2）
**F12 — py verify 技能检查仅目录计数**：空壳技能目录（SKILL.md 被删）仍过；npm 侧反而逐个查 SKILL.md——双端口径不一致，py 应补 per-skill 断言。`.qoder/skills` 与宿主自有技能共存时严格计数使 verify 长期"qoder—"误导（同源语义问题）。（D=N4D-5 / B=N4B-3）
**F13 — Windows 本地生成链写 CRLF**：`gen-host-artifacts.py` write_text 文本模式 → 本机工作树 AGENTS.md 67 处 CRLF，sync copy2 带入 assets；ubuntu CI 重生成故发布无恙，但本机构建的 wheel 带 CRLF 资产。建议生成器显式 `newline="\n"`。（C=N4C-5）
**F14 — 守卫与漂移面**：test_ci_pinning 不认流式 `- {uses:}`（理论漏抓；GH Actions 键名实为大小写敏感，`USES:` 不是合法键，评审的"大小写绕过"前提被主代理证伪）；SHA 与注释无对应性校验；无 dependabot，SHA 静默冻结。（A=N4A-4，部分证伪）
**F15 — 发版语义**：[Unreleased] 含 Added（N4/N5、守卫测试），下次应 **0.5.0**；CHANGELOG 头部"同步四处版本号"措辞落后于 13 处单一来源现实；[Unreleased]→版本小节归档无门禁。（A=N4A-2/N4A-3）

## 2. 实证记录（主代理复现）

| 项 | 方法 | 结果 |
|---|---|---|
| F1 | tempfile 计时 280KB/100KB 病态输入 | 42.1s / 61.5s ✅ |
| F2 | monkeypatch os.replace 抛 errn 32 + cmd_install | 哨兵文件消失、rc=1 ✅ |
| F5/F7/F9 | 代码路径核对（行号见各条） | 与 C/D 结论一致 ✅ |
| F6 | cmd_upgrade 源码 + R4 docstring | npm 项目无 v3 戳→ALL_HOSTS ✅（B 实测 66+ 文件） |
| F11 | 经 `main()` 全流程复现 | 戳残留 `instruction_files:{AGENTS.md:"skipped"}` ✅ |
| 证伪 | GBK 控制台 emoji 崩溃疑云（直调 cmd_install 触发） | 真入口 `main()` 有 `_utf8_stdio` 兜底，产品路径不成立——登记误报 |

## 3. 建议整改序（待确认后开工，全程 TDD）

| 批次 | 项 | 一句话动作 |
|------|----|-----------|
| ① | F1–F4 | 高四连：正则上界化+计时守卫；bundle/技能两条"改名备份"路径的失败分支重构（rename 败即返回、恢复败即保留、dest 先记账再写） |
| ② | F5–F7、F10 | npm 卸载顺序前置判断；upgrade 认 v2 戳收敛；三处 UnicodeDecodeError；zh-CN 矩阵 + 双语对拍门禁 |
| ③ | F8(V9)、F9、F11–F13 | CI ubuntu 执行位断言（实证即结 V7 疑云）；old-* 回收；prune 剔 skipped；py verify per-skill；生成器 LF |
| ④ | F14、F15 | dependabot/注释校验按需；发版走 0.5.0 并修 CHANGELOG 头部措辞 |

> 真机尾项不变：V8 降级观察、GitHub 型 marketplace 解析、N4/N5 桌面核验。
