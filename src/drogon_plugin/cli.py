#!/usr/bin/env python3
"""drogon-claude-plugin — CLI 安装器（PyPI 发行版）.

把随包内置的 drogon 插件资产安装到目标项目的 ``.drogon-plugin/`` 子目录并
给出 Claude Code / ZCode 双宿主启用指引，或对已安装目录做结构校验 / 升级 /
卸载。

v0.2.0 起安装布局变更：资产装入 ``<project>/.drogon-plugin/`` 自包含目录，
不再覆盖项目根的 ``CLAUDE.md`` / ``.claude`` 等文件；卸载对 v0.1.x 的根目录
散装布局仍兼容清理（逐项归属校验，项目自有文件绝不会被误删）。

子命令:
  install   [--target DIR]                 安装资产到 <DIR>/.drogon-plugin/
  verify    [--target DIR]                 校验已安装插件结构
  upgrade   [--target DIR]                 升级到随包版本（含 v0.1.x 布局迁移）
  uninstall [--target DIR]                 移除已安装插件资产
  version
"""

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

# 资产在 wheel 内统一放在 ``drogon_plugin_assets/`` 下（见 pyproject.toml data-files）
_ASSETS_PREFIX = "drogon_plugin_assets"
# v0.2.0 自包含安装目录（相对项目根）
_INSTALL_DIR = ".drogon-plugin"
_LEGACY_STAMP = ".drogon-claude-plugin-installed.json"
_STAMP = ".drogon-claude-plugin-v2.json"
# 本插件 CLAUDE.md 首行标记：卸载时只有匹配才清理项目根的 CLAUDE.md
_CLAUDE_MD_MARKER = "# Drogon 后端开发规则"

_EXPECTED_SKILLS = 22
_EXPECTED_HOOK_FILES = (
    "hooks.json",
    "run-hook.cmd",
    "session-start",
    "post-tool-use",
    "posttooluse.py",
)
_EXPECTED_HOOK_EVENTS = 2  # SessionStart + PostToolUse

_PKG_VERSION: "str | None" = None


def _version() -> str:
    """返回已安装发行包的版本；源码树运行时返回 dev。"""
    global _PKG_VERSION
    if _PKG_VERSION is None:
        try:
            from importlib.metadata import version

            _PKG_VERSION = version("drogon-claude-plugin")
        except Exception:
            _PKG_VERSION = "dev"
    return _PKG_VERSION


def _find_assets() -> Path:
    """定位随包携带的插件资产根目录。"""
    here = Path(__file__).resolve().parent
    return here / _ASSETS_PREFIX


# ---------------------------------------------------------------------------
# 路径与安全护栏
# ---------------------------------------------------------------------------


def _project_dir(args) -> Path:
    """解析并校验项目根：--target 由用户显式给出，但仍做边界防护——必须是已存在
    的目录，且拒绝文件系统根目录 / 用户主目录这类误操作高危目标。"""
    raw = getattr(args, "target", None) or str(Path.cwd())
    p = Path(raw).expanduser().resolve()
    if not p.is_dir():
        raise ValueError(f"目标目录不存在或不是目录: {p}")
    if p.parent == p:
        raise ValueError(f"拒绝在文件系统根目录操作: {p}")
    if p == Path.home():
        raise ValueError(f"拒绝在用户主目录操作: {p}")
    return p


def _install_root(project: Path) -> Path:
    return project / _INSTALL_DIR


def _list_assets(root: Path):
    return (p for p in root.rglob("*") if p.is_file())


def _copy_assets(src_root: Path, target_root: Path) -> int:
    """把 src_root 下所有资产复制到 target_root（相对路径来自对 src_root 的
    枚举，不含用户输入），返回文件数。"""
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
    """v0.1.x 根目录散装布局的归属签名：安装戳 + 本插件特征文件齐备。"""
    if not (project / _LEGACY_STAMP).is_file():
        return False
    return (
        (project / "skills" / "drogon-create-controller").is_dir()
        and (project / "hooks" / "posttooluse.py").is_file()
    )


def _detect_layout(project: Path):
    """返回 ('v2', install_root) / ('legacy', project) / (None, None)。"""
    if (_install_root(project) / ".claude-plugin" / "plugin.json").is_file():
        return "v2", _install_root(project)
    if _legacy_signature_ok(project):
        return "legacy", project
    return None, None


def _remove_legacy_layout(project: Path):
    """清理 v0.1.x 散装在项目根的资产。逐项做归属校验（签名不匹配则跳过并
    告警），项目自身的 CLAUDE.md 等文件绝不会被误删。返回 (removed, skipped)。"""
    removed: list = []
    skipped: list = []
    if not (project / _LEGACY_STAMP).is_file():
        return removed, skipped

    # 目录类资产：内部含本插件特征文件才删
    dir_signatures = (
        ("skills", "drogon-create-controller/SKILL.md"),
        ("hooks", "posttooluse.py"),
        (".claude-plugin", "plugin.json"),
        (".zcode-plugin", "plugin.json"),
    )
    for name, sig in dir_signatures:
        p = project / name
        if not p.exists():
            continue
        if (p / sig).exists():
            shutil.rmtree(p)
            removed.append(name)
        else:
            skipped.append(name)

    # CLAUDE.md：首行是本插件标记才删，否则视为项目自有文件，保留并告警
    md = project / "CLAUDE.md"
    if md.is_file():
        try:
            first_line = md.read_text(encoding="utf-8").split("\n", 1)[0].strip()
        except OSError:
            first_line = ""
        if first_line == _CLAUDE_MD_MARKER:
            md.unlink()
            removed.append("CLAUDE.md")
        else:
            skipped.append("CLAUDE.md（项目自有，已保留）")

    (project / _LEGACY_STAMP).unlink()
    removed.append(_LEGACY_STAMP)
    return removed, skipped


def _print_enable_hint(plugin_root: Path) -> None:
    print("   启用方式（二选一）:")
    print(f"     · Claude Code:  claude plugin install {plugin_root.name} --scope project")
    print("     · ZCode:        在 ZCode 插件管理中添加 marketplace")
    print("       https://github.com/voidvec/drogon-claude-plugin 后安装 drogon 插件")
    print("     （已用 marketplace 安装过则跳过本地注册，直接 claude plugin update drogon）")


# ---------------------------------------------------------------------------
# 子命令
# ---------------------------------------------------------------------------


def cmd_install(args) -> int:
    from . import PLUGIN_VERSION

    try:
        project = _project_dir(args)
        src_root = _find_assets()
        if not src_root.is_dir():
            raise FileNotFoundError(
                f"未找到插件资产目录（{src_root}）。请确认包安装完整。"
            )
        root = _install_root(project)
        if root.exists():
            shutil.rmtree(root)
        count = _copy_assets(src_root, root)
    except (ValueError, FileNotFoundError, OSError) as e:
        print(f"❌ {e}", file=sys.stderr)
        return 1

    manifest_version = _plugin_version(root) or PLUGIN_VERSION
    (root / _STAMP).write_text(
        json.dumps(
            {
                "source": "pypi:drogon-claude-plugin",
                "cli_version": _version(),
                "plugin_version": manifest_version,
                "files": count,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"✅ 已安装 drogon 插件资产到 {root}")
    print(f"   复制 {count} 个文件 · 插件版本 {manifest_version} · {_EXPECTED_SKILLS} 个技能")
    _print_enable_hint(root)
    return 0


def cmd_verify(args) -> int:
    try:
        project = _project_dir(args)
    except ValueError as e:
        print(f"❌ {e}", file=sys.stderr)
        return 1

    layout, plugin_root = _detect_layout(project)
    if layout is None:
        print(f"❌ {project} 下未发现已安装的 drogon 插件（找 .drogon-plugin/ 或 v0.1.x 根目录布局）")
        return 1

    try:
        manifest = _load_manifest(plugin_root)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"❌ {e}", file=sys.stderr)
        return 1

    manifest_ver = str(manifest.get("version", "?"))
    problems: list = []
    skill_names: list = []

    # 技能
    skills_dir = plugin_root / "skills"
    if not skills_dir.is_dir():
        problems.append("缺少 skills/ 目录")
    else:
        skill_names = sorted(d.name for d in skills_dir.iterdir() if d.is_dir())
        if len(skill_names) != _EXPECTED_SKILLS:
            problems.append(f"技能数 {len(skill_names)} != 预期 {_EXPECTED_SKILLS}")
        for n in skill_names:
            if not (skills_dir / n / "SKILL.md").is_file():
                problems.append(f"技能 {n} 缺少 SKILL.md")

    # hooks（脚本 + 事件）
    hooks_dir = plugin_root / "hooks"
    if not hooks_dir.is_dir():
        problems.append("缺少 hooks/ 目录")
    else:
        for f in _EXPECTED_HOOK_FILES:
            if not (hooks_dir / f).is_file():
                problems.append(f"缺少 hooks/{f}")
        hooks_json = hooks_dir / "hooks.json"
        if hooks_json.is_file():
            try:
                data = json.loads(hooks_json.read_text(encoding="utf-8"))
                n = len(data.get("hooks", {}))
                if n != _EXPECTED_HOOK_EVENTS:
                    problems.append(f"hooks 事件数 {n} != 预期 {_EXPECTED_HOOK_EVENTS}")
            except json.JSONDecodeError:
                problems.append("hooks/hooks.json 不是合法 JSON")

    # 规则文件 + ZCode 清单
    if not (plugin_root / "CLAUDE.md").is_file():
        problems.append("缺少 CLAUDE.md")
    if not (plugin_root / ".zcode-plugin" / "plugin.json").is_file():
        problems.append("缺少 .zcode-plugin/plugin.json（ZCode 宿主清单）")

    # 版本一致性
    try:
        from . import PLUGIN_VERSION

        if manifest_ver != PLUGIN_VERSION:
            problems.append(f"manifest 版本 {manifest_ver} 与包版本 {PLUGIN_VERSION} 不一致（可运行 upgrade）")
    except ImportError:
        pass

    print(f"📦 drogon-claude-plugin 结构校验 — {plugin_root}（布局: {layout}）")
    print(f"   插件版本 : {manifest_ver}")
    print(f"   技能数   : {len(skill_names)}")
    print(f"   hooks    : {len(_EXPECTED_HOOK_FILES)} 个文件 / {_EXPECTED_HOOK_EVENTS} 个事件")
    if problems:
        print("   ❌ 发现问题:")
        for p in problems:
            print(f"      - {p}")
        return 1
    print("   ✅ 通过")
    return 0


def cmd_upgrade(args) -> int:
    from . import PLUGIN_VERSION

    try:
        project = _project_dir(args)
        src_root = _find_assets()
        if not src_root.is_dir():
            raise FileNotFoundError(f"未找到插件资产目录（{src_root}）。")
    except (ValueError, FileNotFoundError) as e:
        print(f"❌ {e}", file=sys.stderr)
        return 1

    bundled = _plugin_version(src_root) or PLUGIN_VERSION
    layout, plugin_root = _detect_layout(project)

    # v0.1.x 根目录散装布局 → 清理后迁移到 .drogon-plugin/
    if layout == "legacy":
        removed, skipped = _remove_legacy_layout(project)
        print(f"🔄 已清理 v0.1.x 根目录布局（{len(removed)} 项，迁移到 {_INSTALL_DIR}/）")
        for s in skipped:
            print(f"   ⚠️  跳过 {s}")
        layout = None

    if layout == "v2":
        current = _plugin_version(plugin_root)
        if current == bundled:
            print(f"✅ 已是最新版本 {current}（无需升级）")
            return 0
        print(f"⬆️  {current} → {bundled}")
        shutil.rmtree(plugin_root)
    else:
        print(f"⬆️  安装 {bundled}")

    root = _install_root(project)
    count = _copy_assets(src_root, root)
    (root / _STAMP).write_text(
        json.dumps(
            {
                "source": "pypi:drogon-claude-plugin",
                "cli_version": _version(),
                "plugin_version": bundled,
                "files": count,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"✅ 已升级到 {root}（{count} 个文件 · {bundled}）")
    _print_enable_hint(root)
    return 0


def cmd_uninstall(args) -> int:
    try:
        project = _project_dir(args)
    except ValueError as e:
        print(f"❌ {e}", file=sys.stderr)
        return 1

    removed: list = []

    root = _install_root(project)
    if root.is_dir():
        shutil.rmtree(root)
        removed.append(_INSTALL_DIR)

    legacy_removed, skipped = _remove_legacy_layout(project)
    removed += legacy_removed

    if removed:
        print(f"🗑  已从 {project} 移除: {', '.join(removed)}")
        for s in skipped:
            print(f"   ⚠️  跳过 {s}")
        print("   注意：如曾用 claude plugin install 注册，另需 claude plugin uninstall drogon")
    else:
        print(f"ℹ️   未在 {project} 发现插件资产")
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
        description="安装 / 校验 / 升级 / 卸载 drogon 插件资产（PyPI 发行版，Claude Code / ZCode 双宿主）。",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    for name, help_text, func in (
        ("install", "安装插件资产到 <项目>/.drogon-plugin/", cmd_install),
        ("verify", "校验已安装插件结构", cmd_verify),
        ("upgrade", "升级到随包版本（含 v0.1.x 布局迁移）", cmd_upgrade),
        ("uninstall", "移除已安装插件资产", cmd_uninstall),
    ):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("--target", help="项目根目录（默认当前目录）")
        p.set_defaults(func=func)

    sub.add_parser("version", help="显示版本").set_defaults(func=cmd_version)
    return parser


def main(argv: "list[str] | None" = None) -> int:
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
