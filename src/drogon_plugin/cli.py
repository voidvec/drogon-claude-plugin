#!/usr/bin/env python3
"""drogon-plugin — CLI 安装器（PyPI 发行版）.

把随包内置的 drogon Claude Code 插件资产安装到目标项目并提示启用，
或对已安装目录做结构校验 / 卸载。

子命令:
  install   [--target DIR] [--scope project|user|local]
  verify    [--target DIR]
  uninstall [--target DIR]
  version
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

# 资产在 wheel 内统一放在 ``drogon_plugin_assets/`` 下（见 pyproject.toml data-files）
_ASSETS_PREFIX = "drogon_plugin_assets"
_PLUGIN_ASSET_DIRS = ("skills", "hooks", ".claude-plugin")
_PLUGIN_FILES = ("CLAUDE.md",)
_EXPECTED_SKILLS = 17
_EXPECTED_HOOKS = 2

# scope 目录名映射（Claude Code 约定）
_SCOPE_DIRS = {
    "user": Path.home() / ".claude" / "plugins",
    "local": Path.home() / ".claude" / "plugins",
    "project": None,  # 项目根（默认）
}

_PKG_VERSION: str | None = None


def _version() -> str:
    """返回已安装发行包的版本；源码树运行时返回 unknown。"""
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
    dev_candidate = here / _ASSETS_PREFIX  # src/drogon_plugin/drogon_plugin_assets/
    if dev_candidate.is_dir():
        return dev_candidate
    # wheel 布局: site-packages/drogon_plugin/drogon_plugin_assets/
    return here / _ASSETS_PREFIX


# ---------------------------------------------------------------------------
# 资产复制 / 管理
# ---------------------------------------------------------------------------


def _list_assets(root: Path):
    return (p for p in root.rglob("*") if p.is_file())


def _copy_assets(src_root: Path, target_root: Path) -> int:
    """把 src_root 下所有资产复制到 target_root，返回文件数。"""
    count = 0
    for f in _list_assets(src_root):
        rel = f.relative_to(src_root)
        dest = target_root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, dest)
        count += 1
    return count


def _load_manifest(target_root: Path) -> dict:
    p = target_root / ".claude-plugin" / "plugin.json"
    if not p.is_file():
        raise FileNotFoundError(f"缺少插件清单: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def _plugin_version(target_root: Path) -> str:
    return str(_load_manifest(target_root).get("version", "?"))


def _resolve_target(args) -> Path:
    """子命令用: --target > --scope > 当前目录。"""
    if args.target:
        return Path(args.target).expanduser().resolve()
    if getattr(args, "scope", None):
        if args.scope == "project":
            return Path.cwd().resolve()
        d = _SCOPE_DIRS.get(args.scope)
        if d:
            return d.resolve()
    return Path.cwd().resolve()


# ---------------------------------------------------------------------------
# 子命令
# ---------------------------------------------------------------------------


def cmd_install(args) -> int:
    from . import PLUGIN_VERSION

    target = _resolve_target(args)
    try:
        src_root = _find_assets()
        if not src_root.is_dir():
            raise FileNotFoundError(
                f"未找到插件资产目录（{src_root}）。请确认包安装完整。"
            )
        count = _copy_assets(src_root, target)
    except FileNotFoundError as e:
        print(f"❌ {e}", file=sys.stderr)
        return 1

    stamp = target / ".drogon-plugin-installed.json"
    try:
        manifest_version = _plugin_version(target)
    except FileNotFoundError:
        manifest_version = PLUGIN_VERSION
    stamp.write_text(
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

    print(f"✅ 已安装 drogon 插件资产到 {target}")
    print(f"   复制 {count} 个文件 · 插件版本 {manifest_version}")
    print("   下一步:")
    print("     1) cd <你的 drogon 项目>")
    print("     2) claude plugin install ../drogon-claude-plugin --scope project")
    print("       （或如果已通过 marketplace 添加: claude plugin install drogon）")
    return 0


def cmd_verify(args) -> int:
    target = _resolve_target(args)
    try:
        manifest = _load_manifest(target)
    except FileNotFoundError as e:
        print(f"❌ {e}", file=sys.stderr)
        return 1

    manifest_ver = str(manifest.get("version", "?"))
    problems: list[str] = []
    skill_names: list[str] = []

    # 技能
    skills_dir = target / "skills"
    if not skills_dir.is_dir():
        problems.append("缺少 skills/ 目录")
    else:
        skill_names = sorted(
            d.name for d in skills_dir.iterdir() if d.is_dir()
        )
        if len(skill_names) != _EXPECTED_SKILLS:
            problems.append(f"技能数 {len(skill_names)} != 预期 {_EXPECTED_SKILLS}")
        for n in skill_names:
            if not (skills_dir / n / "SKILL.md").is_file():
                problems.append(f"技能 {n} 缺少 SKILL.md")

    # hooks
    hooks_dir = target / "hooks"
    if not hooks_dir.is_dir():
        problems.append("缺少 hooks/ 目录")
    else:
        hooks_json = hooks_dir / "hooks.json"
        if not hooks_json.is_file():
            problems.append("缺少 hooks/hooks.json")
        else:
            try:
                data = json.loads(hooks_json.read_text(encoding="utf-8"))
                n = len(data.get("hooks", {}))
                if n != _EXPECTED_HOOKS:
                    problems.append(f"hooks 数 {n} != 预期 {_EXPECTED_HOOKS}")
            except json.JSONDecodeError:
                problems.append("hooks/hooks.json 不是合法 JSON")

        if not (hooks_dir / "posttooluse.py").is_file():
            problems.append("缺少 hooks/posttooluse.py")

    # CLAUDE.md
    if not (target / "CLAUDE.md").is_file():
        problems.append("缺少 CLAUDE.md")

    # 版本一致性
    try:
        from . import PLUGIN_VERSION

        if manifest_ver := manifest.get("version"):
            if str(manifest_ver) != PLUGIN_VERSION:
                problems.append(
                    f"manifest 版本 {manifest_ver} 与包版本 {PLUGIN_VERSION} 不一致"
                )
    except ImportError:
        pass

    print(f"📦 drogon-claude-plugin 结构校验 — {target}")
    print(f"   插件版本 : {manifest_ver}")
    print(f"   技能数   : {len(skill_names)}")
    print(f"   hooks    : {_EXPECTED_HOOKS} (SessionStart + PostToolUse)")
    if problems:
        print("   ❌ 发现问题:")
        for p in problems:
            print(f"      - {p}")
        return 1
    print("   ✅ 通过")
    return 0


def cmd_uninstall(args) -> int:
    target = _resolve_target(args)
    removed: list[str] = []
    for name in (*_PLUGIN_ASSET_DIRS, *_PLUGIN_FILES):
        p = target / name
        if p.is_dir() and not p.is_symlink():
            shutil.rmtree(p)
            removed.append(name)
        elif p.is_file():
            p.unlink()
            removed.append(name)
    stamp = target / ".drogon-plugin-installed.json"
    if stamp.is_file():
        stamp.unlink()
        removed.append(".drogon-plugin-installed.json")

    if removed:
        print(f"🗑  已从 {target} 移除: {', '.join(removed)}")
    else:
        print(f"ℹ️   未在 {target} 发现插件资产")
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
        prog="drogon-plugin",
        description="安装 / 校验 / 卸载 drogon Claude Code 插件资产（PyPI 发行版）。",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_install = sub.add_parser("install", help="安装插件资产到目标项目")
    p_install.add_argument("--target")
    p_install.add_argument("--scope", choices=["project", "user", "local"])
    p_install.set_defaults(func=cmd_install)

    p_verify = sub.add_parser("verify", help="校验已安装插件结构")
    p_verify.add_argument("--target")
    p_verify.set_defaults(func=cmd_verify)

    p_uninstall = sub.add_parser("uninstall", help="移除已安装插件资产")
    p_uninstall.add_argument("--target")
    p_uninstall.set_defaults(func=cmd_uninstall)

    sub.add_parser("version", help="显示版本").set_defaults(func=cmd_version)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if not hasattr(args, "func"):
        parser.print_help()
        return 0

    # 只有需要目标路径的子命令才设置 target
    if getattr(args, "func", None) in (cmd_install, cmd_verify, cmd_uninstall):
        args.target = _resolve_target(args)

    try:
        return args.func(args)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())