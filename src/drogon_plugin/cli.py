#!/usr/bin/env python3
"""drogon-claude-plugin — CLI 安装器 v3(PyPI 发行版).

把 drogon 插件资产安装到目标项目,支持多宿主分发(Claude Code / ZCode /
Codex / Cursor / VS Code Copilot / Gemini CLI / Qoder / CodeBuddy / Trae /
通用 .agents),或校验 / 扫描违规 / 升级 / 卸载。

宿主落点(全部有官方文档依据,见 docs/INTEGRATION-REVIEW-v0.3.0.md):
  claude|zcode   → .drogon-plugin/ 自包含目录(v0.2 行为,经宿主 marketplace 注册)
  codex          → AGENTS.md(项目级规则;技能经 codex marketplace 安装本仓库)
  cursor         → .cursor/skills/<skill>/ + .cursor/rules/drogon-plugin.mdc
  copilot|agents → .agents/skills/<skill>/ + AGENTS.md(VS Code 原生发现位置)
  gemini         → GEMINI.md(项目级;技能经 gemini extensions 安装本仓库)
  qoder          → AGENTS.md(Qoder 官方兼容)
  codebuddy      → CODEBUDDY.md(项目指令文件)
  trae           → .trae/skills/<skill>/ + AGENTS.md(Trae 官方兼容;不投 .mdc,见 R10)

安全承诺:
  · 项目自有指令文件(AGENTS.md / GEMINI.md / CODEBUDDY.md)绝不覆盖:
    已存在时默认跳过并打印合并指引;--force-agents 才追加
    <!-- drogon-plugin begin/end --> 标记段;卸载只删标记段。
  · ours-by-name 文件(.cursor/rules/drogon-plugin.mdc 等)只增删自己的名字。
  · 所有删除走安装戳 + 归属签名双保险;拒绝在文件系统根/用户主目录操作。
  · scan 在进程内加载扫描模块,被扫描路径必须解析到项目目录之内。

子命令:
  install   [--target DIR] [--host LIST] [--force-agents]
  verify    [--target DIR]
  upgrade   [--target DIR]
  uninstall [--target DIR] [--host LIST]
  scan      [--target DIR] [--format human|json] [--strict] [PATH...]
  hosts
  version
"""

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path

# 资产在 wheel 内统一放在 ``drogon_plugin_assets/`` 下(见 pyproject.toml data-files)
_ASSETS_PREFIX = "drogon_plugin_assets"
_INSTALL_DIR = ".drogon-plugin"
_LEGACY_STAMP = ".drogon-claude-plugin-installed.json"
_STAMP_V2 = ".drogon-claude-plugin-v2.json"
_STAMP_V3 = ".drogon-plugin-install.json"

_CLAUDE_MD_MARKER = "# Drogon 后端开发规则"
_MARKER_BEGIN = "<!-- drogon-plugin begin -->"
_MARKER_END = "<!-- drogon-plugin end -->"

_EXPECTED_HOOK_FILES = (
    "hooks.json",
    "run-hook.cmd",
    "session-start",
    "post-tool-use",
    "posttooluse.py",
)
_EXPECTED_HOOK_EVENTS = 2

# 技能数量没有常量:单一事实源是随包资产里的 skills/ 目录,一律实枚举(见 _bundled_skill_count)。
# 历史上这里硬编码过 22,导致新增技能需要人工同步 7 处常量 + 若干文档文案。

_REPO_URL = "https://github.com/voidvec/drogon-claude-plugin"

_PKG_VERSION: "str | None" = None

_MARKER_SECTION_RE = re.compile(
    re.escape(_MARKER_BEGIN) + r"[\s\S]*?" + re.escape(_MARKER_END) + r"\n?"
)

# 孤立标记行(只有 begin 没有 end,或反之):用户手改坏时会出现。
# 它们是我们写入的标记,可以安全清理后重写一段完整的。
_MARKER_LINE_RE = re.compile(
    r"^[ \t]*(?:" + re.escape(_MARKER_BEGIN) + r"|" + re.escape(_MARKER_END) + r")[ \t]*$\n?",
    re.M,
)


# ---------------------------------------------------------------------------
# 宿主注册表
# ---------------------------------------------------------------------------

# 指令文件 = 用户可能自有的项目级文件(三态保护);规则文件 = ours-by-name
HOSTS = {
    "claude": {"kind": "bundle"},
    "zcode": {"kind": "bundle"},
    "codex": {"kind": "instruction", "file": "AGENTS.md"},
    "cursor": {
        "kind": "skills+rulefile",
        "skills_dir": ".cursor/skills",
        "rule_file": ".cursor/rules/drogon-plugin.mdc",
    },
    "copilot": {"kind": "skills+instruction", "skills_dir": ".agents/skills", "file": "AGENTS.md"},
    "agents": {"kind": "skills+instruction", "skills_dir": ".agents/skills", "file": "AGENTS.md"},
    "gemini": {"kind": "instruction", "file": "GEMINI.md"},
    "qoder": {"kind": "instruction", "file": "AGENTS.md"},
    "codebuddy": {"kind": "instruction", "file": "CODEBUDDY.md"},
    # 回归(R10):Trae 官方规则是 .trae/rules/*.md,文档零处 .mdc —— 旧落点
    # drogon-plugin.mdc 是宿主不读的 inert 文件。改走 skills + AGENTS.md 双通道。
    "trae": {"kind": "skills+instruction", "skills_dir": ".trae/skills", "file": "AGENTS.md"},
}

# `all` 的互斥规则(评审 #7):claude/zcode/codex/gemini/cursor 已有技能分发通道,
# 不落 .agents/skills,避免 ZCode/VS Code 重复发现同名技能。
ALL_HOSTS = ["claude", "zcode", "codex", "cursor", "gemini", "qoder", "codebuddy", "trae"]

# 卸载时可能需要清理空目录的候选(仅当为空时删除)
_OUR_DIR_CANDIDATES = [
    ".cursor/skills",
    ".cursor/rules",
    ".cursor",
    ".agents/skills",
    ".agents",
    ".trae/skills",
    ".trae/rules",  # 旧版 .mdc 落点(R10 已撤),空目录顺手清理
    ".trae",
]


def _version() -> str:
    global _PKG_VERSION
    if _PKG_VERSION is None:
        try:
            from importlib.metadata import version

            _PKG_VERSION = version("drogon-claude-plugin")
        except Exception:
            _PKG_VERSION = "dev"
    return _PKG_VERSION


def _find_assets() -> Path:
    here = Path(__file__).resolve().parent
    return here / _ASSETS_PREFIX


# ---------------------------------------------------------------------------
# 技能数量:单一事实源 = 资产目录里的 skills/(禁止硬编码)
# ---------------------------------------------------------------------------


def _skill_count_of(skills_dir: Path) -> int:
    if not skills_dir.is_dir():
        return 0
    return len([d for d in skills_dir.iterdir() if d.is_dir()])


def _bundled_skill_count() -> int:
    """随包技能数(实枚举)。资产缺失时返回 0,调用方需据此降级。"""
    return _skill_count_of(_find_assets() / "skills")


def _skills_ok(skills_dir: Path) -> bool:
    """技能目录是否与随包资产一致。资产不可用时退化为"非空"检查。"""
    n = _skill_count_of(skills_dir)
    expected = _bundled_skill_count()
    return n == expected if expected else n > 0


def _parse_hosts(spec: "str | None") -> list:
    if not spec or spec == "all":
        return list(ALL_HOSTS)
    hosts = []
    for h in spec.split(","):
        h = h.strip().lower()
        if not h:
            continue
        if h not in HOSTS:
            raise ValueError(f"未知宿主: {h}(可用: {', '.join(HOSTS)} 或 all)")
        hosts.append(h)
    return hosts


# ---------------------------------------------------------------------------
# 路径与安全护栏
# ---------------------------------------------------------------------------


def _project_dir(args) -> Path:
    raw = getattr(args, "target", None) or str(Path.cwd())
    p = Path(raw).expanduser().resolve()
    if not p.is_dir():
        raise ValueError(f"目标目录不存在或不是目录: {p}")
    if p.parent == p:
        raise ValueError(f"拒绝在文件系统根目录操作: {p}")
    if p == Path.home():
        raise ValueError(f"拒绝在用户主目录操作: {p}")
    return p


def _list_assets(root: Path):
    return (p for p in root.rglob("*") if p.is_file())


def _is_ignored_rel(rel: str) -> bool:
    """安装清单不含中间产物(如宿主执行 hook 时可能生成的 __pycache__)。"""
    return "__pycache__" in Path(rel).parts


def _file_hashes(root: Path, skip: "set[str] | None" = None) -> dict:
    """受管文件的 SHA-256 清单(relpath -> hexdigest),用于安装后漂移检测。"""
    import hashlib

    skip = skip or set()
    out = {}
    for f in sorted(_list_assets(root)):
        rel = f.relative_to(root).as_posix()
        if rel in skip or _is_ignored_rel(rel):
            continue
        out[rel] = hashlib.sha256(f.read_bytes()).hexdigest()
    return out


def _copy_assets(src_root: Path, target_root: Path) -> int:
    count = 0
    for f in _list_assets(src_root):
        rel = f.relative_to(src_root)
        dest = target_root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, dest)
        count += 1
    return count


def _load_manifest(plugin_root: Path) -> dict:
    p = plugin_root / ".claude-plugin" / "plugin.json"
    if not p.is_file():
        raise FileNotFoundError(f"缺少插件清单: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def _plugin_version(plugin_root: Path) -> "str | None":
    try:
        return str(_load_manifest(plugin_root).get("version", "?"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def _legacy_signature_ok(project: Path) -> bool:
    if not (project / _LEGACY_STAMP).is_file():
        return False
    return (
        (project / "skills" / "drogon-create-controller").is_dir()
        and (project / "hooks" / "posttooluse.py").is_file()
    )


def _detect_bundle_layout(project: Path):
    if (project / _INSTALL_DIR / ".claude-plugin" / "plugin.json").is_file():
        return "v2", project / _INSTALL_DIR
    if _legacy_signature_ok(project):
        return "legacy", project
    return None, None


def _remove_legacy_layout(project: Path):
    removed, skipped = [], []
    if not (project / _LEGACY_STAMP).is_file():
        return removed, skipped
    for name, sig in (
        ("skills", "drogon-create-controller/SKILL.md"),
        ("hooks", "posttooluse.py"),
        (".claude-plugin", "plugin.json"),
        (".zcode-plugin", "plugin.json"),
    ):
        p = project / name
        if not p.exists():
            continue
        if (p / sig).exists():
            shutil.rmtree(p)
            removed.append(name)
        else:
            skipped.append(name)
    md = project / "CLAUDE.md"
    if md.is_file():
        first_line = ""
        try:
            first_line = md.read_text(encoding="utf-8").split("\n", 1)[0].strip()
        except OSError:
            pass
        if first_line == _CLAUDE_MD_MARKER:
            md.unlink()
            removed.append("CLAUDE.md")
        else:
            skipped.append("CLAUDE.md(项目自有,已保留)")
    (project / _LEGACY_STAMP).unlink()
    removed.append(_LEGACY_STAMP)
    return removed, skipped


# ---------------------------------------------------------------------------
# 指令文件三态(AGENTS.md / GEMINI.md / CODEBUDDY.md)
# ---------------------------------------------------------------------------


def _write_instruction_file(project: Path, name: str, content: str, force: bool):
    """三态写入。返回 action: full(新建整文件)/ marker(替换或追加标记段)/
    skipped(已存在且未 force)。

    注意:进入"替换"分支的判据必须是**成对的**标记段(`_MARKER_SECTION_RE`),
    不能只看 `_MARKER_BEGIN in text` —— 否则文件含孤立 begin(用户手改坏)时会
    写回原文却仍返回 "marker",让 uninstall 误以为可以剥离标记段。
    """
    p = project / name
    section = f"{_MARKER_BEGIN}\n{content.rstrip()}\n{_MARKER_END}\n"
    if not p.exists():
        p.write_text(section, encoding="utf-8")
        return "full"
    text = p.read_text(encoding="utf-8")
    if _MARKER_SECTION_RE.search(text):
        # 已有完整标记段(可能多段):全部替换为最新内容(升级语义)
        p.write_text(_MARKER_SECTION_RE.sub(section.rstrip("\n") + "\n", text), encoding="utf-8")
        return "marker"
    if _MARKER_BEGIN in text or _MARKER_END in text:
        # 半损坏:存在孤立标记(是我们写的,被手改坏了)。先清掉孤立标记行,
        # 再写回一段完整的 —— 这是唯一能保证 "返回 marker ⇔ 文件里确有可剥离标记段" 的做法。
        cleaned = _MARKER_LINE_RE.sub("", text).rstrip()
        body = f"{cleaned}\n\n{section}" if cleaned else section
        p.write_text(body, encoding="utf-8")
        return "marker"
    if force:
        p.write_text(text.rstrip() + "\n\n" + section, encoding="utf-8")
        return "marker"
    return "skipped"


def _strip_marker_section(project: Path, name: str) -> bool:
    """卸载:删标记段。返回该文件是否含标记段(即是否被处理)。"""
    p = project / name
    if not p.is_file():
        return False
    text = p.read_text(encoding="utf-8")
    if not _MARKER_SECTION_RE.search(text):
        return False
    # 多段标记全部剥离,并清掉可能存在的孤立标记行
    new = _MARKER_LINE_RE.sub("", _MARKER_SECTION_RE.sub("", text))
    new = re.sub(r"\n{3,}", "\n\n", new)
    p.write_text(new.rstrip() + "\n", encoding="utf-8")
    return True


# ---------------------------------------------------------------------------
# 安装戳
# ---------------------------------------------------------------------------


def _read_json(p: Path) -> dict:
    """读 JSON 对象;缺失或损坏一律返回 {}（不新增异常路径）。"""
    if not p.is_file():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _load_stamp(project: Path) -> dict:
    return _read_json(project / _STAMP_V3)


def _save_stamp(project: Path, data: dict) -> None:
    (project / _STAMP_V3).write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# 提示
# ---------------------------------------------------------------------------

_HOST_HINTS = {
    "claude": "claude plugin install .drogon-plugin --scope project(已用 marketplace 则 update drogon)",
    "zcode": f"ZCode 插件管理 → 添加 marketplace {_REPO_URL} → 安装 drogon",
    "codex": (
        "codex plugin marketplace add voidvec/drogon-claude-plugin → "
        "codex plugin install drogon@drogon-claude-plugin;"
        "装后在 /plugins 面板 review & trust(信任前插件钩子不运行)"
    ),
    "cursor": "重启 Cursor 打开本项目即生效(.cursor/skills 自动发现)",
    "copilot": "在 VS Code 打开本项目即生效(AGENTS.md + .agents/skills 自动发现)",
    "agents": "任何读取 AGENTS.md / .agents/skills 的工具打开本项目即生效",
    "gemini": f"gemini extensions install {_REPO_URL}(项目内 GEMINI.md 规则已即刻生效)",
    "qoder": "Qoder 打开本项目即生效(官方兼容 AGENTS.md)",
    "codebuddy": "CodeBuddy 打开本项目即读取 CODEBUDDY.md",
    "trae": "Trae 打开本项目即生效(.trae/skills + AGENTS.md;旧 .trae/rules/*.mdc 已撤,R10)",
}


def _print_hints(hosts: list) -> None:
    print("   启用方式:")
    for h in hosts:
        hint = _HOST_HINTS.get(h)
        if hint:
            print(f"     · {h}: {hint}")


# ---------------------------------------------------------------------------
# install
# ---------------------------------------------------------------------------


def cmd_install(args) -> int:
    from . import PLUGIN_VERSION

    try:
        project = _project_dir(args)
        hosts = _parse_hosts(getattr(args, "host", None))
        src_root = _find_assets()
        if not src_root.is_dir():
            raise FileNotFoundError(f"未找到插件资产目录({src_root}),请确认包安装完整。")
    except (ValueError, FileNotFoundError) as e:
        print(f"❌ {e}", file=sys.stderr)
        return 1

    force = bool(getattr(args, "force_agents", False))
    written: list = []
    instruction_files: dict = {}
    agents_md = (
        (src_root / "AGENTS.md").read_text(encoding="utf-8")
        if (src_root / "AGENTS.md").is_file()
        else ""
    )
    mdc = (
        "---\n"
        "description: Drogon C++ 后端开发规则(异步回调/事件循环纪律 + Skill 路由)\n"
        "globs:\n"
        "alwaysApply: true\n"
        "---\n\n" + agents_md
    )

    installed_hosts = []
    for host in hosts:
        conf = HOSTS[host]
        kind = conf["kind"]

        if kind == "bundle":
            root = project / _INSTALL_DIR
            if root.exists():
                shutil.rmtree(root)
            count = _copy_assets(src_root, root)
            (root / _STAMP_V2).write_text(
                json.dumps(
                    {
                        "source": "pypi:drogon-claude-plugin",
                        "cli_version": _version(),
                        "plugin_version": _plugin_version(root) or PLUGIN_VERSION,
                        "files": count,
                        # 受管文件摘要:verify 据此检测资产被改动/缺失/多余(C3)
                        "hashes": _file_hashes(root, skip={_STAMP_V2}),
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            installed_hosts.extend(["claude", "zcode"])
            continue

        if kind.startswith("skills"):
            skills_src = src_root / "skills"
            dest_base = project / conf["skills_dir"]
            n = 0
            for d in sorted(skills_src.iterdir()):
                if not d.is_dir():
                    continue
                dest = dest_base / d.name
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.copytree(d, dest)
                n += 1
                written.append(str(dest.relative_to(project)))
            print(f"   [{host}] 技能 {n} 个 → {conf['skills_dir']}")

        if "rulefile" in kind:
            rf = project / conf["rule_file"]
            rf.parent.mkdir(parents=True, exist_ok=True)
            rf.write_text(mdc, encoding="utf-8")
            written.append(str(rf.relative_to(project)))
            print(f"   [{host}] 规则 → {conf['rule_file']}")

        if "instruction" in kind:
            name = conf["file"]
            if not agents_md:
                print(f"   [{host}] ⚠ 资产缺 AGENTS.md,跳过 {name}")
                continue
            action = _write_instruction_file(project, name, agents_md, force=force)
            # 同一安装批次内,同一指令文件可能被多个宿主先后写入
            # (如 codex 建文件 full,qoder 替换标记段 marker)——记录取最强动作,
            # 防 full 被降级(否则全量卸载只剥标记段,残留我们创建的文件)。
            _rank = {"full": 3, "marker": 2, "skipped": 1}
            if _rank.get(action, 0) >= _rank.get(instruction_files.get(name, ""), 0):
                instruction_files[name] = action
            if action == "skipped":
                print(
                    f"   [{host}] ⚠ {name} 已存在,未改动(项目自有文件不受触碰)。\n"
                    f"       合并方式:加 <!-- drogon-plugin begin/end --> 标记段,"
                    f"或 --force-agents 追加(卸载只删标记段)"
                )
            else:
                print(f"   [{host}] 规则 → {name}({action})")

        installed_hosts.append(host)

    stamp = _load_stamp(project)
    # 指令文件动作取"最强":一旦 full(文件由我们创建)就不被后装的 marker
    # 降级——否则全量卸载只剥标记段,留下我们创建的空文件。
    rank = {"full": 3, "marker": 2, "skipped": 1}
    merged_instructions = dict(stamp.get("instruction_files", {}))
    for name, action in instruction_files.items():
        if rank.get(action, 0) >= rank.get(merged_instructions.get(name, ""), 0):
            merged_instructions[name] = action
    stamp.update(
        {
            "version": PLUGIN_VERSION,
            "hosts": sorted(set(stamp.get("hosts", []) + installed_hosts)),
            "files": sorted(set(stamp.get("files", []) + written)),
            "instruction_files": merged_instructions,
        }
    )
    _save_stamp(project, stamp)

    print(f"✅ 安装完成:宿主 {', '.join(sorted(set(installed_hosts)))}")
    _print_hints(sorted(set(installed_hosts)))
    return 0


# ---------------------------------------------------------------------------
# verify
# ---------------------------------------------------------------------------


def _host_artifact_ok(project: Path, conf: dict) -> bool:
    kind = conf["kind"]
    if kind == "bundle":
        return (project / _INSTALL_DIR / ".claude-plugin" / "plugin.json").is_file()
    ok = True
    if kind.startswith("skills"):
        ok = ok and _skills_ok(project / conf["skills_dir"])
    if "rulefile" in kind:
        ok = ok and (project / conf["rule_file"]).is_file()
    if "instruction" in kind:
        p = project / conf["file"]
        if not p.is_file():
            ok = False
        else:
            try:
                ok = ok and (_MARKER_BEGIN in p.read_text(encoding="utf-8"))
            except OSError:
                ok = False
    return ok


def _drift_problems(plugin_root: Path) -> list:
    """已安装 bundle 的资产漂移检测(缺失/被改动/多余)。

    无清单时静默跳过——升级前用旧版安装的项目没有 hashes 字段,verify 不应因此报错。
    """
    recorded = _read_json(plugin_root / _STAMP_V2).get("hashes")
    if not isinstance(recorded, dict) or not recorded:
        return []
    current = _file_hashes(plugin_root, skip={_STAMP_V2})
    problems = []
    missing = sorted(set(recorded) - set(current))
    modified = sorted(k for k in set(recorded) & set(current) if recorded[k] != current[k])
    added = sorted(set(current) - set(recorded))
    if missing:
        problems.append(f"资产缺失 {len(missing)} 个(如 {missing[0]});可 upgrade 重装")
    if modified:
        problems.append(f"资产被改动 {len(modified)} 个(如 {modified[0]});可 upgrade 覆盖")
    if added:
        problems.append(f"资产目录存在未受管文件 {len(added)} 个(如 {added[0]})")
    return problems


def cmd_verify(args) -> int:
    try:
        project = _project_dir(args)
    except ValueError as e:
        print(f"❌ {e}", file=sys.stderr)
        return 1

    problems: list = []
    layout, plugin_root = _detect_bundle_layout(project)
    stamp = _load_stamp(project)

    manifest_ver = "-"
    if layout == "v2":
        try:
            manifest_ver = str(_load_manifest(plugin_root).get("version", "?"))
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"❌ {e}", file=sys.stderr)
            return 1
        skills_dir = plugin_root / "skills"
        if not skills_dir.is_dir():
            problems.append("缺少 skills/ 目录")
        elif not _skills_ok(skills_dir):
            problems.append(
                f"技能数 {_skill_count_of(skills_dir)} != 随包 {_bundled_skill_count()}"
            )
        for f in _EXPECTED_HOOK_FILES:
            if not (plugin_root / "hooks" / f).is_file():
                problems.append(f"缺少 hooks/{f}")
        hooks_json = plugin_root / "hooks" / "hooks.json"
        if hooks_json.is_file():
            n_events = len(_read_json(hooks_json).get("hooks", {}))
            if n_events != _EXPECTED_HOOK_EVENTS:
                problems.append(f"hooks 事件数 {n_events} != 预期 {_EXPECTED_HOOK_EVENTS}")
        if not (plugin_root / "CLAUDE.md").is_file():
            problems.append("缺少 CLAUDE.md")
        if not (plugin_root / ".zcode-plugin" / "plugin.json").is_file():
            problems.append("缺少 .zcode-plugin/plugin.json")
        problems.extend(_drift_problems(plugin_root))

    host_status = [(h, _host_artifact_ok(project, c)) for h, c in HOSTS.items()]

    print(f"📦 drogon-claude-plugin 校验 — {project}")
    print(f"   bundle   : {layout or '未安装'}(版本 {manifest_ver})")
    row1 = "  ".join(f"{h}{'✅' if ok else '—'}" for h, ok in host_status[:5])
    row2 = "  ".join(f"{h}{'✅' if ok else '—'}" for h, ok in host_status[5:])
    print(f"   宿主     : {row1}")
    print(f"             {row2}")
    if stamp:
        print(f"   安装记录 : v{stamp.get('version', '?')} · 宿主 {', '.join(stamp.get('hosts', []))}")

    if layout is None and not any(ok for _, ok in host_status):
        print("   ❌ 未发现任何插件产物(先运行 install)")
        return 1
    if problems:
        print("   ❌ 发现问题:")
        for p in problems:
            print(f"      - {p}")
        return 1
    print("   ✅ 通过(未安装的宿主显示 —,属正常;需要时 install --host <name>)")
    return 0


# ---------------------------------------------------------------------------
# upgrade(bundle 重装;多宿主产物幂等重生成;标记段升级语义)
# ---------------------------------------------------------------------------


def cmd_upgrade(args) -> int:
    """升级到随包版本。

    回归(R4):旧实现无条件 ``force_agents=True`` 且不带 host → cmd_install 按
    ALL_HOSTS 重装。两个后果:①给用户只装过部分宿主的项目凭空落下其余八家产物;
    ②把标记段强推进用户自有的 AGENTS.md/GEMINI.md/CODEBUDDY.md。
    新语义:范围 = 安装戳里已安装的宿主(--host 可显式覆盖);marker 追加是
    显式 opt-in(--force-agents),永不默认发生;无安装戳退化为全量安装。
    """
    if not getattr(args, "host", None):
        try:
            project = _project_dir(args)
            stamped = [h for h in _load_stamp(project).get("hosts", []) if h in HOSTS]
        except ValueError:
            stamped = []
        # _parse_hosts 对空串/None 走 ALL_HOSTS —— 无戳即无范围,保持旧行为
        args.host = ",".join(sorted(set(stamped))) if stamped else None
    return cmd_install(args)


# ---------------------------------------------------------------------------
# uninstall
# ---------------------------------------------------------------------------


def _cleanup_empty_dirs(project: Path) -> None:
    for rel in _OUR_DIR_CANDIDATES:
        d = project / rel
        try:
            if d.is_dir() and not any(d.iterdir()):
                d.rmdir()
        except OSError:
            pass


def _uninstall_bundle(project: Path, conf: dict, stamp: dict, removed: list, removing: list) -> None:
    """bundle 宿主(claude/zcode)共用 ``.drogon-plugin/``:整目录都由本插件所有,直接删除。

    注意粒度语义:claude 与 zcode 共用同一 bundle,按宿主粒度无法拆分,
    因此卸载任一 bundle 宿主即移除整个 bundle(在 ``--help`` 与输出中已说明)。
    """
    root = project / _INSTALL_DIR
    if root.is_dir():
        shutil.rmtree(root)
        removed.append(_INSTALL_DIR)


def _hosts_using_skills_dir(installed: "list[str]", skills_dir: str) -> set:
    """已安装宿主中,哪些把技能落在 ``skills_dir``。"""
    return {
        h for h in installed
        if h in HOSTS and HOSTS[h].get("skills_dir") == skills_dir
    }


def _uninstall_skills(project: Path, conf: dict, stamp: dict, removed: list, removing: list) -> None:
    """删 ours-by-name 的 ``drogon-*`` 技能目录。

    两个约束:
      1. 先判 ``is_dir()`` —— 同名**文件**会让 ``rmtree`` 抛错;
      2. **引用计数** —— ``copilot`` 与 ``agents`` 共用 ``.agents/skills``,
         卸载其一不得清空另一个仍在用的技能(与指令文件同构的共享资源保护)。
    """
    base_rel = conf["skills_dir"]
    installed = [h for h in stamp.get("hosts", []) if h in HOSTS]
    if _hosts_using_skills_dir(installed, base_rel) - set(removing):
        return

    base = project / base_rel
    if not base.is_dir():
        return
    for d in sorted(base.glob("drogon-*")):
        if not d.is_dir():
            continue
        shutil.rmtree(d)
        removed.append(str(d.relative_to(project)))


def _uninstall_rulefile(project: Path, conf: dict, stamp: dict, removed: list, removing: list) -> None:
    rf = project / conf["rule_file"]
    if rf.is_file():
        rf.unlink()
        removed.append(str(rf.relative_to(project)))


def _hosts_using_instruction(installed: "list[str]", name: str) -> set:
    """已安装宿主中,哪些依赖指令文件 ``name``。"""
    return {
        h for h in installed
        if h in HOSTS and "instruction" in HOSTS[h]["kind"] and HOSTS[h]["file"] == name
    }


def _uninstall_instruction(project: Path, conf: dict, stamp: dict, removed: list, removing: list) -> None:
    """指令文件可能被多个宿主共享(codex / qoder / copilot / agents 都用 AGENTS.md)。

    仅当**移除本批宿主后已无任何已安装宿主再引用它**、且 stamp 记为 ``full``(由我们
    创建)时才整份删除;否则退化为只剥标记段 —— 绝不删掉其它宿主仍在用的整文件。
    回归来源:此前 ``install --host codex`` 后 ``uninstall --host qoder`` 会把 AGENTS.md 整份删掉。
    """
    name = conf["file"]
    installed = [h for h in stamp.get("hosts", []) if h in HOSTS]
    still_using = _hosts_using_instruction(installed, name) - set(removing)

    if still_using:
        # 仍被其它已安装宿主使用:整份保留(标记段也不能剥 —— 那段内容正是它们需要的)。
        # 最后一个使用者被卸载时才会走到下面的删除/剥离分支。
        return

    action = stamp.get("instruction_files", {}).get(name)
    if action == "full" and (project / name).is_file():
        (project / name).unlink()
        removed.append(name)
    elif _strip_marker_section(project, name):
        # 标记段已剥:同步清掉安装记录,否则 stamp 会因"文件仍存在(用户自有内容)"
        # 而留下过期的 instruction_files → 安装戳残留、verify 显示半残状态。
        stamp.setdefault("instruction_files", {}).pop(name, None)
        removed.append(f"{name}(标记段)")


# 宿主类型 -> 卸载动作(**显式映射**)。
#
# 为什么用映射而不是 if-链:此前用 `"skills" in kind / "rulefile" in kind /
# "instruction" in kind` 三个判定,而 `bundle` 一个都不匹配 —— `uninstall --host claude`
# 因此静默空操作(装得进、卸不掉)。映射之外,一致性门禁还会断言
# "HOSTS 里出现的每一种 kind 都被此映射覆盖",让"新增宿主类型却忘记登记卸载动作"
# 从"静默失效"变成"CI 报错"。
_UNINSTALL_COMPONENT_ACTIONS = {
    "bundle": _uninstall_bundle,
    "skills": _uninstall_skills,
    "rulefile": _uninstall_rulefile,
    "instruction": _uninstall_instruction,
}


def uninstall_component_kinds() -> "list[str]":
    """本 CLI 已登记卸载动作的宿主类型组件(供一致性门禁比对 HOSTS)。"""
    return sorted(_UNINSTALL_COMPONENT_ACTIONS)


def _uninstall_actions_for(kind: str):
    """把(可能是复合的)kind 如 ``"skills+instruction"`` 拆成动作序列。

    出现未登记组件时**抛出**而不是跳过 —— 静默跳过正是 C1 缺陷的成因。
    """
    try:
        return tuple(_UNINSTALL_COMPONENT_ACTIONS[part] for part in kind.split("+"))
    except KeyError as e:
        raise KeyError(f"未登记卸载动作的宿主类型组件: {e.args[0]}") from None


def _expand_bundle_group(hosts: list) -> list:
    """bundle 宿主共用 ``.drogon-plugin/``:移除其一即移除整组。

    安装时 ``--host claude`` 会在 stamp 里同时登记 claude 与 zcode(两者都因该
    bundle 而可用);卸载若只摘掉 claude,stamp 会留下 zcode → 安装戳残留。
    """
    expanded = list(hosts)
    if any(HOSTS[h]["kind"] == "bundle" for h in expanded):
        for h, conf in HOSTS.items():
            if conf["kind"] == "bundle" and h not in expanded:
                expanded.append(h)
    return expanded


def _uninstall_hosts(project: Path, hosts: list, stamp: dict) -> list:
    effective = _expand_bundle_group(hosts)
    removed: list = []
    for host in effective:
        conf = HOSTS[host]
        for action in _uninstall_actions_for(conf["kind"]):
            action(project, conf, stamp, removed, effective)
    stamp["hosts"] = [h for h in stamp.get("hosts", []) if h not in effective]
    return removed


def _prune_stamp(project: Path, stamp: dict) -> None:
    """剔掉已不存在的落点记录。

    否则按宿主卸载后 ``stamp["files"]`` 仍非空,会把安装戳文件留在项目里(残留)。
    """
    stamp["files"] = [f for f in stamp.get("files", []) if (project / f).exists()]
    stamp["instruction_files"] = {
        n: a for n, a in stamp.get("instruction_files", {}).items() if (project / n).exists()
    }


def cmd_uninstall(args) -> int:
    try:
        project = _project_dir(args)
        spec = getattr(args, "host", None)
    except ValueError as e:
        print(f"❌ {e}", file=sys.stderr)
        return 1

    stamp = _load_stamp(project)

    if spec and spec != "all":
        try:
            hosts = _parse_hosts(spec)
        except ValueError as e:
            print(f"❌ {e}", file=sys.stderr)
            return 1
        removed = _uninstall_hosts(project, hosts, stamp)
        _cleanup_empty_dirs(project)
        _prune_stamp(project, stamp)
        if stamp.get("hosts") or stamp.get("files") or stamp.get("instruction_files"):
            _save_stamp(project, stamp)
        else:
            (project / _STAMP_V3).unlink(missing_ok=True)
        if removed:
            print(f"🗑  已按宿主移除 {len(removed)} 项")
        else:
            print("ℹ️   所选宿主无产物")
        return 0

    # 全量卸载
    removed: list = []
    for name, action in stamp.get("instruction_files", {}).items():
        if action == "full" and (project / name).is_file():
            (project / name).unlink()
            removed.append(name)
        elif _strip_marker_section(project, name):
            removed.append(f"{name}(标记段)")
    for rel in stamp.get("files", []):
        p = project / rel
        if p.is_dir():
            shutil.rmtree(p)
            removed.append(rel)
        elif p.is_file():
            p.unlink()
            removed.append(rel)

    root = project / _INSTALL_DIR
    if root.is_dir():
        shutil.rmtree(root)
        removed.append(_INSTALL_DIR)
    legacy_removed, skipped = _remove_legacy_layout(project)
    removed += legacy_removed

    # 无戳兜底:ours-by-name 签名清理 + 标记段剥离
    if not stamp:
        for pattern in (
            ".cursor/skills/drogon-*",
            ".agents/skills/drogon-*",
            ".trae/skills/drogon-*",
            ".cursor/rules/drogon-plugin.mdc",
            ".trae/rules/drogon-plugin.mdc",  # 旧版落点(R10),无戳兜底时仍负责清扫
        ):
            for p in project.glob(pattern):
                if p.is_dir():
                    shutil.rmtree(p)
                else:
                    p.unlink()
                removed.append(str(p.relative_to(project)))
        for name in ("AGENTS.md", "GEMINI.md", "CODEBUDDY.md"):
            if _strip_marker_section(project, name):
                removed.append(f"{name}(标记段)")

    _cleanup_empty_dirs(project)
    (project / _STAMP_V3).unlink(missing_ok=True)

    if removed:
        print(f"🗑  已从 {project} 移除 {len(removed)} 项")
        for s in skipped:
            print(f"   ⚠️  跳过 {s}")
        print("   注意:如曾用 claude plugin install 注册,另需 claude plugin uninstall drogon")
    else:
        print(f"ℹ️   未在 {project} 发现插件资产")
    return 0


# ---------------------------------------------------------------------------
# scan(无钩子宿主 / CI 兜底)— 进程内加载扫描模块,不产生任何子进程
# ---------------------------------------------------------------------------


def _scan_error(args, message: str, code: int) -> int:
    """scan 的错误输出也遵守 ``--format json`` 契约。

    回归来源:此前错误路径只往 stderr 打印并直接 return,若调用方用
    ``--format json`` 解析 stdout 会拿到非 JSON。新增的 ``error`` 字段是**纯增量**
    (``findings`` / ``total`` 的语义不变)。
    """
    if getattr(args, "format", "human") == "json":
        print(
            json.dumps(
                {"error": message, "findings": [], "total": 0},
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(f"❌ {message}", file=sys.stderr)
    return code


def cmd_scan(args) -> int:
    try:
        project = _project_dir(args)
    except ValueError as e:
        return _scan_error(args, str(e), 1)

    scanner_path = _find_assets() / "hooks" / "posttooluse.py"
    if not scanner_path.is_file():
        return _scan_error(args, "未找到随包扫描器(hooks/posttooluse.py)", 1)

    # 路径边界:每个被扫描路径必须解析到项目目录之内(防 ../ 逃逸读任意文件)
    raw_paths = getattr(args, "paths", None) or ["."]
    safe_paths = []
    for rp in raw_paths:
        candidate = Path(rp)
        resolved = candidate.resolve() if candidate.is_absolute() else (project / candidate).resolve()
        if resolved != project and not resolved.is_relative_to(project):
            return _scan_error(args, f"拒绝扫描项目外的路径: {rp}", 2)
        safe_paths.append(str(resolved.relative_to(project)))

    import importlib.util

    # 动态加载随包扫描器时禁止写字节码缓存:否则会在资产目录里生成 __pycache__,
    # 既污染随包资产(被 sync-assets --check 判为不一致),也不是我们管理的文件。
    sys.dont_write_bytecode = True

    spec = importlib.util.spec_from_file_location("drogon_posttooluse_scan", scanner_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    prev_cwd = os.getcwd()
    try:
        os.chdir(project)  # scan_paths 以 cwd 为边界与相对路径基准
        return mod.scan_paths(
            safe_paths,
            fmt=getattr(args, "format", "human"),
            strict=bool(getattr(args, "strict", False)),
        )
    finally:
        os.chdir(prev_cwd)


# ---------------------------------------------------------------------------
# hosts / version
# ---------------------------------------------------------------------------


def cmd_hosts(args) -> int:
    print("支持的宿主(all 为默认互斥集合;copilot/agents 需单独指定以落 .agents/skills):")
    for h, conf in HOSTS.items():
        in_all = "✅ all  " if h in ALL_HOSTS else "   opt-in"
        print(f"  {h:10s}{in_all}{conf['kind']}")
    return 0


def cmd_version(args) -> int:
    try:
        from . import PLUGIN_VERSION
    except ImportError:
        PLUGIN_VERSION = "?"
    print(f"drogon-claude-plugin (pypi) v{_version()} | 内置插件 v{PLUGIN_VERSION}")
    return 0


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="drogon-claude-plugin",
        description="drogon 插件多宿主安装器(Claude Code / ZCode / Codex / Cursor / VS Code / Gemini / Qoder / CodeBuddy / Trae / .agents)。",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("install", help="安装插件产物(默认全部宿主)")
    p.add_argument("--target", help="项目根目录(默认当前目录)")
    p.add_argument("--host", help="宿主列表(逗号分隔;默认 all)")
    p.add_argument(
        "--force-agents",
        action="store_true",
        help="项目已有 AGENTS.md/GEMINI.md/CODEBUDDY.md 时追加标记段(默认跳过不动)",
    )
    p.set_defaults(func=cmd_install)

    p = sub.add_parser("verify", help="校验已安装产物")
    p.add_argument("--target")
    p.set_defaults(func=cmd_verify)

    p = sub.add_parser("upgrade", help="升级到随包版本(默认范围 = 已安装宿主)")
    p.add_argument("--target")
    p.add_argument("--host", help="只升级指定宿主(默认:安装戳中已安装的宿主)")
    p.add_argument(
        "--force-agents",
        action="store_true",
        help="用户已有 AGENTS.md/GEMINI.md/CODEBUDDY.md 时追加标记段(默认跳过不动)",
    )
    p.set_defaults(func=cmd_upgrade)

    p = sub.add_parser(
        "uninstall",
        help="移除插件产物",
        epilog=(
            "粒度说明:claude/zcode 共用 .drogon-plugin/ bundle,按宿主粒度无法拆分,"
            "卸载任一 bundle 宿主即移除整个 bundle;其它宿主只移除各自的落点。"
        ),
    )
    p.add_argument("--target")
    p.add_argument("--host", help="只移除指定宿主的产物(默认全部)")
    p.set_defaults(func=cmd_uninstall)

    p = sub.add_parser("scan", help="扫描 drogon API 违规(无钩子宿主 / CI)")
    p.add_argument("--target")
    p.add_argument("--format", choices=["human", "json"], default="human")
    p.add_argument("--strict", action="store_true", help="发现违规时退出码 1(CI 拦截)")
    p.add_argument("paths", nargs="*", help="扫描路径(默认整个项目)")
    p.set_defaults(func=cmd_scan)

    sub.add_parser("hosts", help="列出支持的宿主").set_defaults(func=cmd_hosts)
    sub.add_parser("version", help="显示版本").set_defaults(func=cmd_version)
    return parser


def available_commands() -> "list[str]":
    """本 CLI 支持的子命令集合(从解析器实枚举)。

    供能力契约测试比对,避免维护第二份命令清单——实现改了解析器,
    这里与 tests/test_hosts.py 的断言会同步感知。
    """
    parser = _build_parser()
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return sorted(action.choices.keys())
    return []


def _utf8_stdio() -> None:
    # Windows 下 stdout 为管道/重定向时默认 cp1252,print ✅/中文 会抛 UnicodeEncodeError
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass


def main(argv: "list[str] | None" = None) -> int:
    _utf8_stdio()
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        return args.func(args)
    except KeyboardInterrupt:
        return 130
    except (OSError, json.JSONDecodeError) as e:
        print(f"❌ {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
