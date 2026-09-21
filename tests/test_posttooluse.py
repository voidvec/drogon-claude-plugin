"""Violation-scanner unit tests: every pattern in hooks/posttooluse.py gets
should-match and should-not-match fixtures, including the v0.1.0 regression
cases (callback-variable naming freedom; case-sensitive C++ identifiers so
isDone()/task.done() no longer trigger done() warnings).

Run:  python -m pytest tests/test_posttooluse.py
"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOK = REPO_ROOT / "hooks" / "posttooluse.py"

spec = importlib.util.spec_from_file_location("posttooluse", HOOK)
ptu = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ptu)

CPP_MATCH = [
    ("FILTER_ADD macro", "void init() { FILTER_ADD(MyFilter); }"),
    ("ADD_MIDDLEWARE macro", "ADD_MIDDLEWARE(Log);"),
    ("METHOD_LIST_ADD in ws ctrl", "METHOD_LIST_ADD(begin, \"/ws\", Get);"),
    ("createDbClient", "auto c = app().createDbClient();"),
    ("AsyncTask + co_await no try", "AsyncTask h() { auto r = co_await f(); }"),
    ("co_await in callback middleware", "class M : public HttpMiddleware<M, false> { void invoke(...) { co_await x; } }"),
    ("sync sendRequest 1-arg", "auto r = client->sendRequest(req);"),
    ("sync sendRequest 2-arg", "auto r = client->sendRequest(req, 5);"),
    ("session operator[]", "auto &v = req->session()->operator[](\"k\");"),
    ("sessionPtr operator[]", "sessionPtr->operator[] (\"k\");"),
    ("advice inside handler", "void h() { app().registerSyncAdvice(cb); }"),
]

CPP_NO_MATCH = [
    # Regression v0.1.0 §4.1: any callback variable name is legal now.
    ("cb naming is free", "std::function<void(const HttpResponsePtr &)> &&cb"),
    ("cbPtr naming", "auto cbPtr = std::make_shared<std::function<void(const HttpResponsePtr &)>>(std::move(cb));"),
    # Regression v0.1.0 §4.2: case-sensitive identifiers.
    ("isDone is not done()", "int ok = task.isDone();"),
    ("task.done is not done()", "bool x = task.done;"),
    ("async sendRequest with callback", "client->sendRequest(req, [this](ReqResult r, HttpResponsePtr resp) {});"),
    ("sendRequestCoro is fine", "auto resp = co_await client->sendRequestCoro(req);"),
    ("Task<HttpResponsePtr> coroutine", "Task<HttpResponsePtr> h() { co_return resp; }"),
    ("coroutine middleware base", "class M : public HttpCoroMiddleware<M, false> { Task<HttpResponsePtr> invoke(...) { auto r = co_await next; } };"),
    ("getOptional session", "auto uid = req->session()->getOptional<int>(\"userId\");"),
    ("normal middleware", "class M : public HttpMiddleware<M, false> { void invoke(const HttpRequestPtr &, NextCallback &&nCb, Callback &&mCb) { nCb(std::move(mCb)); } }"),
]

CSP_MATCH = [
    ("jinja output", "<div>{{ name }}</div>"),
    ("raw block", "<%raw%>x</%raw%>"),
    ("viewpath", "<%viewpath a %>"),
    ("at-at wrap", "<p>@@key@@</p>"),
    ("extends", "<%extends base %>"),
    ("jinja if", "{% if ok %}y{% end %}"),
]

CSP_NO_MATCH = [
    ("drogon inline output", "<div>[[ name ]]</div>"),
    ("single-value interpolation", "{% key %}"),
    ("c++ block", "<%c++ HttpResponsePtr resp; %>"),
    ("layout", "<%layout base %>"),
    ("view include", "<%view header %>"),
]

CONFIG_MATCH = [
    ("password key", '{"db_clients": [{"password": "x"}]}'),
    ("username key", '{"username": "root"}'),
    ("ssl as string", '{"ssl": "true"}'),
]

CONFIG_NO_MATCH = [
    ("passwd is correct", '{"passwd": "x"}'),
    ("user is correct", '{"user": "root"}'),
    ("ssl boolean", '{"ssl": true}'),
]

TEST_MATCH = [
    ("done()", "TEST(P) { std::thread t([&]{ done(); }); }"),
    ("gtest ASSERT_EQ", "ASSERT_EQ(a, b);"),
    ("createDbClient in test", "auto c = app().createDbClient();"),
]

TEST_NO_MATCH = [
    ("isDone regression", "CHECK(task.isDone());"),
    ("CHECK macro is drogon", "CHECK(x == 1);"),
    ("MANDATE", "MANDATE(ok);"),
]


def _hits(violations, text):
    return [m for m in ptu.scan_text(text, violations)]


def test_cpp_violations_match():
    for label, code in CPP_MATCH:
        hits = _hits(ptu.CPP_VIOLATIONS, code)
        assert hits, f"should match: {label}"


def test_cpp_violations_do_not_overmatch():
    for label, code in CPP_NO_MATCH:
        hits = _hits(ptu.CPP_VIOLATIONS, code)
        assert not hits, f"false positive: {label} -> {hits}"


def test_csp_violations():
    for label, code in CSP_MATCH:
        assert _hits(ptu.CSP_VIOLATIONS, code), f"should match: {label}"
    for label, code in CSP_NO_MATCH:
        assert not _hits(ptu.CSP_VIOLATIONS, code), f"false positive: {label}"


def test_config_violations():
    for label, code in CONFIG_MATCH:
        assert _hits(ptu.CONFIG_VIOLATIONS, code), f"should match: {label}"
    for label, code in CONFIG_NO_MATCH:
        assert not _hits(ptu.CONFIG_VIOLATIONS, code), f"false positive: {label}"


def test_test_violations():
    for label, code in TEST_MATCH:
        assert _hits(ptu.TEST_VIOLATIONS, code), f"should match: {label}"
    for label, code in TEST_NO_MATCH:
        assert not _hits(ptu.TEST_VIOLATIONS, code), f"false positive: {label}"


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
    }
    for path, expected in cases.items():
        got = ptu.file_category(path)
        assert got == expected, f"{path}: expected {expected}, got {got}"


def test_main_flow_via_stdin():
    payload = json.dumps(
        {
            "tool_name": "Write",
            "tool_input": {
                "file_path": "/tmp/bad.cc",
                "content": "auto c = app().createDbClient();\nFILTER_ADD(X);",
            },
        }
    )
    p = subprocess.run(
        [sys.executable, str(HOOK)],
        input=payload,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert p.returncode == 0
    data = json.loads(p.stdout)
    msg = data["systemMessage"]
    assert "createDbClient" in msg and "FILTER_ADD" in msg
    assert "bad.cc" in msg


def test_main_flow_ignores_non_file_tools():
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": "ls"}})
    p = subprocess.run(
        [sys.executable, str(HOOK)],
        input=payload,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert p.returncode == 0
    assert json.loads(p.stdout) == {}


if __name__ == "__main__":
    sys.exit(0)
