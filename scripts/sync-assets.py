#!/usr/bin/env python3
"""同步插件资产到 PyPI 包目录.

将仓库根下的 {skills, hooks, .claude-plugin, CLAUDE.md} 同步复制到
``src/drogon_plugin/drogon_plugin_assets/``，供 setuptools 打包进 wheel。

用法:
    python scripts/sync-assets.py [--check]

--check 只校验是否最新（CI 用），不一致时退出码 1。
"""
import filecmp
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ASSETS = ("skills", "hooks", ".claude-plugin", ".zcode-plugin", ".codex-plugin")
# 注意:.agents/(Codex 对本仓库的 marketplace 发现入口)是仓库级元数据,
# 不进发行资产——不能被 CLI 装进用户项目。
FILES = ("CLAUDE.md", "AGENTS.md", "GEMINI.md", "gemini-extension.json")
DEST = REPO_ROOT / "src" / "drogon_plugin" / "drogon_plugin_assets"

# 需要排除的中间产物目录（如 Python 字节码缓存）
IGNORE_DIRS = {"__pycache__"}


def _iter_files(root: Path):
    """递归列出 root 下所有文件，排除 IGNORE_DIRS。"""
    for file in root.rglob("*"):
        if file.is_file() and not any(part in IGNORE_DIRS for part in file.parts):
            yield file


def sync() -> int:
    dest_assets = DEST
    if dest_assets.exists():
        shutil.rmtree(dest_assets)
    dest_assets.mkdir(parents=True)

    count = 0
    for name in ASSETS:
        src = REPO_ROOT / name
        if src.is_dir():
            # 逐文件复制并跳过忽略目录（copytree 的 ignore 回调）
            def _ignore(dir_path, names, _src=src):
                return [n for n in names if n in IGNORE_DIRS]

            shutil.copytree(src, dest_assets / name, ignore=_ignore)
            count += sum(1 for _ in _iter_files(src))
    for name in FILES:
        src = REPO_ROOT / name
        if src.is_file():
            shutil.copy2(src, dest_assets / name)
            count += 1
    return count


def _all_files_raw(root: Path):
    """不做忽略过滤地列出所有文件(用于检测目标侧是否混入中间产物)。"""
    for p in root.rglob("*"):
        if p.is_file():
            yield p


def check() -> bool:
    """比较源资产与同步目标是否一致。"""
    # 目标侧不允许出现中间产物——与 sync-assets.mjs 的严格性对齐。
    # (copytree/cpSync 曾把 __pycache__ 原样带进包,导致包内多出 .pyc)
    if DEST.is_dir():
        for f in _all_files_raw(DEST):
            if any(part in IGNORE_DIRS for part in f.parts):
                return False
    for name in ASSETS:
        src = REPO_ROOT / name
        dst = DEST / name
        if not dst.is_dir():
            return False
        src_files = sorted(_iter_files(src))
        dst_files = sorted(_iter_files(dst))
        if len(src_files) != len(dst_files):
            return False
        for s, d in zip(src_files, dst_files):
            if s.relative_to(src) != d.relative_to(dst):
                return False
            if not filecmp.cmp(s, d, shallow=False):
                return False
    for name in FILES:
        src = REPO_ROOT / name
        dst = DEST / name
        if src.is_file():
            if not dst.is_file() or not filecmp.cmp(src, dst, shallow=False):
                return False
    return True


def _utf8_stdio() -> None:
    # Windows 下 stdout 为管道时默认 cp1252,print ✅/中文 会抛 UnicodeEncodeError
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass


def main() -> int:
    _utf8_stdio()
    if len(sys.argv) > 1 and sys.argv[1] == "--check":
        if not DEST.is_dir():
            print("❌ 资产目录缺失，请先运行 python scripts/sync-assets.py")
            return 1
        if check():
            print("✅ 插件资产与源码同步")
            return 0
        print("❌ 插件资产与源码不一致，请运行 python scripts/sync-assets.py")
        return 1

    count = sync()
    print(f"✅ 已同步 {count} 个资产文件到 {DEST.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())