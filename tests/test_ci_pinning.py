# -*- coding: utf-8 -*-
"""CI 供应链守卫:workflow 引用的第三方 action 必须按 commit SHA 固定(L7)。

tag 可被仓库所有权转移/强推重指向(maintainer 接管事故均发生过),未固定的
`uses:` 让 CI 在不可控代码上跑 secrets。publish.yml 带 PyPI/npm 凭证,尤其致命。

解析器与 SHA↔注释对应校验共用 `scripts/check-action-pinning.py` 的**同一实现**
(离线断言在这里跑,联网比对由该脚本作为独立 CI 步骤跑),避免两份正则各漂各的。
"""
import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "check_action_pinning", REPO_ROOT / "scripts" / "check-action-pinning.py"
)
pinning = importlib.util.module_from_spec(_spec)
sys.modules["check_action_pinning"] = pinning
_spec.loader.exec_module(pinning)

WORKFLOWS = pinning.workflow_files()
PINNED = pinning.PINNED
VERSION_IN_COMMENT = pinning.VERSION_IN_COMMENT
scan_uses = pinning.scan_uses
SHA40 = "0123456789abcdef0123456789abcdef01234567"


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


def test_detector_catches_flow_mapping_uses_forms():
    """F14:flow-mapping 写法(`- {uses: ...}` / `{ uses: '...', with: {...} }`)是
    合法 YAML,GitHub 照样解析成引用。此前 USES_LINE 只认块式 `- uses:`,这种形态
    会整行漏抓——未固定引用就能藏在 flow 写法里带着 secrets 跑。"""
    cases = {
        "        - {uses: actions/checkout@v4}": "actions/checkout@v4",
        "        - { uses: 'actions/setup-python@v5', python-version: '3.11' }":
            "actions/setup-python@v5",
        "      - {uses: softprops/action-gh-release@v2, files: dist/*}":
            "softprops/action-gh-release@v2",
    }
    got = [value for _lineno, value, _raw in scan_uses(cases.keys())]
    assert got == list(cases.values()), f"flow-mapping 形态漏抓/解析失真: {got}"


def test_flow_mapping_uses_is_flagged_when_unpinned():
    """端到端:把 flow 形态塞进 workflow 文本,守卫必须报出未固定(offender),
    而不是安静放行。"""
    lines = ["      - {uses: actions/checkout@v4}"]
    offenders = [
        value for _lineno, value, _raw in scan_uses(lines)
        if not value.startswith("./") and not PINNED.match(value)
    ]
    assert offenders == ["actions/checkout@v4"], f"未固定引用被放过: {offenders}"


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


# ---------------------------------------------------------------------------
# 批次④-F14b:SHA↔注释版本对应性(联网比对的纯逻辑,离线注入 refs)
# ---------------------------------------------------------------------------

OTHER40 = "ffffffffffffffffffffffffffffffffffffffff"
REFS = {"actions/checkout": {"v4.4.0": SHA40, "v4.3.0": OTHER40, "main": "2" * 40}}


def _entry(sha=SHA40, comment=" v4.4.0", repo="actions/checkout"):
    return [("ci.yml", 30, repo, sha, comment)]


def test_audit_passes_when_comment_matches_pinned_sha():
    """基准:注释声称的 tag 在上游确实指向钉住的 SHA → 无问题。"""
    assert pinning.audit(_entry(), REFS) == []


def test_audit_flags_comment_pointing_at_a_different_sha():
    """核心缺口:注释说 v4.4.0 而上游 v4.4.0 已是另一个提交(强推/tag 漂移)。"""
    problems = pinning.audit(_entry(sha=OTHER40, comment=" v4.4.0"), REFS)
    assert len(problems) == 1, problems
    assert "v4.4.0" in problems[0] and SHA40 in problems[0], (
        "问题须同时含声称版本与 SHA 实际对应的 tag,否则无法定位:%s" % problems[0]
    )


def test_audit_flags_claim_absent_upstream():
    """注释写了一个上游不存在的 tag(拼错/已删/其实是分支名)→ 必须红。"""
    problems = pinning.audit(_entry(comment=" v9.9.9"), REFS)
    assert any("v9.9.9" in p for p in problems), problems


def test_audit_flags_unparsable_comment():
    problems = pinning.audit(_entry(comment=" 见 issue 123"), REFS)
    assert any("版本号" in p for p in problems), problems


def test_audit_fails_closed_when_remote_unreachable():
    """网络/限流不能变成静默绿灯:取不回 refs 也要报。"""
    problems = pinning.audit(_entry(), {}, {"actions/checkout": "git ls-remote 失败: 403"})
    assert any("无法核实" in p for p in problems), problems


def test_audit_accepts_comment_mentioning_several_versions():
    """升级注记里新旧版本号同时出现(`bumped from v4.3.0 to v4.4.0`)是人写注释的
    常态:钉住的 SHA 只要对应其中**任一**声称版本就该放行,否则审计作业会假红。"""
    problems = pinning.audit(_entry(comment=" bumped from v4.3.0 to v4.4.0"), REFS)
    assert problems == [], problems


def test_audit_flags_comment_when_no_claimed_version_matches():
    """反向对照:注记提到多个版本但没有一个对应钉住的 SHA(整条注释说谎)仍必须红,
    并把所有声称版本都列出来,便于判断是漏改还是改错。"""
    pinned = "3" * 40  # 上游没有任何 ref 指向它
    problems = pinning.audit(_entry(sha=pinned, comment=" bumped from v4.4.0 to v4.3.0"), REFS)
    assert len(problems) == 1, problems
    assert "v4.4.0" in problems[0] and "v4.3.0" in problems[0], problems[0]
    assert "不对应" in problems[0], problems[0]


def test_main_fails_closed_when_nothing_parsed(monkeypatch, capsys):
    """审计作业不能因为"一条固定引用都没解析到"就静默绿(workflow 目录改名、
    引用形态整体漂出解析面都会这样)。"""
    monkeypatch.setattr(pinning, "collect_offline_entries", lambda: [])
    assert pinning.main() == 1
    assert "解析到" in capsys.readouterr().out, "红得要说清原因"


def test_parse_ls_remote_prefers_dereferenced_annotated_tag():
    """附注 tag 在 ls-remote 里有两行(tag 对象 + ^{} 提交对象),钉的是提交 SHA;
    取错一行会让每条固定行都假红。"""
    stdout = (
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\trefs/tags/v1.14.2\n"
        + SHA40 + "\trefs/tags/v1.14.2^{}\n"
        + OTHER40 + "\trefs/heads/release/v1\n"
    )
    refs = pinning.parse_ls_remote(stdout)
    assert refs["v1.14.2"] == SHA40, refs
    assert refs["release/v1"] == OTHER40, refs


def test_parse_pinned_skips_unpinned_and_local_refs():
    lines = [
        "      - uses: actions/checkout@v4",              # 未固定 → 留给离线守卫
        "      - uses: ./local/composite # v1.0.0",       # 本地 action 无上游
        "      - uses: o/r@%s # v1.2.3" % SHA40,
    ]
    assert pinning.parse_pinned(lines) == [(3, "o/r", SHA40, " v1.2.3")]


def test_repo_workflows_have_consistent_annotations_offline():
    """集成:真实 workflow 的固定行都能解析出(仓库, SHA, 声称版本),
    联网比对才有输入(解析不到就是这里红,而不是静默少核几条)。"""
    entries = pinning.collect_offline_entries()
    assert len(entries) >= 5, "解析到的固定引用过少,守卫空转:%s" % entries
    for path, lineno, repo, sha, comment in entries:
        assert pinning.CLAIM.search(comment), "%s:%d 注释解析不出版本:%r" % (path, lineno, comment)
