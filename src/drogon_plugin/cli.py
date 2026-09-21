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
  trae           → .trae/rules/drogon-plugin.mdc

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

_EXPECTED_SKILLS = 22
_EXPECTED_HOOK_FILES = (
    "hooks.json",
    "run-hook.cmd",
    "session-start",
    "post-tool-use",
    "posttooluse.py",
)
_EXPECTED_HOOK_EVENTS = 2

_REPO_URL = "https://github.com/voidvec/drogon-claude-plugin"

_PKG_VERSION: "str | None" = None

_MARKER_SECTION_RE = re.compile(
    re.escape(_MARKER_BEGIN) + r"[\s\S]*?" + re.escape(_MARKER_END) + r"\n?"
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
    "trae": {"kind": "rulefile", "rule_file": ".trae/rules/drogon-plugin.mdc"},
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
    ".trae/rules",
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
    skipped(已存在且未 force)。"""
    p = project / name
    section = f"{_MARKER_BEGIN}\n{content.rstrip()}\n{_MARKER_END}\n"
    if not p.exists():
        p.write_text(section, encoding="utf-8")
        return "full"
    text = p.read_text(encoding="utf-8")
    if _MARKER_BEGIN in text:
        # 已有标记段:替换为最新内容(升级语义)
        p.write_text(_MARKER_SECTION_RE.sub(section.rstrip("\n") + "\n", text, count=1), encoding="utf-8")
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
    new = _MARKER_SECTION_RE.sub("", text, count=1)
    new = re.sub(r"\n{3,}", "\n\n", new)
    p.write_text(new.rstrip() + "\n", encoding="utf-8")
    return True


# ---------------------------------------------------------------------------
# 安装戳
# ---------------------------------------------------------------------------


def _load_stamp(project: Path) -> dict:
    p = project / _STAMP_V3
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


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
    "trae": "Trae 打开本项目即生效(.trae/rules)",
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
        base = project / conf["skills_dir"]
        n = len([d for d in base.iterdir() if d.is_dir()]) if base.is_dir() else 0
        ok = ok and n >= _EXPECTED_SKILLS
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
        else:
            n = len([d for d in skills_dir.iterdir() if d.is_dir()])
            if n != _EXPECTED_SKILLS:
                problems.append(f"技能数 {n} != 预期 {_EXPECTED_SKILLS}")
        for f in _EXPECTED_HOOK_FILES:
            if not (plugin_root / "hooks" / f).is_file():
                problems.append(f"缺少 hooks/{f}")
        if not (plugin_root / ".zcode-plugin" / "plugin.json").is_file():
            problems.append("缺少 .zcode-plugin/plugin.json")

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
    args.force_agents = True
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


def _uninstall_hosts(project: Path, hosts: list, stamp: dict) -> list:
    removed = []
    for host in hosts:
        conf = HOSTS[host]
        kind = conf["kind"]
        if "skills" in kind:
            base = project / conf["skills_dir"]
            if base.is_dir():
                for d in sorted(base.glob("drogon-*")):
                    shutil.rmtree(d)
                    removed.append(str(d.relative_to(project)))
        if "rulefile" in kind:
            rf = project / conf["rule_file"]
            if rf.is_file():
                rf.unlink()
                removed.append(str(rf.relative_to(project)))
        if "instruction" in kind:
            name = conf["file"]
            action = stamp.get("instruction_files", {}).get(name)
            if action == "full" and (project / name).is_file():
                (project / name).unlink()
                removed.append(name)
            elif _strip_marker_section(project, name):
                removed.append(f"{name}(标记段)")
    stamp["hosts"] = [h for h in stamp.get("hosts", []) if h not in hosts]
    return removed


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
        if stamp.get("hosts") or stamp.get("files"):
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
            ".cursor/rules/drogon-plugin.mdc",
            ".trae/rules/drogon-plugin.mdc",
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


def cmd_scan(args) -> int:
    try:
        project = _project_dir(args)
    except ValueError as e:
        print(f"❌ {e}", file=sys.stderr)
        return 1

    scanner_path = _find_assets() / "hooks" / "posttooluse.py"
    if not scanner_path.is_file():
        print("❌ 未找到随包扫描器(hooks/posttooluse.py)", file=sys.stderr)
        return 1

    # 路径边界:每个被扫描路径必须解析到项目目录之内(防 ../ 逃逸读任意文件)
    raw_paths = getattr(args, "paths", None) or ["."]
    safe_paths = []
    for rp in raw_paths:
        candidate = Path(rp)
        resolved = candidate.resolve() if candidate.is_absolute() else (project / candidate).resolve()
        if resolved != project and not resolved.is_relative_to(project):
            print(f"❌ 拒绝扫描项目外的路径: {rp}", file=sys.stderr)
            return 2
        safe_paths.append(str(resolved.relative_to(project)))

    import importlib.util

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

    p = sub.add_parser("upgrade", help="升级到随包版本")
    p.add_argument("--target")
    p.set_defaults(func=cmd_upgrade)

    p = sub.add_parser("uninstall", help="移除插件产物")
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
