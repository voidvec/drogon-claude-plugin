"""Violation-scanner tests, now **rule-level**.

Every rule in hooks/posttooluse.py must have at least one positive fixture
(must match — guards against false negatives) and at least one negative
fixture (must NOT match — guards against false positives). A rule without a
negative fixture is a rule whose false positives nobody would notice, so the
suite fails if one is missing.

It also keeps the v0.1.0 regression guards: callback-variable naming freedom,
and case-sensitive C++ identifiers so isDone()/task.done never trigger done().

Run:  python -m pytest tests/test_posttooluse.py
"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOK = REPO_ROOT / "hooks" / "posttooluse.py"

spec = importlib.util.spec_from_file_location("posttooluse", HOOK)
ptu = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ptu)


# ---------------------------------------------------------------------------
# Rule-level fixtures: rule_id -> (positive, negative)
# ---------------------------------------------------------------------------

RULE_FIXTURES = {
    # C++ rules
    "CPP.001": (
        "void init() { FILTER_ADD(MyFilter); }",
        "app().registerFilter(std::make_shared<MyFilter>());",
    ),
    "CPP.002": (
        "ADD_MIDDLEWARE(Log);",
        "app().registerMiddleware(std::make_shared<Log>());",
    ),
    "CPP.003": (
        'METHOD_LIST_ADD(begin, "/ws", Get);',
        'WS_PATH_ADD("/ws", Get);',
    ),
    "CPP.004": (
        "auto c = app().createDbClient();",
        "app().addDbClient(conf);",
    ),
    "CPP.005": (
        "AsyncTask h() { auto r = co_await f(); }",
        "AsyncTask h() { try { auto r = co_await f(); } catch (...) {} }",
    ),
    "CPP.006": (
        "class M : public HttpMiddleware<M, false> { void invoke(...) { co_await x; } }",
        "class M : public HttpCoroMiddleware<M, false> { Task<HttpResponsePtr> invoke(...) { auto r = co_await next; } };",
    ),
    "CPP.007": (
        "auto r = client->sendRequest(req);",
        "client->sendRequest(req, [this](ReqResult r, HttpResponsePtr resp) {});",
    ),
    "CPP.008": (
        'auto &v = req->session()->operator[]("k");',
        'auto uid = req->session()->getOptional<int>("userId");',
    ),
    "CPP.009": (
        "void h(const HttpRequestPtr &req) { app().registerSyncAdvice(cb); }",
        "int main() { app().registerSyncAdvice(cb); app().run(); }",
    ),
    # CSP rules
    "CSP.001": ("<div>{{ name }}</div>", "<div>[[ name ]]</div>"),
    "CSP.002": ("<%raw%>x</%raw%>", "<%view header %>"),
    "CSP.003": ("<%viewpath a %>", "<%view header %>"),
    "CSP.004": ("<p>@@key@@</p>", "<%c++ auto v = @@; %>"),
    "CSP.005": ("<%extends base %>", "<%layout base %>"),
    "CSP.006": ("{% if ok %}y{% end %}", "{% key %}"),
    # Config rules
    "CFG.001": ('{"db_clients": [{"password": "x"}]}', '{"passwd": "x"}'),
    "CFG.002": ('{"username": "root"}', '{"user": "root"}'),
    "CFG.003": ('{"ssl": "true"}', '{"ssl": true}'),
    # Test rules
    "TEST.001": ("TEST(P) { std::thread t([&]{ done(); }); }", "CHECK(task.isDone());"),
    "TEST.002": ("ASSERT_EQ(a, b);", "CHECK(x == 1);"),
    "TEST.003": ("auto c = app().createDbClient();", "app().addDbClient(conf);"),
}


def _rule(rule_id):
    for r in ptu.ALL_RULES:
        if r.rule_id == rule_id:
            return r
    raise AssertionError(f"unknown rule {rule_id}")


def test_every_rule_has_a_stable_unique_id():
    ids = [r.rule_id for r in ptu.ALL_RULES]
    assert len(ids) == len(set(ids)), f"duplicate rule_id: {ids}"
    for r in ptu.ALL_RULES:
        assert r.rule_id, "empty rule_id"
        assert r.severity in ("error", "warning"), f"{r.rule_id}: bad severity {r.severity}"
        assert r.guide, f"{r.rule_id}: missing guide (fix pointer to a skill)"


def test_every_rule_has_positive_and_negative_fixtures():
    """No rule may be shipped without both a positive and a negative fixture."""
    missing = sorted(set(r.rule_id for r in ptu.ALL_RULES) - set(RULE_FIXTURES))
    assert not missing, f"rules without fixtures (false positive/negative unguarded): {missing}"


@pytest.mark.parametrize("rule_id", sorted(RULE_FIXTURES))
def test_rule_matches_positive_fixture(rule_id):
    rule = _rule(rule_id)
    positive, _ = RULE_FIXTURES[rule_id]
    assert ptu.scan_text(positive, [rule]), f"{rule_id}: positive fixture did not match"


@pytest.mark.parametrize("rule_id", sorted(RULE_FIXTURES))
def test_rule_does_not_match_negative_fixture(rule_id):
    rule = _rule(rule_id)
    _, negative = RULE_FIXTURES[rule_id]
    hits = [h.rule_id for h in ptu.scan_text(negative, [rule])]
    assert not hits, f"{rule_id}: false positive on its negative fixture"


# ---------------------------------------------------------------------------
# v0.1.0 regression guards (cross-rule, not rule-specific)
# ---------------------------------------------------------------------------

CPP_NO_MATCH = [
    # Regression v0.1.0 §4.1: any callback variable name is legal now.
    ("cb naming is free", "std::function<void(const HttpResponsePtr &)> &&cb"),
    ("cbPtr naming", "auto cbPtr = std::make_shared<std::function<void(const HttpResponsePtr &)>>(std::move(cb));"),
    # Regression v0.1.0 §4.2: case-sensitive identifiers.
    ("isDone is not done()", "int ok = task.isDone();"),
    ("task.done is not done()", "bool x = task.done;"),
    ("sendRequestCoro is fine", "auto resp = co_await client->sendRequestCoro(req);"),
    ("Task<HttpResponsePtr> coroutine", "Task<HttpResponsePtr> h() { co_return resp; }"),
    ("normal middleware", "class M : public HttpMiddleware<M, false> { void invoke(const HttpRequestPtr &, NextCallback &&nCb, Callback &&mCb) { nCb(std::move(mCb)); } }"),
]


def test_cpp_rules_do_not_overmatch_legal_code():
    for label, code in CPP_NO_MATCH:
        hits = [h.rule_id for h in ptu.scan_text(code, ptu.CPP_RULES)]
        assert not hits, f"false positive: {label} -> {hits}"


def test_advice_registration_in_main_is_not_flagged():
    """CPP.009 must not fire on the correct pattern (register before run())."""
    legal = "int main() { app().registerSyncAdvice(cb); app().registerBeginningAdvice(cb2); app().run(); }"
    assert not ptu.scan_text(legal, [ _rule("CPP.009") ])


def test_file_category_routing():
    cases = {
        "src/UserCtrl.cc": "cpp",
        "include/a.h": "cpp",
        "views/Home.csp": "csp",
        "config.json": "config",
        "conf/config.yaml": "config",
        "tests/test_login.cc": "test",
        "test/main.cc": "test",
        "src/util_test.cc": "test",
        "src/main.cc": "cpp",
        "docs/readme.md": None,
        "Cargo.toml": None,
        # 回归(C3):裸子串判定 `'test' in base` 曾把下列普通源文件判成测试文件,
        # 从而叠加 TEST_RULES 产生误报(title 里的 "test" 恰好出现)
        "src/latest.cc": "cpp",
        "src/contest.cc": "cpp",
        "src/greatest.cc": "cpp",
        "src/fastest.cc": "cpp",
        "src/attested.cc": "cpp",
        # 真正的测试文件仍须识别(CamelCase / 前后缀 / 根目录同名)
        "src/UserTest.cc": "test",
        "src/util_test.hpp": "test",
        "src/test_helper.cc": "test",
        "test.cc": "test",
        "src/mytest.cc": "cpp",
        # CamelCase 里 "Test" 出现在中间:必须仍然识别(精确化不能变成漏判)
        "src/MyTestSuite.cc": "test",
        "src/FooTestHelper.cc": "test",
    }
    for path, expected in cases.items():
        got = ptu.file_category(path)
        assert got == expected, f"{path}: expected {expected}, got {got}"


def test_test_category_does_not_leak_into_latest_cc():
    """latest.cc 既不能判为 test,也不能因此命中 TEST.001。"""
    assert ptu.file_category("src/latest.cc") == "cpp"
    hits = ptu.scan_text("CHECK(task.done);", ptu.rules_for("cpp"))
    assert not hits, f"cpp 规则集不该命中测试规则: {[h.rule_id for h in hits]}"


def test_test_category_inherits_cpp_rules():
    assert set(ptu.CPP_RULES) <= set(ptu.rules_for("test"))


# ---------------------------------------------------------------------------
# Hook protocol (stdin -> stdout) and scan contract
# ---------------------------------------------------------------------------


def _hook(payload: dict):
    p = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout)


def test_main_flow_reports_violations_with_rule_ids():
    data = _hook({
        "tool_name": "Write",
        "tool_input": {
            "file_path": "/tmp/bad.cc",
            "content": "auto c = app().createDbClient();\nFILTER_ADD(X);",
        },
    })
    msg = data["systemMessage"]
    assert "CPP.004" in msg and "CPP.001" in msg
    assert "bad.cc" in msg


def test_main_flow_ignores_non_file_tools():
    assert _hook({"tool_name": "Bash", "tool_input": {"command": "ls"}}) == {}


def test_main_flow_silent_on_clean_code():
    assert _hook({
        "tool_name": "Write",
        "tool_input": {"file_path": "/tmp/ok.cc", "content": "int main() { return 0; }"},
    }) == {}


def test_scan_json_contract_is_backward_compatible_superset(tmp_path):
    """--scan JSON must keep findings[].violations / total and add rules[] only."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "bad.cc").write_text(
        "void f() { FILTER_ADD(x); }\nauto c = app().createDbClient();\n", encoding="utf-8"
    )

    import os

    old = os.getcwd()
    os.chdir(tmp_path)
    try:
        r = subprocess.run(
            [sys.executable, str(HOOK), "--scan", "--format", "json", "."],
            capture_output=True, text=True, encoding="utf-8", shell=False,
        )
    finally:
        os.chdir(old)

    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    # 既有契约
    assert data["total"] == 2
    finding = data["findings"][0]
    assert set(finding) >= {"file", "violations", "rules"}
    assert isinstance(finding["violations"], list) and all(isinstance(v, str) for v in finding["violations"])
    # 增量契约
    rule_ids = {x["rule_id"] for x in finding["rules"]}
    assert rule_ids == {"CPP.001", "CPP.004"}
    for x in finding["rules"]:
        assert set(x) == {"rule_id", "severity", "guide"}


def test_scan_format_missing_value_is_graceful():
    """回归(C5):`--scan --format`(缺取值)曾抛 IndexError + traceback。"""
    r = subprocess.run(
        [sys.executable, str(HOOK), "--scan", "--format"],
        capture_output=True, text=True, encoding="utf-8", cwd=str(REPO_ROOT),
    )
    assert r.returncode == 2, f"expected exit 2, got {r.returncode}"
    combined = r.stdout + r.stderr
    assert "Traceback" not in combined and "IndexError" not in combined
    assert "usage" in combined.lower()


def test_scan_rejects_unknown_format_value():
    r = subprocess.run(
        [sys.executable, str(HOOK), "--scan", "--format", "xml", "."],
        capture_output=True, text=True, encoding="utf-8", cwd=str(REPO_ROOT),
    )
    assert r.returncode == 2
    assert "xml" in (r.stdout + r.stderr)


def test_scan_json_error_path_emits_json(tmp_path):
    """回归(H4):错误路径也必须遵守 --format json 契约(新增 error 字段,纯增量)。"""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    r = subprocess.run(
        [sys.executable, str(HOOK), "--scan", "--format", "json", ".."],
        capture_output=True, text=True, encoding="utf-8", cwd=str(workspace),
    )
    assert r.returncode == 2, r.stderr
    data = json.loads(r.stdout)  # 必须是合法 JSON
    assert "error" in data and data["error"]
    assert data["findings"] == [] and data["total"] == 0


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))
