#!/usr/bin/env python3
"""workflow 里 action 引用的 SHA↔注释版本对应性校验(第四轮评审 F14)。

pytest 侧 `tests/test_ci_pinning.py` 离线保证"每个 `uses:` 都固定到 40 位 SHA 且行尾有版本
注释";本脚本补上离线做不到的那一半:**注释声称的 tag 必须真的指向上游那个 SHA**。

为什么要它:SHA 固定挡住的是"tag 被重指向后 CI 跑到新代码",而注释是人和 dependabot
之外唯一的版本线索。二者一旦脱钩(SHA 已换、注释没改;或注释写了一个上游根本不存在的
tag),升级比对就拿着假版本当真,固定形同虚设。

用法:
    python scripts/check-action-pinning.py             # 出网核实,不一致退出码 1
    python scripts/check-action-pinning.py --offline   # 只列出解析到的引用,不联网
"""
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
WORKFLOW_DIR = REPO / ".github" / "workflows"

# owner/repo@<40 位十六进制 SHA>
PINNED = re.compile(r"^[\w.-]+/[\w.-]+@[0-9a-f]{40}$")
# `uses:` 可为列表项、映射键或 flow-mapping 成员;键名允许大小写/冒号前空格;值允许 YAML 引号包裹
USES_LINE = re.compile(r"""^\s*(?:-\s*)?(?P<flow>[\[{])?\s*[Uu]ses\s*:\s*(?P<value>.+)$""")
# flow-mapping 里值到第一个 `,`(后继键)或 `}`/`]`(容器闭合)为止
FLOW_VALUE_END = re.compile(r"[,\]}]")
# 版本注释须含"点分版本"或"release/vN"形态;裸数字(如 `# 见 issue 123`)不算
VERSION_IN_COMMENT = re.compile(r"v?\d+\.\d+|release/v\d+")
# 注释里的完整 ref 名(优先三段,退回两段;`release/vN` 是分支形态)
CLAIM = re.compile(r"(release/v\d+|v?\d+\.\d+\.\d+|v?\d+\.\d+)")


def workflow_files() -> "list[Path]":
    return sorted(
        list(WORKFLOW_DIR.glob("*.yml")) + list(WORKFLOW_DIR.glob("*.yaml"))
    )


def scan_uses(lines) -> "list[tuple[int, str, str]]":
    """从 workflow 文本行提取 (lineno, 动作值, 原始行);跳过整行注释与值内注释残留。"""
    out = []
    for lineno, line in enumerate(lines, 1):
        stripped = line.lstrip()
        if stripped.startswith("#"):  # 整行注释
            continue
        m = USES_LINE.match(line)
        if not m:
            continue
        raw_value, _, _comment = m.group("value").partition("#")
        if m.group("flow"):  # flow 形态:`{uses: owner/repo@sha, with: ...}`
            raw_value = FLOW_VALUE_END.split(raw_value, maxsplit=1)[0]
        value = raw_value.strip().strip("'\"")
        if value:
            out.append((lineno, value, line.rstrip()))
    return out


def parse_pinned(lines) -> "list[tuple[int, str, str, str]]":
    """(lineno, owner/repo, sha, 行尾注释) —— 只取固定到 SHA 的第三方引用。"""
    out = []
    for lineno, value, raw in scan_uses(lines):
        if value.startswith("./") or not PINNED.match(value):
            continue
        repo_part, _, sha = value.rpartition("@")
        comment = raw.partition("#")[2]
        out.append((lineno, repo_part, sha, comment))
    return out


def parse_ls_remote(stdout: str) -> "dict[str, str]":
    """`git ls-remote` 输出 → {ref 短名: commit SHA}。

    附注 tag 会同时列出 `refs/tags/vX`(tag 对象)与 `refs/tags/vX^{}`(提交对象),
    workflow 里钉的是提交 SHA,故 `^{}` 形态优先,否则每条固定行都会假红。
    """
    refs: "dict[str, str]" = {}
    for line in stdout.splitlines():
        sha, _, ref = line.partition("\t")
        ref = ref.strip()
        if not ref or len(sha.strip()) != 40:
            continue
        sha = sha.strip()
        if ref.startswith("refs/tags/"):
            name = ref[len("refs/tags/"):]
            if name.endswith("^{}"):
                refs[name[:-3]] = sha
            else:
                refs.setdefault(name, sha)
        elif ref.startswith("refs/heads/"):
            refs[ref[len("refs/heads/"):]] = sha
    return refs


def fetch_refs(repo: str) -> "dict[str, str]":
    """向 GitHub 要该仓库的全量 refs(一次拿全,按仓库缓存)。失败抛 RuntimeError。"""
    cmd = ["git", "ls-remote", "https://github.com/%s" % repo]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise RuntimeError("git ls-remote 无法执行: %s" % e)
    if p.returncode != 0:
        raise RuntimeError("git ls-remote %s 失败: %s" % (repo, p.stderr.strip()[:200]))
    return parse_ls_remote(p.stdout)


def audit(entries, refs_by_repo, errors=None) -> "list[str]":
    """核心比对(纯函数,可离线注入 refs 测试)。

    entries: [(path, lineno, repo, sha, comment)];
    refs_by_repo: {repo: {ref 名: sha}};errors: {repo: 取回失败说明} —— 取不回就红,
    供应链门禁不能因为网络抖动静默放行。
    """
    errors = errors or {}
    problems = []
    for path, lineno, repo, sha, comment in entries:
        loc = "%s:%d" % (path, lineno)
        if repo in errors:
            problems.append("%s: 无法核实 %s 的上游 refs(%s)" % (loc, repo, errors[repo]))
            continue
        m = CLAIM.search(comment or "")
        if not m:
            problems.append("%s: 注释无可解析版本号,无从比对 SHA 对应关系" % loc)
            continue
        claim = m.group(1)
        refs = refs_by_repo.get(repo, {})
        if claim not in refs:
            problems.append(
                "%s: 注释声称 %s@%s,但上游没有该 tag/分支(可能已删、拼错或只是分支名)"
                % (loc, repo, claim)
            )
            continue
        if refs[claim] != sha:
            actual = sorted(n for n, s in refs.items() if s == sha and "." in n)
            problems.append(
                "%s: 注释声称 %s@%s,但该 SHA 实际对应 %s(上游 %s = %s)"
                % (loc, repo, claim, actual or "无同名 ref", claim, refs[claim])
            )
    return problems


def collect_offline_entries() -> "list[tuple[str, int, str, str, str]]":
    """所有 workflow 的固定行(含未固定形态留给离线守卫,这里只取已固定的)。"""
    out = []
    for wf in workflow_files():
        for lineno, repo, sha, comment in parse_pinned(
            wf.read_text(encoding="utf-8").splitlines()
        ):
            out.append((wf.name, lineno, repo, sha, comment))
    return out


def main() -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

    entries = collect_offline_entries()
    if "--offline" in sys.argv:
        for path, lineno, repo, sha, comment in entries:
            print("%s:%d %s @ %s%s" % (path, lineno, repo, sha[:12], "  # " + comment if comment else ""))
        print("解析到 %d 条 SHA 固定引用(未联网)" % len(entries))
        return 0

    repos = sorted({e[2] for e in entries})
    refs_by_repo, errors = {}, {}
    for repo in repos:
        try:
            refs_by_repo[repo] = fetch_refs(repo)
        except RuntimeError as e:
            errors[repo] = str(e)

    problems = audit(entries, refs_by_repo, errors)
    if problems:
        print("❌ action 固定与注释版本不对应:")
        for p in problems:
            print("  - %s" % p)
        return 1
    print("✅ %d 条 SHA 固定引用与注释版本对应(核实于 %d 个上游仓库)" % (len(entries), len(repos)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
