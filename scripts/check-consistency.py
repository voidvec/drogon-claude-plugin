#!/usr/bin/env python3
"""跨产物一致性门禁 —— 纯标准库,无第三方依赖。

仓库已经用「`VERSION` 单一来源 + 生成器 `--check`」锁住了版本类产物;本脚本把同一种
思路扩展到**生成器覆盖不到的那些约束**:技能清单与计数、双语 README、两个 CLI 的能力
契约、两份资产同步器的常量等价、以及"代码里不得再出现硬编码技能数"。

为什么需要它:这些约束此前只存在于人的记忆与散文里,漂移了没有任何信号
(实测:技能数 `22` 曾在 7 处常量 + 34 处文案中硬编码;SKILL.md 的 `version` 字段
漂移成两套值且无测试引用)。

用法:
    python scripts/check-consistency.py          # 人类可读报告,不一致退出码 1
    python scripts/check-consistency.py --json   # 机器可读
    # pytest 侧的等价入口见 tests/test_hosts.py::test_cross_artifact_consistency

约定:每个 check 返回问题字符串列表(空 = 通过)。新增约束请加一个 `_check_*` 函数
并登记到 CHECKS。
"""
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# 事实源读取
# ---------------------------------------------------------------------------

RAW_SKILL_TOKEN = re.compile(r"\bdrogon-(?:create|gen|setup)-[a-z0-9-]+\b")
# 技能表格的一行:首列是反引号包起来的技能名(排除宿主/参数等其它表格)
SKILL_TABLE_ROW = re.compile(r"^\|\s*`drogon-[a-z0-9-]+`\s*\|")


def skills() -> "list[str]":
    """技能清单唯一事实源:skills/ 目录。"""
    d = REPO / "skills"
    return sorted(p.name for p in d.iterdir() if p.is_dir()) if d.is_dir() else []


def read(rel: str) -> str:
    return (REPO / rel).read_text(encoding="utf-8", errors="ignore")


def capabilities() -> dict:
    return json.loads(read("scripts/plugin-capabilities.json"))


# ---------------------------------------------------------------------------
# 断言辅助
# ---------------------------------------------------------------------------


def _counts_in_text(text: str, patterns: "list[str]") -> "list[tuple[str, int]]":
    """返回 (匹配原文, 数字) 列表,用于把文档里的计数与事实源比对。"""
    found = []
    for pat in patterns:
        for m in re.finditer(pat, text):
            found.append((m.group(0).strip(), int(m.group(1))))
    return found


SKILL_COUNT_PATTERNS = (
    r"(\d+)\s*code-generation skills",
    r"(\d+)\s*skills\b",
    r"(\d+)\s*个代码生成技能",
    r"(\d+)\s*个技能",
    r"`skills/`\s*[（(](\d+)",
    r"skills\s*[（(](\d+)",
    r"code-generation skills\s*\((\d+)\)",
    r"代码生成技能\s*[（(](\d+)",
)
HOOK_COUNT_PATTERNS = (
    r"(\d+)\s*automatic detection hooks",
    r"(\d+)\s*hooks\b",
    r"(\d+)\s*个[^，。\n]{0,8}钩子",
)
EXPECTED_HOOK_COUNT = 2

# 文档里允许出现技能数的地方(其余文件不校验,如 CHANGELOG 的历史叙述)
COUNTED_DOCS = ("README.md", "README.zh-CN.md", "npm/README.md", "npm/README.zh-CN.md")


# ---------------------------------------------------------------------------
# 各项检查
# ---------------------------------------------------------------------------


def _check_readme_counts() -> "list[str]":
    """4 份 README 里的技能数/钩子数必须等于事实源(数字可以由人生成,但必须被校验)。"""
    problems = []
    n_skills = len(skills())
    for rel in COUNTED_DOCS:
        if not (REPO / rel).is_file():
            problems.append(f"{rel}: 文件缺失")
            continue
        text = read(rel)
        for raw, value in _counts_in_text(text, SKILL_COUNT_PATTERNS):
            if value != n_skills:
                problems.append(f"{rel}: “{raw}” 与事实源技能数 {n_skills} 不一致")
        for raw, value in _counts_in_text(text, HOOK_COUNT_PATTERNS):
            if value != EXPECTED_HOOK_COUNT:
                problems.append(f"{rel}: “{raw}” 与事实源钩子数 {EXPECTED_HOOK_COUNT} 不一致")
    return problems


def _skill_table_rows(rel: str) -> "list[str]":
    return [line for line in read(rel).splitlines() if SKILL_TABLE_ROW.match(line)]


def _check_readme_skill_coverage() -> "list[str]":
    """双语主 README 必须覆盖每个技能,且不得引用不存在的技能名。"""
    problems = []
    actual = set(skills())
    for rel in ("README.md", "README.zh-CN.md"):
        text = read(rel)
        referenced = set(RAW_SKILL_TOKEN.findall(text))
        missing = sorted(actual - referenced)
        unknown = sorted(referenced - actual)
        if missing:
            problems.append(f"{rel}: 未提及技能 {missing}")
        if unknown:
            problems.append(f"{rel}: 引用了不存在的技能名 {unknown}")
    return problems


def _check_readme_bilingual_parity() -> "list[str]":
    """中英 README 的技能表格行数必须一致,且主 README 至少要有完整的技能表。

    注意:npm 的两份 README 只描述安装器、**不含**技能表格(0 行 == 0 行),
    因此这对它们恒真;真正起作用的是仓库根那两份(每份应含全部技能行)。
    """
    problems = []
    for en, zh in (("README.md", "README.zh-CN.md"), ("npm/README.md", "npm/README.zh-CN.md")):
        if not (REPO / en).is_file() or not (REPO / zh).is_file():
            problems.append(f"{en} / {zh}: 文件缺失")
            continue
        a, b = _skill_table_rows(en), _skill_table_rows(zh)
        if len(a) != len(b):
            problems.append(f"{en}({len(a)} 行) 与 {zh}({len(b)} 行) 技能表格行数不一致")
    # 主 README 必须给出完整技能表(防止"表格被整体删掉后两侧都是 0 行"的假绿)
    n_skills = len(skills())
    for rel in ("README.md", "README.zh-CN.md"):
        n_rows = len(_skill_table_rows(rel))
        if n_rows < n_skills:
            problems.append(f"{rel}: 技能表格仅 {n_rows} 行 < 技能数 {n_skills}")
    return problems


def _parse_quoted(text: str) -> "list[str]":
    return re.findall(r"['\"]([^'\"]+)['\"]", text)


def _check_sync_assets_parity() -> "list[str]":
    """两份资产同步器的 ASSETS/FILES/IGNORE_DIRS 必须等价(实现可平行,常量不可漂移)。"""
    py = read("scripts/sync-assets.py")
    mjs = read("scripts/sync-assets.mjs")
    problems = []

    specs = (
        ("ASSETS", r"^ASSETS = \(([^)]*)\)", r"const ASSETS = \[([^\]]*)\]"),
        ("FILES", r"^FILES = \(([^)]*)\)", r"const FILES = \[([^\]]*)\]"),
        ("IGNORE_DIRS", r"^IGNORE_DIRS = \{([^}]*)\}", r"const IGNORE_DIRS = new Set\(\[([^\]]*)\]\)"),
    )
    for name, py_pat, mjs_pat in specs:
        mp = re.search(py_pat, py, re.M)
        mm = re.search(mjs_pat, mjs, re.M)
        if not mp or not mm:
            problems.append(f"sync-assets: 无法解析 {name}(py={bool(mp)}, mjs={bool(mm)})")
            continue
        py_vals, mjs_vals = set(_parse_quoted(mp.group(1))), set(_parse_quoted(mm.group(1)))
        if py_vals != mjs_vals:
            problems.append(
                f"sync-assets: {name} 不一致 — py={sorted(py_vals)} mjs={sorted(mjs_vals)}"
            )
    return problems


def _pypi_commands() -> "list[str]":
    sys.path.insert(0, str(REPO / "src"))
    from drogon_plugin import cli  # noqa: PLC0415

    return cli.available_commands()


def _npm_commands() -> "list[str]":
    """从 npm CLI 的 COMMANDS 常量提取(单一来源,不依赖 node 运行时)。"""
    m = re.search(r"const COMMANDS = \[([^\]]*)\]", read("npm/bin/cli.js"))
    return sorted(_parse_quoted(m.group(1))) if m else []


def _check_cli_capability_contract() -> "list[str]":
    """两个 CLI 的真实命令集合必须与 plugin-capabilities.json 的声明完全一致。"""
    problems = []
    decl = capabilities()
    try:
        actual = {"pypi": sorted(_pypi_commands()), "npm": _npm_commands()}
    except Exception as e:  # pragma: no cover - 环境异常
        return [f"cli 能力: 无法读取实现({e})"]

    for cli_name in ("pypi", "npm"):
        declared = sorted(decl["cli"][cli_name]["commands"])
        if actual[cli_name] != declared:
            problems.append(
                f"cli 能力: {cli_name} 实际 {actual[cli_name]} != 声明 {declared}"
                "(能力差异必须在 plugin-capabilities.json 显式登记)"
            )

    # 已知缺口声明必须与真实差集吻合 —— 差距是评审过的决定,不是意外
    gap = sorted(set(actual["pypi"]) - set(actual["npm"]))
    declared_gap = sorted(decl.get("known_gaps", {}).get("npm", {}).get("commands", []))
    if gap != declared_gap:
        problems.append(f"cli 能力: npm 相对 pypi 的真实缺口 {gap} != 声明缺口 {declared_gap}")
    return problems


def _check_no_hardcoded_skill_count() -> "list[str]":
    """两个 CLI 里不得再出现硬编码技能数,且必须真的调用各自的枚举助手。

    两类失败都要抓:
      1. 负向 —— 仍有字面量或残留常量(如 `EXPECTED_SKILLS = 22`);
      2. 正向 —— 删掉常量后**忘了同步引用点**(例如常量没了、日志行还写着
         `${EXPECTED_SKILLS}`,这会让 install 抛 ReferenceError,而只查字面量
         的检查会静默通过)。回归来源:本轮真实踩到过。
    """
    problems = []
    clis = (("src/drogon_plugin/cli.py", r"_bundled_skill_count\("),
            ("npm/bin/cli.js", r"bundledSkillCount\("))
    forbidden = (
        (r"EXPECTED_SKILLS\s*[:=]\s*\d+", "技能数应实枚举,不得定义数字常量"),
        (r"\bEXPECTED_SKILLS\b", "该常量已移除:技能数须由 assets 目录实枚举"),
        (r"!=\s*22\b", "技能数不应与字面量 22 比较"),
        (r"-eq\s+22\b", "技能数不应与字面量 22 比较"),
    )
    for rel, helper in clis:
        if not (REPO / rel).is_file():
            continue
        text = read(rel)
        for pat, why in forbidden:
            m = re.search(pat, text)
            if m:
                problems.append(f"{rel}: 命中硬编码 -- “{m.group(0)}”({why})")
        # 正向:必须存在"实枚举"的入口,避免"删了常量但没接上枚举"这种退化
        if not re.search(helper, text):
            problems.append(f"{rel}: 未发现实枚举入口 {helper} —— 技能数可能已失去事实源")

    for rel in ("scripts/dev-smoke-test.py", "scripts/dev-smoke-test.mjs",
                "scripts/gen-host-artifacts.py", ".github/workflows/ci.yml"):
        if not (REPO / rel).is_file():
            continue
        text = read(rel)
        for pat, why in (forbidden[2], forbidden[3]):
            m = re.search(pat, text)
            if m:
                problems.append(f"{rel}: 命中硬编码 -- “{m.group(0)}”({why})")
    return problems


SESSION_START_SOURCES = {"startup", "resume", "clear", "compact", "fork"}


def _check_session_start_matcher_covers_resume() -> "list[str]":
    """SessionStart 的 matcher 必须覆盖全部已知来源。

    来源取值集合为 startup/resume/clear/compact/fork(Claude 与 Codex 一致)。
    弱子串断言会被 `startup|resume|clear|compact` 这类"缺 fork"枚举蒙过 ——
    漏任一来源即"该场景不注入规则"的静默失效,故按集合覆盖校验(或 `*`)。
    """
    data = json.loads(read("hooks/hooks.json"))
    entries = data.get("hooks", {}).get("SessionStart", [])
    if not entries:
        return ["hooks/hooks.json: 缺少 SessionStart 事件"]
    problems = []
    for entry in entries:
        matcher = entry.get("matcher", "")
        covered = SESSION_START_SOURCES if matcher == "*" else set(matcher.split("|"))
        missing = sorted(SESSION_START_SOURCES - covered)
        if missing:
            problems.append(
                f"hooks/hooks.json: SessionStart matcher “{matcher}” 未覆盖来源 {missing}"
                "(对应场景下规则不会注入)"
            )
    return problems


def _check_uninstall_kinds_covered() -> "list[str]":
    """HOSTS 里出现的每一种宿主类型(可为复合 kind,如 skills+instruction)都必须有卸载动作。

    回归来源:`bundle` 曾不在任何 if 分支里,导致 `uninstall --host claude` 静默空操作。
    """
    sys.path.insert(0, str(REPO / "src"))
    from drogon_plugin import cli  # noqa: PLC0415

    registered = set(cli.uninstall_component_kinds())
    problems = []
    for host, conf in cli.HOSTS.items():
        for part in conf["kind"].split("+"):
            if part not in registered:
                problems.append(
                    f"宿主 {host} 的类型组件 “{part}” 未登记卸载动作"
                    "(新增宿主类型时必须同步 _UNINSTALL_COMPONENT_ACTIONS)"
                )
    return problems


def _check_rule_files_have_no_control_chars() -> "list[str]":
    """规则文件不得含 C0 控制字符(\\t \\n \\r 除外)。

    session-start 会把规则文件内容内联进 JSON;含其它控制字符会产出非法 JSON,
    导致宿主解析失败、规则注入静默失效。
    """
    problems = []
    for rel in ("CLAUDE.md", "AGENTS.md", "GEMINI.md"):
        if not (REPO / rel).is_file():
            continue
        text = read(rel)
        bad = sorted({c for c in text if ord(c) < 0x20 and c not in "\t\n\r"})
        if bad:
            problems.append(f"{rel}: 含控制字符 {[hex(ord(c)) for c in bad]}")
    return problems


def _check_npm_managed_entries_match_sync() -> "list[str]":
    """npm CLI 回退模式的受管条目必须与 npm 侧资产同步器的 ASSETS+FILES 等价。"""
    npm_src = read("npm/bin/cli.js")
    m = re.search(r"const MANAGED_ENTRIES = new Set\(\[([\s\S]*?)\]\)", npm_src)
    if not m:
        return ["npm/bin/cli.js: 未找到 MANAGED_ENTRIES(回退模式的受管资产清单)"]
    managed = set(_parse_quoted(m.group(1)))

    mjs = read("scripts/sync-assets.mjs")
    declared = set()
    for pat in (r"const ASSETS = \[([^\]]*)\]", r"const FILES = \[([^\]]*)\]"):
        mm = re.search(pat, mjs)
        if not mm:
            return [f"scripts/sync-assets.mjs: 无法解析 {pat}"]
        declared |= set(_parse_quoted(mm.group(1)))

    if managed != declared:
        return [
            f"npm/bin/cli.js MANAGED_ENTRIES 与 sync-assets.mjs 的 ASSETS+FILES 不一致:"
            f" 仅 npm 有 {sorted(managed - declared)};仅同步器有 {sorted(declared - managed)}"
        ]
    return []


def _check_extensionless_hook_scripts_are_lf_pinned() -> "list[str]":
    """无扩展名的钩子脚本必须被 .gitattributes 显式固定为 LF。

    按扩展名的规则(`*.sh`/`*.py`)覆盖不到 `session-start` / `post-tool-use`;
    缺少声明时,Windows 在 ``core.autocrlf=true``(Git for Windows 默认)下克隆会得到
    CRLF,而 bash 会把 `\\r` 当成命令的一部分 → 钩子静默失效。
    """
    ga = read(".gitattributes")
    problems = []
    for rel in ("hooks/session-start", "hooks/post-tool-use"):
        if not re.search(rf"^{re.escape(rel)}\s+.*\beol=lf\b", ga, re.M):
            problems.append(
                f".gitattributes: 缺少 “{rel} … eol=lf”"
                "(无扩展名脚本不会被 *.sh 规则覆盖,Windows 克隆可能变 CRLF)"
            )
    return problems


def _check_hook_rules_have_ids() -> "list[str]":
    """钩子规则必须带稳定 rule_id,且 ID 唯一(报告与测试据此精确引用)。"""
    sys.path.insert(0, str(REPO / "hooks"))
    import importlib.util  # noqa: PLC0415

    # 不为被加载的模块写字节码缓存(避免在仓库里生成 __pycache__ 噪声)
    sys.dont_write_bytecode = True

    spec = importlib.util.spec_from_file_location(
        "posttooluse_consistency", REPO / "hooks" / "posttooluse.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    problems = []
    ids = [r.rule_id for r in mod.ALL_RULES]
    # 空集也是失败——否则规则库被误清空时,"没有重复"会静默通过(假绿)
    if not ids:
        return ["hooks/posttooluse.py: 规则库为空 —— 扫描器已失效"]
    dups = sorted({i for i in ids if ids.count(i) > 1})
    if dups:
        problems.append(f"hooks/posttooluse.py: rule_id 重复 {dups}")
    if any(not i for i in ids):
        problems.append("hooks/posttooluse.py: 存在空 rule_id")
    # 每条规则必须能被人读懂:message 与 guide 不可为空
    for r in mod.ALL_RULES:
        if not r.message or not r.guide:
            problems.append(f"hooks/posttooluse.py: {r.rule_id or '<no id>'} 缺 message/guide")
    return problems


def _check_marketplace_local_sources() -> "list[str]":
    """本地 marketplace source 必须以 ./ 开头(官方文档硬约束,回归 R1)。

    Claude 系条目 source 是字符串,Codex 系是 {source:"local", path};两种形态
    都盖。`.` / 绝对路径形态会让宿主解析失败,且只在使用者安装时才暴露。
    """
    problems = []
    for rel in (".claude-plugin/marketplace.json", ".agents/plugins/marketplace.json"):
        data = json.loads(read(rel))
        for e in data.get("plugins", []):
            src = e.get("source")
            value = src if isinstance(src, str) else (
                src.get("path") if isinstance(src, dict) and src.get("source") == "local" else None
            )
            if value is not None and not value.startswith("./"):
                problems.append(
                    f"{rel}: 插件 {e.get('name', '?')} 的本地 source {value!r} 未以 ./ 开头"
                    '(官方文档:"Local plugin sources must start with ./")'
                )
    return problems


def _check_npm_hooks_keep_exec_bit() -> "list[str]":
    """npm 复制资产后必须给钩子脚本补可执行位(回归 P2)。

    fs.copyFileSync 不携带源 mode;Linux/macOS 上 hooks/session-start 等
    落地即失去 x 位 → 宿主执行 command 时 Permission denied,钩子静默失效。
    静态守卫:四个钩子文件都出现在 chmod 逻辑覆盖的文件清单里。
    """
    src = read("npm/bin/cli.js")
    if "chmodSync" not in src:
        return ["npm/bin/cli.js: 复制资产后无 chmodSync —— POSIX 下钩子脚本丢可执行位(P2)"]
    problems = []
    for rel in ("run-hook.cmd", "session-start", "post-tool-use", "posttooluse.py"):
        if rel not in src:
            problems.append(f"npm/bin/cli.js: 钩子 chmod 清单缺 {rel}")
    return problems


CHECKS = (
    ("README 计数与事实源一致", _check_readme_counts),
    ("双语 README 技能覆盖完整", _check_readme_skill_coverage),
    ("双语 README 结构对齐", _check_readme_bilingual_parity),
    ("双资产同步器常量等价", _check_sync_assets_parity),
    ("CLI 能力契约与实现一致", _check_cli_capability_contract),
    ("无硬编码技能数量", _check_no_hardcoded_skill_count),
    ("钩子规则 ID 唯一", _check_hook_rules_have_ids),
    ("SessionStart matcher 覆盖全部来源", _check_session_start_matcher_covers_resume),
    ("无扩展名钩子脚本固定 LF", _check_extensionless_hook_scripts_are_lf_pinned),
    ("宿主类型均有卸载动作", _check_uninstall_kinds_covered),
    ("规则文件无控制字符", _check_rule_files_have_no_control_chars),
    ("npm 受管条目与同步器等价", _check_npm_managed_entries_match_sync),
    ("本地 marketplace source 以 ./ 开头", _check_marketplace_local_sources),
    ("npm 钩子保留可执行位", _check_npm_hooks_keep_exec_bit),
)


def run_checks() -> "list[str]":
    """跑全部检查,返回 flatten 后的问题列表(空 = 全部通过)。"""
    problems = []
    for name, fn in CHECKS:
        try:
            problems.extend(fn())
        except Exception as e:  # 检查自身异常也算失败,避免静默跳过
            problems.append(f"[{name}] 检查执行异常: {type(e).__name__}: {e}")
    return problems


def _utf8_stdio() -> None:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass


def main() -> int:
    _utf8_stdio()
    problems = run_checks()
    if "--json" in sys.argv:
        print(json.dumps({"ok": not problems, "problems": problems}, ensure_ascii=False, indent=2))
        return 1 if problems else 0
    if problems:
        print("❌ 跨产物一致性检查未通过:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print(f"✅ 跨产物一致性检查通过({len(CHECKS)} 项)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
