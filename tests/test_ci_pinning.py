# -*- coding: utf-8 -*-
"""CI 供应链守卫:workflow 引用的第三方 action 必须按 commit SHA 固定(L7)。

tag 可被仓库所有权转移/强推重指向(maintainer 接管事故均发生过),未固定的
`uses:` 让 CI 在不可控代码上跑 secrets。publish.yml 带 PyPI/npm 凭证,尤其致命。
"""
import re
from pathlib import Path

WORKFLOWS = sorted(
    list((Path(__file__).resolve().parents[1] / ".github" / "workflows").glob("*.yml"))
    + list((Path(__file__).resolve().parents[1] / ".github" / "workflows").glob("*.yaml"))
)

# owner/repo@<40 位十六进制 SHA>
PINNED = re.compile(r"^[\w.-]+/[\w.-]+@[0-9a-f]{40}$")
# `uses:` 可为列表项或映射键;键名允许大小写/冒号前空格;值允许 YAML 引号包裹
USES_LINE = re.compile(r"""^\s*(?:-\s*)?[Uu]ses\s*:\s*(.+)$""")
# 版本注释须含"点分版本"或"release/vN"形态;裸数字(如 `# 见 issue 123`)不算
VERSION_IN_COMMENT = re.compile(r"v?\d+\.\d+|release/v\d+")


def scan_uses(lines):
    """从 workflow 文本行提取 (lineno, 动作值, 原始行);跳过整行注释与值内注释残留。"""
    out = []
    for lineno, line in enumerate(lines, 1):
        stripped = line.lstrip()
        if stripped.startswith("#"):  # 整行注释
            continue
        m = USES_LINE.match(line)
        if not m:
            continue
        raw_value, _, _comment = m.group(1).partition("#")
        value = raw_value.strip().strip("'\"")
        if value:
            out.append((lineno, value, line.rstrip()))
    return out


def _all_uses():
    for wf in WORKFLOWS:
        for lineno, value, raw in scan_uses(wf.read_text(encoding="utf-8").splitlines()):
            yield wf, lineno, value, raw


def test_workflows_exist():
    assert WORKFLOWS, "未找到 workflow 文件——测试路径失效"


def test_all_actions_pinned_to_full_sha():
    offenders = []
    for wf, lineno, value, raw in _all_uses():
        if value.startswith("./"):  # 本地复合 action 无需固定
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
    for wf, lineno, value, raw in _all_uses():
        if value.startswith("./"):
            continue
        comment = raw.partition("#")[2]
        if not VERSION_IN_COMMENT.search(comment):
            missing.append(f"{wf.name}:{lineno}: {raw.strip()}")
    assert not missing, (
        "SHA 固定行缺少版本注释(应形如 `# v4.2.2` / `# release/v1`):\n  "
        + "\n  ".join(missing)
    )


# ---------------------------------------------------------------------------
# 守卫自身的正/反例(评审补漏:检测器不能静默漏形态,注释断言不能被裸数字骗过)
# ---------------------------------------------------------------------------

SHA40 = "0123456789abcdef0123456789abcdef01234567"


def test_detector_catches_tag_and_quote_forms():
    cases = {
        "      - uses: actions/checkout@v4": "actions/checkout@v4",
        "      - uses:  actions/setup-python@v5 ": "actions/setup-python@v5",
        '        uses: "actions/setup-node@v4"': "actions/setup-node@v4",
        "        uses: 'softprops/action-gh-release@v2' # v2.0.0": "softprops/action-gh-release@v2",
        "        uses: owner/repo@%s # v1.2.3" % SHA40: "owner/repo@" + SHA40,
        "        uses: ./local/composite": "./local/composite",
    }
    got = {lineno: value for lineno, value, _ in scan_uses(cases.keys())}
    assert list(got.values()) == list(cases.values()), f"值解析失真: {got}"


def test_detector_skips_comments_and_non_uses_keys():
    lines = [
        "# - uses: evil/action@v1(整行注释不算引用)",
        "  name: uses: fake",          # 值不是引用
        "  steps:",
    ]
    assert scan_uses(lines) == []


def test_bare_number_comment_is_not_a_version_annotation():
    """正向对照:评审实证 `# 见 issue 123` 曾骗过宽松断言 → 收紧后必须拒绝。"""
    assert not VERSION_IN_COMMENT.search(" 见 issue 123")
    assert VERSION_IN_COMMENT.search(" v4.4.0")
    assert VERSION_IN_COMMENT.search(" release/v1 HEAD")
    assert VERSION_IN_COMMENT.search(" 固定至 v1.14.2 线")
