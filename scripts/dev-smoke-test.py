#!/usr/bin/env python3
"""端到端冒烟测试：验证 PyPI CLI 安装/校验/升级/卸载 到临时目录。

用法:
    python scripts/dev-smoke-test.py [--keep]

要求: 先安装本包（pip install -e . 或 .whl）.
所有子进程调用均为显式参数列表 + shell=False，不经过任何 shell。
"""
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path


def run(cli_args):
    """以参数列表运行 drogon-claude-plugin（shell=False，无拼接）。"""
    print(f"$ drogon-claude-plugin {' '.join(cli_args)}")
    r = subprocess.run(
        ["drogon-claude-plugin", *cli_args],
        capture_output=True,
        text=True,
        shell=False,
    )
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
    plugin = target / ".drogon-plugin"

    # 项目自有文件：安装/升级/卸载全程不得触碰
    own_md = target / "CLAUDE.md"
    own_md.write_text("# 我的项目\n", encoding="utf-8")

    # version
    rc, _ = run(["version"])
    if rc != 0:
        return 1

    # install → .drogon-plugin/
    rc, _ = run(["install", "--target", str(target)])
    if rc != 0:
        return 1
    for rel in (
        ".claude-plugin/plugin.json",
        ".zcode-plugin/plugin.json",
        "CLAUDE.md",
        "hooks/hooks.json",
        "hooks/run-hook.cmd",
        "hooks/session-start",
        "hooks/post-tool-use",
        "hooks/posttooluse.py",
    ):
        if not (plugin / rel).is_file():
            print(f"❌ 缺少 {rel}")
            return 1
    n_skills = len(list((plugin / "skills").iterdir()))
    if n_skills != 22:
        print(f"❌ skills 数 {n_skills} != 22")
        return 1
    if own_md.read_text(encoding="utf-8") != "# 我的项目\n":
        print("❌ 安装覆盖了项目自有 CLAUDE.md")
        return 1

    # verify
    rc, out = run(["verify", "--target", str(target)])
    if rc != 0 or "✅ 通过" not in out:
        print("❌ verify 未通过")
        return 1

    # upgrade（同版本 → 提示已是最新）
    rc, out = run(["upgrade", "--target", str(target)])
    if rc != 0 or "已是最新" not in out:
        print("❌ upgrade(同版本) 未通过")
        return 1

    # uninstall
    rc, _ = run(["uninstall", "--target", str(target)])
    if rc != 0 or plugin.exists():
        print("❌ uninstall 未清空")
        return 1
    if own_md.read_text(encoding="utf-8") != "# 我的项目\n":
        print("❌ 卸载误删了项目自有 CLAUDE.md")
        return 1

    print("✅ PyPI CLI 冒烟测试通过")
    if not args.keep:
        import shutil

        shutil.rmtree(tmp, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
