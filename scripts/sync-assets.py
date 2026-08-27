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
ASSETS = ("skills", "hooks", ".claude-plugin")
FILES = ("CLAUDE.md",)
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
    for name in ("CLAUDE.md",):
        src = REPO_ROOT / name
        if src.is_file():
            shutil.copy2(src, dest_assets / name)
            count += 1
    return count


def check() -> bool:
    """比较源资产与同步目标是否一致。"""
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
    return True


def main() -> int:
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