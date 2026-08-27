#!/usr/bin/env python3
"""端到端冒烟测试：验证 PyPI CLI 安装/校验/卸载 到临时目录。

用法:
    python scripts/dev-smoke-test.py [--keep]

要求: 先安装本包（pip install -e . 或 .whl）.
"""
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path


def run(cmd, cwd=None):
    print(f"$ {' '.join(cmd)}")
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    print(r.stdout, end="")
    if r.stderr:
        print(r.stderr, file=sys.stderr, end="")
    return r.returncode, r.stdout


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", action="store_true")
    args = ap.parse_args()

    tmp = Path(tempfile.mkdtemp(prefix="drogon-smoke-"))
    target = tmp / "proj"
    target.mkdir()

    # version
    rc, _ = run(["drogon-claude-plugin", "version"])
    if rc != 0:
        return 1

    # install
    rc, _ = run(["drogon-claude-plugin", "install", "--target", str(target)])
    if rc != 0:
        return 1
    for rel in (".claude-plugin/plugin.json", "CLAUDE.md", "hooks/posttooluse.py"):
        if not (target / rel).is_file():
            print(f"❌ 缺少 {rel}")
            return 1
    if len(list((target / "skills").iterdir())) != 17:
        print(f"❌ skills 数 != 17: {list((target / 'skills').iterdir())}")
        return 1

    # verify
    rc, out = run(["drogon-claude-plugin", "verify", "--target", str(target)])
    if rc != 0 or "✅ 通过" not in out:
        print("❌ verify 未通过")
        return 1

    # uninstall
    rc, _ = run(["drogon-claude-plugin", "uninstall", "--target", str(target)])
    if rc != 0 or (target / "skills").exists():
        print("❌ uninstall 未清空")
        return 1

    print("✅ PyPI CLI 冒烟测试通过")
    if not args.keep:
        import shutil

        shutil.rmtree(tmp, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())