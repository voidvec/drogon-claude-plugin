"""End-to-end smoke tests for the cross-platform hook scripts.

Runs the real entry points (hooks/session-start, hooks/post-tool-use,
hooks/run-hook.cmd) through bash and asserts the host-facing protocol:
one JSON object on stdout for SessionStart, systemMessage warnings for
PostToolUse, and graceful no-ops on failure paths.

These tests mirror what Claude Code / ZCode execute on each OS; on Windows
bash comes from Git for Windows, on Linux/macOS it is the system bash.
"""

import json
import os
import platform
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOKS = REPO_ROOT / "hooks"

SESSION_START_EVENT = '{"hook_event_name":"SessionStart","source":"startup"}\n'


def _posix(p):
    """Windows paths must use forward slashes when handed to bash."""
    return str(p).replace("\\", "/")


def _bash():
    """Resolve a bash that can see Windows paths.

    On Windows, `bash` on PATH may resolve to WSL bash, which cannot open
    D:/... paths. Prefer Git for Windows bash at standard locations (same
    lookup order as hooks/run-hook.cmd), then PATH.
    """
    if platform.system() == "Windows":
        for cand in (
            r"C:\Program Files\Git\bin\bash.exe",
            r"C:\Program Files (x86)\Git\bin\bash.exe",
        ):
            if os.path.isfile(cand):
                return cand
    return "bash"


BASH = _bash()


def _run(command, stdin_data=""):
    return subprocess.run(
        command,
        input=stdin_data,
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(REPO_ROOT),
    )


def _skip_if_no_bash():
    try:
        subprocess.run(
            [BASH, "--version"], capture_output=True, check=True
        )
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("bash not available")


def test_session_start_outputs_valid_json_with_rules():
    _skip_if_no_bash()
    p = _run([BASH, _posix(HOOKS / "session-start")], SESSION_START_EVENT)
    assert p.returncode == 0, p.stderr
    assert p.stdout.lstrip().startswith("{")
    data = json.loads(p.stdout)
    ctx = data["hookSpecificOutput"]["additionalContext"]
    assert data["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    # The injected context must be the CLAUDE.md rules, fully intact.
    for marker in ("异步回调模型", "Trantor", "Skill 路由表", "drogon-gen-orm-crud"):
        assert marker in ctx, f"missing marker: {marker}"
    src = (REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8").strip()
    assert ctx.strip() == src, "injected context differs from CLAUDE.md"


def test_session_start_survives_missing_claude_md(tmp_path):
    _skip_if_no_bash()
    # Point the plugin root at an empty dir: hook must exit 0 with no output.
    env = dict(os.environ, CLAUDE_PLUGIN_ROOT=_posix(tmp_path))
    p = subprocess.run(
        [BASH, _posix(HOOKS / "session-start")],
        input=SESSION_START_EVENT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        cwd=str(REPO_ROOT),
    )
    assert p.returncode == 0
    assert p.stdout.strip() == ""


def test_post_tool_use_reports_cpp_violation():
    _skip_if_no_bash()
    payload = json.dumps(
        {
            "tool_name": "Write",
            "tool_input": {
                "file_path": "/tmp/x.cc",
                "content": "void f() { FILTER_ADD(x); }",
            },
        }
    )
    p = _run([BASH, _posix(HOOKS / "post-tool-use")], payload)
    assert p.returncode == 0, p.stderr
    data = json.loads(p.stdout)
    assert "FILTER_ADD" in data["systemMessage"]


def test_post_tool_use_silent_on_clean_code():
    _skip_if_no_bash()
    payload = json.dumps(
        {
            "tool_name": "Write",
            "tool_input": {
                "file_path": "/tmp/x.cc",
                "content": "int main() { return 0; }",
            },
        }
    )
    p = _run([BASH, _posix(HOOKS / "post-tool-use")], payload)
    assert p.returncode == 0, p.stderr
    assert json.loads(p.stdout) == {}


def test_run_hook_cmd_dispatches_session_start():
    _skip_if_no_bash()
    p = _run([BASH, _posix(HOOKS / "run-hook.cmd"), "session-start"], SESSION_START_EVENT)
    assert p.returncode == 0, p.stderr
    data = json.loads(p.stdout)
    assert "additionalContext" in data["hookSpecificOutput"]


def test_run_hook_cmd_dispatches_post_tool_use():
    _skip_if_no_bash()
    payload = json.dumps(
        {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "models/User.cc",
                "new_string": "auto c = cli->createDbClient(cfg);",
            },
        }
    )
    p = _run([BASH, _posix(HOOKS / "run-hook.cmd"), "post-tool-use"], payload)
    assert p.returncode == 0, p.stderr
    data = json.loads(p.stdout)
    assert "createDbClient" in data["systemMessage"]


def test_hooks_json_is_valid_and_uses_run_hook_cmd():
    data = json.loads((HOOKS / "hooks.json").read_text(encoding="utf-8"))
    for event in ("SessionStart", "PostToolUse"):
        entry = data["hooks"][event][0]["hooks"][0]
        assert entry["type"] == "command"
        assert entry["shell"] == "bash"
        assert "run-hook.cmd" in entry["command"]
        assert entry.get("timeout", 0) >= 5, f"{event} timeout too tight"


def test_session_start_matcher_covers_resume():
    """回归(H1):来源集合为 startup/resume/clear/compact,漏 resume 会导致会话恢复不注入规则。"""
    data = json.loads((HOOKS / "hooks.json").read_text(encoding="utf-8"))
    entry = data["hooks"]["SessionStart"][0]
    assert "resume" in entry["matcher"], f"SessionStart matcher 未覆盖 resume: {entry['matcher']}"


def test_session_start_strips_control_chars(tmp_path):
    """回归(H5):规则文件含 C0 控制字符时,产出仍必须是合法 JSON。"""
    _skip_if_no_bash()
    (tmp_path / "CLAUDE.md").write_text(
        "# 规则\n\n正常内容\x0c含换页符\x0b含垂直制表\n", encoding="utf-8"
    )
    env = dict(os.environ, CLAUDE_PLUGIN_ROOT=_posix(tmp_path))
    p = subprocess.run(
        [BASH, _posix(HOOKS / "session-start")],
        input=SESSION_START_EVENT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        cwd=str(REPO_ROOT),
    )
    assert p.returncode == 0, p.stderr
    data = json.loads(p.stdout)  # 含控制字符时 raw 输出会破坏 JSON,这里必须能解析
    ctx = data["hookSpecificOutput"]["additionalContext"]
    assert "正常内容" in ctx
    assert not [c for c in ctx if ord(c) < 0x20 and c not in "\t\n\r"], "控制字符未被剔除"


def test_hook_scripts_use_lf_on_disk():
    """钩子脚本含 CRLF 时 bash 会把 \\r 当成命令的一部分(静默失效),磁盘上必须是 LF。"""
    for rel in ("hooks/session-start", "hooks/post-tool-use", "hooks/run-hook.cmd"):
        data = (REPO_ROOT / rel).read_bytes()
        assert b"\r\n" not in data, f"{rel}: 含 CRLF,bash 解析会被 \\r 破坏"


def test_extensionless_hook_scripts_are_lf_pinned_in_gitattributes():
    """无扩展名脚本必须显式声明 LF —— 按扩展名的规则覆盖不到它们(Windows 克隆会变 CRLF)。"""
    ga = (REPO_ROOT / ".gitattributes").read_text(encoding="utf-8")
    for rel in ("hooks/session-start", "hooks/post-tool-use"):
        assert re.search(rf"^{re.escape(rel)}\s+.*\beol=lf\b", ga, re.M), (
            f".gitattributes 缺少 {rel} 的 eol=lf 声明"
        )


def test_rule_files_have_no_control_chars():
    """防我们自己往规则文件里引入控制字符(session-start 的前提)。"""
    for rel in ("CLAUDE.md", "AGENTS.md", "GEMINI.md"):
        text = (REPO_ROOT / rel).read_text(encoding="utf-8")
        bad = sorted({hex(ord(c)) for c in text if ord(c) < 0x20 and c not in "\t\n\r"})
        assert not bad, f"{rel}: 含控制字符 {bad}"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))
