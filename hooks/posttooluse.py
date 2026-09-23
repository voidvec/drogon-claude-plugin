#!/usr/bin/env python3
"""PostToolUse hook for drogon plugin.
Detects common drogon API violations in C++/CSP/config files after edits.
Outputs warnings via systemMessage; never blocks (PostToolUse is post-hoc).

Also usable as a standalone scanner for hosts without hooks (Gemini/Qoder/
Trae/...) and for CI:

    python posttooluse.py --scan [--format human|json] [--strict] PATH...

Each PATH is a file or directory (walked recursively); only files whose
category matches a violation list are reported. All paths must stay under
the current working directory. --strict exits 1 when violations are found.

Rule model (v0.4.0): every rule carries a stable ``rule_id`` plus ``severity``
and a ``guide`` (the skill that documents the fix). ``--scan`` JSON output is a
**backward-compatible superset**: the original ``findings[].violations`` (list of
messages) and ``total`` are unchanged, and each finding additionally carries a
``rules`` array with the structured metadata.
"""
import json
import os
import re
import sys
from typing import List, NamedTuple, Optional

# ---------------------------------------------------------------------------
# Rule database.
#
# Every rule is a Rule(rule_id, severity, pattern, message, guide, flags):
#   rule_id   stable identifier ("CPP.001") — referenced by tests, the
#             consistency gate and the human/JSON output
#   severity  "error" | "warning"
#   guide     the skill that documents the fix (loaded on demand by the model)
#   flags     defaults to 0 (case-sensitive). Only genuinely case-insensitive
#             patterns (CSP tags) opt into re.IGNORECASE.
#
# C++ identifiers (done(), ASSERT_*, createDbClient, ...) MUST stay
# case-sensitive, otherwise isDone() / task.done are false positives
# (the v0.1.0 regression this suite guards).
# ---------------------------------------------------------------------------


class Rule(NamedTuple):
    rule_id: str
    severity: str
    pattern: str
    message: str
    guide: str
    flags: int = 0


# C++ source files (.h, .cc, .cpp, .cxx, .hpp)
CPP_RULES: List[Rule] = [
    # --- Nonexistent macros ------------------------------------------------
    Rule("CPP.001", "error", r"\bFILTER_ADD\b",
         "FILTER_ADD macro does not exist. Use app().registerFilter(std::make_shared<YourFilter>()) instead.",
         "drogon-gen-filter"),
    Rule("CPP.002", "error", r"\bADD_MIDDLEWARE\b",
         "ADD_MIDDLEWARE macro does not exist. Use app().registerMiddleware(std::make_shared<YourMiddleware>()) instead.",
         "drogon-gen-middleware"),
    Rule("CPP.003", "error", r"\bMETHOD_LIST_ADD\b",
         "METHOD_LIST_ADD does not exist. WebSocket controllers use WS_PATH_ADD(path, ...).",
         "drogon-gen-websocket"),
    # --- Deprecated APIs ---------------------------------------------------
    Rule("CPP.004", "error", r"\bcreateDbClient\b",
         "createDbClient() is deprecated. Use addDbClient() instead (HttpAppFramework.h).",
         "drogon-gen-db-config"),
    # --- Coroutines --------------------------------------------------------
    # AsyncTask that co_awaits without try/catch risks std::terminate on an
    # uncaught exception. Single-line signature matching is unreliable for
    # coroutines, so this stays advisory. Task<HttpResponsePtr> is
    # intentionally NOT flagged (the framework handles response+exceptions).
    Rule("CPP.005", "warning", r"\bAsyncTask\b(?:(?!\btry\b).){0,200}?\bco_await\b",
         "AsyncTask with co_await: wrap the body in try/catch — an uncaught exception calls "
         "std::terminate. Prefer Task<HttpResponsePtr> (the framework handles response+exceptions).",
         "drogon-gen-coroutine-handler", re.DOTALL),
    Rule("CPP.006", "error",
         r"class\s+\w+\s*:\s*public\s+HttpMiddleware\s*<\s*\w+\s*,\s*false\s*>[^}]*\bco_await\b",
         "co_await inside a callback-style HttpMiddleware. Coroutine middleware must derive from "
         "HttpCoroMiddleware<T, false>, not HttpMiddleware<T, false> (HttpMiddleware.h:111).",
         "drogon-gen-coroutine-handler"),
    # --- HttpClient sync deadlock -----------------------------------------
    # Matches the sync overload client->sendRequest(req) / sendRequest(req, timeout)
    # (no callback parameter) — it has a deadlock assert when called from the loop thread.
    Rule("CPP.007", "error", r"->\s*sendRequest\s*\(\s*[^,)]+(?:,\s*[\d.]+\s*)?\)",
         "HttpClient synchronous sendRequest(req [, timeout]) has a deadlock assert and must NOT be "
         "called in the event-loop thread / handler. Use the async overload sendRequest(req, callback) "
         "or sendRequestCoro() (HttpClient.h:133).",
         "drogon-gen-http-client"),
    # --- Session naked subscript ------------------------------------------
    Rule("CPP.008", "warning", r"session\w*(?:\s*\(\s*\))?\s*->\s*operator\s*\[\s*\]",
         "session->operator[] returns std::any& and needs any_cast — error-prone. "
         "Use getOptional<T>() or modify<T>() instead (Session.h).",
         "drogon-gen-session-auth"),
    # --- Advice registered inside a handler --------------------------------
    # Scoped to a registration that appears inside a function taking an
    # HttpRequestPtr/HttpResponsePtr — i.e. a handler body. Registering advice
    # in main() (before app().run()) is correct and must NOT be flagged.
    Rule("CPP.009", "error",
         r"(?:HttpRequestPtr|HttpResponsePtr)\b[^{}]{0,160}\{[^{}]{0,240}?"
         r"\bregister(SyncAdvice|PreRoutingAdvice|PostRoutingAdvice|PreHandlingAdvice|"
         r"PostHandlingAdvice|PreSendingAdvice|BeginningAdvice|NewConnectionAdvice|"
         r"HttpResponseCreationAdvice|SessionStartAdvice|SessionDestroyAdvice)\s*\(",
         "Advice must be registered before app().run(), never dynamically inside a handler "
         "(HttpAppFramework.h:273-441, 920-928).",
         "drogon-gen-advice"),
]

# CSP template files (.csp) — tags are case-insensitive in practice, so these
# rules opt into re.IGNORECASE (matching the comment intent that v0.3.x only
# documented but never implemented).
CSP_RULES: List[Rule] = [
    Rule("CSP.001", "error", r"\{\{.*\}\}",
         "{{ }} is Jinja2/Mustache syntax, not supported by drogon CSP. Use [[ key ]] for inline output.",
         "drogon-gen-csp-view", re.IGNORECASE),
    Rule("CSP.002", "error", r"<%raw%>|<\/%raw%>",
         "<%raw%>...</%raw%> does not exist in drogon CSP.",
         "drogon-gen-csp-view", re.IGNORECASE),
    Rule("CSP.003", "error", r"<%viewpath\s",
         "<%viewpath> does not exist. Use <%view name %> to include a sub-view.",
         "drogon-gen-csp-view", re.IGNORECASE),
    Rule("CSP.004", "warning", r"@@\w+@@",
         "@@key@@ wrapping syntax does not exist. @@ is a standalone reference to HttpViewData, "
         "used only inside <%c++ %> blocks.",
         "drogon-gen-csp-view", re.IGNORECASE),
    Rule("CSP.005", "error", r"<%extends\s",
         "<%extends> does not exist. Use <%layout name %> at the top of the .csp file.",
         "drogon-gen-csp-view", re.IGNORECASE),
    Rule("CSP.006", "error", r"\{%\s*if\b|\{%\s*for\b|\{%\s*end\b",
         "{% if %}/{% for %}/{% end %} block tags are not supported by drogon CSP. "
         "Use <%c++ %> blocks for control flow. (Single-value {% key %} is valid for interpolation.)",
         "drogon-gen-csp-view", re.IGNORECASE),
]

# Config files (config.json, config.yaml, config.yml) — JSON/YAML keys are case-sensitive
# 回归(R6):此前模式只接受带双引号的 JSON 键,YAML 形态(`password: secret`)整体
# 漏报。分支二用 `(?<![\w."])` 挡住 db_password 这类前后缀粘连,避免新误报。
CONFIG_RULES: List[Rule] = [
    Rule("CFG.001", "error", r'"password"\s*:|(?<![\w."])password\s*:',
         '"password" key found — drogon uses "passwd" for the database password in config. '
         'Change to "passwd". (See ConfigLoader.cc)',
         "drogon-gen-db-config"),
    Rule("CFG.002", "error", r'"username"\s*:|(?<![\w."])username\s*:',
         '"username" key found — drogon uses "user" for the database user in config. '
         'Change to "user". (See ConfigLoader.cc)',
         "drogon-gen-db-config"),
    Rule("CFG.003", "error",
         r'"ssl"\s*:\s*"[^"]*"|(?<![\w."])ssl\s*:\s*["\'][^"\']*["\']',
         '"ssl" must be a boolean (true/false), not a string.',
         "drogon-setup-config"),
]

# Test files (*test*.cc, *test*.cpp, files in test/ or tests/)
# C++ identifiers — case-sensitive to avoid isDone() / task.done false positives.
TEST_RULES: List[Rule] = [
    Rule("TEST.001", "error", r"\bdone\s*\(\s*\)",
         "done() callback does not exist in DROGON_TEST. Use CHECK/REQUIRE/MANDATE assertions "
         "inside async callbacks, or queueInLoop() for event-loop scheduling.",
         "drogon-gen-test"),
    Rule("TEST.002", "error", r"\bASSERT_(EQ|NE|TRUE|FALSE|STREQ|STRNE|THROW|NO_THROW)\b",
         "ASSERT_* macros (gtest style) are not drogon test macros. "
         "Use CHECK(), REQUIRE(), MANDATE(), CHECK_THROWS(), etc. (drogon_test.h)",
         "drogon-gen-test"),
    Rule("TEST.003", "error", r"\bcreateDbClient\b",
         "createDbClient() is deprecated. Use addDbClient() before test::run() instead.",
         "drogon-gen-test"),
]

ALL_RULES: List[Rule] = CPP_RULES + CSP_RULES + CONFIG_RULES + TEST_RULES


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

EXT_CSP = {'.csp'}
EXT_CPP = {'.h', '.hh', '.hpp', '.hxx', '.cc', '.cpp', '.cxx', '.c', '.inc'}
EXT_CONFIG = {'.json', '.yaml', '.yml'}

def file_category(file_path: str) -> Optional[str]:
    """Return 'cpp', 'csp', 'config', 'test', or None based on file path."""
    base = os.path.basename(file_path)
    _, ext = os.path.splitext(file_path)
    ext_lower = ext.lower()

    # CSP first — distinct extension
    if ext_lower in EXT_CSP:
        return 'csp'

    # Config files
    if ext_lower in EXT_CONFIG or base in ('config.json', 'config.yaml', 'config.yml'):
        return 'config'

    # Test files — by exact path segment or exact filename pattern
    if ext_lower in EXT_CPP:
        return 'test' if _is_test_path(file_path, base) else 'cpp'

    return None


# 测试文件判定必须**精确**,禁止裸子串:
# `'test' in 'latest.cc'` 为真(la-te-st),会把普通源文件判成测试文件,
# 于是 `rules_for('test')` 叠加 TEST_RULES,让 `task.done()` 之类在正常代码里误报。
_TEST_DIR_SEGMENTS = frozenset({"test", "tests"})


def _is_test_path(file_path: str, base: str) -> bool:
    """路径段精确匹配(test/、tests/) 或 文件名前后缀精确匹配(test_*.cc、*_test.cc、*Test.cc)。"""
    segments = [s for s in file_path.replace("\\", "/").split("/") if s]
    # 目录段精确匹配(最后一段是文件名自身,已由下方文件名规则处理)
    if any(seg.lower() in _TEST_DIR_SEGMENTS for seg in segments[:-1]):
        return True
    stem, _ = os.path.splitext(base)
    stem_lower = stem.lower()
    return (
        stem_lower == "test"
        or stem_lower.startswith("test_")
        or stem_lower.endswith("_test")
        # CamelCase:大小写敏感的 "Test" 子串(刻意不用 lower,否则 latest/contest 又会中招)
        # 覆盖 UserTest.cc / MyTestSuite.cc / FooTestHelper.cc
        or "Test" in stem
    )


def scan_text(text: str, rules: List[Rule]) -> List[Rule]:
    """Return the rules that match ``text`` (deduplicated by rule_id, in order)."""
    hits: List[Rule] = []
    seen = set()
    for rule in rules:
        try:
            matched = re.search(rule.pattern, text, rule.flags) is not None
        except re.error:
            continue
        if matched and rule.rule_id not in seen:
            seen.add(rule.rule_id)
            hits.append(rule)
    return hits


def rules_for(category: str) -> List[Rule]:
    """Rule set for a file category; test files inherit the C++ rules too."""
    return {
        "cpp": CPP_RULES,
        "csp": CSP_RULES,
        "config": CONFIG_RULES,
        "test": TEST_RULES + CPP_RULES,
    }.get(category, [])


# Back-compat alias (v0.3.x callers/tests used ``violations_map_for``).
violations_map_for = rules_for


def extract_new_text(tool_input: dict) -> Optional[str]:
    """Extract the new/changed text from tool_input depending on tool type.

    回归(R5):畸形 payload(tool_input 非 dict 成员 / edits 是字符串数组)
    曾让本函数抛 AttributeError → traceback 逃逸,违反钩子的 never-blocks 契约。
    """
    # Write tool: 'content' field has the full new file content
    content = tool_input.get('content')
    if isinstance(content, str) and content:
        return content

    # Edit tool: 'new_string' field
    new_string = tool_input.get('new_string')
    if isinstance(new_string, str) and new_string:
        return new_string

    # MultiEdit tool: concatenate edits (non-dict entries are skipped, not fatal)
    edits = tool_input.get('edits')
    if isinstance(edits, list):
        parts = [e.get('new_string', '') for e in edits
                 if isinstance(e, dict) and isinstance(e.get('new_string'), str)]
        joined = ' '.join(p for p in parts if p)
        if joined:
            return joined

    return None


# Codex 的 canonical 工具名是 apply_patch(codex-rs hook_names.rs;Write/Edit
# 只是 matcher 别名),payload 为 {"command": <patch 文本>} 且无 file_path。
# 回归(R3):按名白名单 + file_path 取值让扫描器在 Codex 上永远空转。
_PATCH_FILE_RE = re.compile(r"^\*\*\*\s+(?:Update|Add|Delete)\s+File:\s*(.+?)\s*$", re.M)


def apply_patch_sections(tool_input: dict) -> "List[tuple]":
    """Parse a Codex apply_patch payload into ``[(file_path, added_text), ...]``.

    Only '+' added lines are scanned — context/removed lines are pre-existing
    code the model did not write. Returns [] for anything that isn't a patch.
    """
    command = tool_input.get('command') if isinstance(tool_input, dict) else None
    if not isinstance(command, str) or "*** Begin Patch" not in command:
        return []
    sections: "List[tuple]" = []
    current: "Optional[list]" = None
    for line in command.splitlines():
        m = _PATCH_FILE_RE.match(line)
        if m:
            current = [m.group(1), []]
            sections.append(current)
            continue
        if line.startswith("***"):
            current = None
            continue
        if current is not None and line.startswith("+"):
            current[1].append(line[1:])
    return [(path, "\n".join(lines)) for path, lines in sections if lines]


# 黑名单而非白名单(R3):未知工具名(各宿主编辑工具命名不一:search_replace 等)
# 只要携带 file_path/content 或 apply_patch 补丁就应被扫描;明确非文件类工具秒退。
NON_FILE_TOOLS = frozenset({
    # Claude Code
    "Bash", "Read", "Grep", "Glob", "LS", "WebFetch", "WebSearch",
    "Agent", "Task", "TodoWrite", "NotebookRead", "KillShell", "Skill",
    "SlashCommand", "AskUserQuestion",
    # Codex / 小写别名(同为非文件编辑类)
    "read_file", "list_dir", "web_search", "search_files", "update_plan",
    "view_image", "run_command",
})


# ---------------------------------------------------------------------------
# Standalone scan mode (no-hook hosts + CI)
# ---------------------------------------------------------------------------


def _iter_scannable(root: str):
    """Yield files under root whose category has a violation list."""
    if os.path.isfile(root):
        if file_category(str(root)) is not None:
            yield root
        return
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in ("__pycache__", ".git", "node_modules", "build")]
        for name in filenames:
            p = os.path.join(dirpath, name)
            if file_category(p) is not None:
                yield p


def _emit_scan_error(fmt: str, message: str) -> None:
    """错误输出也遵守 ``--format json`` 契约(新增 ``error`` 字段,纯增量)。

    回归来源:此前错误路径只写 stderr,调用方用 ``--format json`` 解析 stdout
    会拿到非 JSON,破坏 CI 集成。
    """
    if fmt == "json":
        print(json.dumps({"error": message, "findings": [], "total": 0},
                         ensure_ascii=False, indent=2))
    else:
        print(message, file=sys.stderr)


def scan_paths(paths, fmt: str = "human", strict: bool = False) -> int:
    """Scan files/directories; print report; return process exit code."""
    cwd = os.path.realpath(os.getcwd())
    resolved = []
    for p in paths:
        rp = os.path.realpath(p)
        # 边界护栏:被扫描路径必须在当前工作目录之内,防任意路径读取
        if not (rp == cwd or rp.startswith(cwd + os.sep)):
            _emit_scan_error(fmt, f"refused: {p} is outside the working directory")
            return 2
        resolved.append(rp)

    findings = []  # list of {file, violations: [msg], rules: [{rule_id, severity, guide}]}
    for rp in resolved:
        for f in _iter_scannable(rp):
            category = file_category(f)
            try:
                text = open(f, encoding="utf-8", errors="ignore").read()
            except OSError:
                continue
            hits = scan_text(text, rules_for(category))
            if hits:
                findings.append({
                    "file": os.path.relpath(f, cwd),
                    # 既有契约:violations 为人类可读消息列表(字段名与语义不变)
                    "violations": [r.message for r in hits],
                    # 新增(纯增量):结构化规则元数据,便于按 rule_id 精确引用
                    "rules": [
                        {"rule_id": r.rule_id, "severity": r.severity, "guide": r.guide}
                        for r in hits
                    ],
                })

    if fmt == "json":
        print(json.dumps({"findings": findings, "total": sum(len(x["violations"]) for x in findings)},
                         ensure_ascii=False, indent=2))
    else:
        if not findings:
            print("✅ no drogon API violations found")
        for item in findings:
            print(f"🔍 {item['file']}")
            for rule, msg in zip(item["rules"], item["violations"]):
                print(f"   - [{rule['rule_id']}] ({rule['severity']}) {msg}")
        total = sum(len(x["violations"]) for x in findings)
        if total:
            print(f"\n共 {total} 处违规(文件 {len(findings)} 个);修复后重跑,或 CI 用 --strict 拦截")
    return 1 if (strict and findings) else 0


def _utf8_stdio():
    # 回归(P1):钩子负载是 UTF-8 JSON,而 Windows 下重定向的 stdin 默认走
    # locale 编码(cp1252/cp936);strict 解码遇非法字节直接 UnicodeDecodeError
    # → traceback + rc=1。stdin 以 replace 读取:非法字节变 U+FFFD,扫描照常。
    # stdout/stderr 同因:违规消息含中文/破折号,strict 编码会抛 UnicodeEncodeError。
    for s in (sys.stdin, sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def _hook_report(input_data: dict) -> dict:
    """Hook protocol body: payload -> response dict ({} = silent no-op)."""
    tool_name = input_data.get('tool_name', '')
    if tool_name in NON_FILE_TOOLS:
        return {}

    tool_input = input_data.get('tool_input')
    if not isinstance(tool_input, dict):
        # 回归(R5):tool_input 为字符串/None 等畸形值时优雅降级,不得 AttributeError
        return {}

    # Codex apply_patch:补丁内可含多个文件,逐文件解析新增行
    sections = apply_patch_sections(tool_input)
    if not sections:
        file_path = tool_input.get('file_path', '')
        if not isinstance(file_path, str) or not file_path:
            return {}
        new_text = extract_new_text(tool_input)
        if not new_text:
            return {}
        sections = [(file_path, new_text)]

    blocks = []
    for file_path, new_text in sections:
        category = file_category(file_path)
        if category is None:
            continue
        hits = scan_text(new_text, rules_for(category))
        if not hits:
            continue
        header = f"🔍 **Drogon API violations detected in `{os.path.basename(file_path)}`**"
        items = '\n'.join(f'- [{r.rule_id}] {r.message}' for r in hits)
        blocks.append(f"{header}\n\n{items}")

    if not blocks:
        return {}
    return {"systemMessage": "\n\n".join(blocks)}


def main():
    _utf8_stdio()
    # --scan 模式:独立扫描器(无钩子宿主 / CI),不走 stdin hook 协议
    if "--scan" in sys.argv[1:]:
        args = [a for a in sys.argv[1:] if a != "--scan"]
        strict = "--strict" in args
        args = [a for a in args if a != "--strict"]
        fmt = "human"
        if "--format" in args:
            i = args.index("--format")
            if i + 1 >= len(args):
                # 缺取值:给用法提示而不是 IndexError(回归来源:--format 作末位参数会崩溃)
                print("usage: posttooluse.py --scan [--format human|json] [--strict] PATH...",
                      file=sys.stderr)
                return 2
            fmt = args[i + 1]
            if fmt not in ("human", "json"):
                print(f"unknown --format value: {fmt} (expected human|json)", file=sys.stderr)
                return 2
            del args[i:i + 2]
        if not args:
            print("usage: posttooluse.py --scan [--format json] [--strict] PATH...", file=sys.stderr)
            return 2
        return scan_paths(args, fmt=fmt, strict=strict)

    try:
        input_data = json.load(sys.stdin)
    except (ValueError, IOError):
        print(json.dumps({}))
        return 0
    if not isinstance(input_data, dict):
        print(json.dumps({}))
        return 0

    # never-blocks 契约:钩子分支的任何未预期异常都必须降级为静默 no-op,
    # 而不是 traceback + 非零退出(回归 R5 的纵深兜底)。
    try:
        output = _hook_report(input_data)
    except Exception:
        output = {}
    print(json.dumps(output))
    return 0


if __name__ == '__main__':
    sys.exit(main())
