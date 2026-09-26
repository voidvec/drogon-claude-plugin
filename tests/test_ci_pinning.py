# -*- coding: utf-8 -*-
"""CI 供应链守卫:workflow 引用的第三方 action 必须按 commit SHA 固定(L7)。

tag 可被仓库所有权转移/强推重指向(maintainer 接管事故均发生过),未固定的
`uses:` 让 CI 在不可控代码上跑 secrets。publish.yml 带 PyPI/npm 凭证,尤其致命。
"""
import re
from pathlib import Path

WORKFLOWS = sorted((Path(__file__).resolve().parents[1] / ".github" / "workflows").glob("*.yml"))

# owner/repo@<40 位十六进制 SHA>(允许 @sha#v1.2.3 无空格注释变体)
PINNED = re.compile(r"^[\w.-]+/[\w.-]+@[0-9a-f]{40}$")
USES_LINE = re.compile(r"^\s*(?:-\s+)?uses:\s*(\S+)")


def _uses_values(path: Path):
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if "#" in line.split("uses:")[0]:  # 整行注释
            continue
        m = USES_LINE.match(line)
        if m:
            yield lineno, m.group(1), line


def test_workflows_exist():
    assert WORKFLOWS, "未找到 workflow 文件——测试路径失效"


def test_all_actions_pinned_to_full_sha():
    offenders = []
    for wf in WORKFLOWS:
        for lineno, value, raw in _uses_values(wf):
            # 本地复合 action(./...)无需固定;其余一律要求全 40 位 SHA
            if value.startswith("./"):
                continue
            if not PINNED.match(value):
                offenders.append(f"{wf.name}:{lineno}: {raw.strip()}")
    assert not offenders, (
        "以下 action 引用未按 commit SHA 固定(L7 复发,tag 可被重指向):\n  "
        + "\n  ".join(offenders)
    )


def test_pinned_lines_document_source_tag():
    """SHA 不可读,行尾必须注明对应 tag/分支,否则升级时无从比对版本。"""
    missing = []
    for wf in WORKFLOWS:
        for lineno, value, raw in _uses_values(wf):
            if value.startswith("./"):
                continue
            comment = raw.split("#", 1)[1].strip() if "#" in raw else ""
            if not re.search(r"v?\d[\w.\-/]*", comment):
                missing.append(f"{wf.name}:{lineno}: {raw.strip()}")
    assert not missing, (
        "SHA 固定行缺少版本注释(应形如 `# v4.2.2` / `# release/v1 分支 HEAD`):\n  "
        + "\n  ".join(missing)
    )
