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


def sync() -> int:
    dest_assets = DEST
    if dest_assets.exists():
        shutil.rmtree(dest_assets)
    dest_assets.mkdir(parents=True)

    count = 0
    for name in ASSETS:
        src = REPO_ROOT / name
        if src.is_dir():
            shutil.copytree(src, dest_assets / name)
            count += sum(1 for _ in src.rglob("*") if _.is_file())
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
        src_files = sorted(p for p in src.rglob("*") if p.is_file())
        dst_files = sorted(p for p in dst.rglob("*") if p.is_file())
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