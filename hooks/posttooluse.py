#!/usr/bin/env python3
"""PostToolUse hook for drogon plugin.
Detects common drogon API violations in C++/CSP/config files after edits.
Outputs warnings via systemMessage; never blocks (PostToolUse is post-hoc).
"""
import json
import os
import re
import sys
from typing import List, Optional, Tuple, Union

# ---------------------------------------------------------------------------
# Violation database — each entry is (regex, message) or (regex, message, flags).
# Per-pattern flags default to 0 (case-sensitive). Only set re.IGNORECASE when
# the pattern is genuinely case-insensitive (e.g. CSP tags). C++ identifiers
# (done(), ASSERT_*, createDbClient, ...) MUST stay case-sensitive to avoid
# false positives like isDone() / task.done().
# ---------------------------------------------------------------------------

# Type alias: 2-tuple (pattern, message) or 3-tuple (pattern, message, flags)
Violation = Union[Tuple[str, str], Tuple[str, str, int]]

# C++ source files (.h, .cc, .cpp, .cxx, .hpp)
CPP_VIOLATIONS: List[Violation] = [
    # Nonexistent macros
    (r'\bFILTER_ADD\b',
     'FILTER_ADD macro does not exist. Use app().registerFilter(std::make_shared<YourFilter>()) instead.'),
    (r'\bADD_MIDDLEWARE\b',
     'ADD_MIDDLEWARE macro does not exist. Use app().registerMiddleware(std::make_shared<YourMiddleware>()) instead.'),
    (r'\bMETHOD_LIST_ADD\b',
     'METHOD_LIST_ADD does not exist. WebSocket controllers use WS_PATH_ADD(path, ...).'),
    # Deprecated APIs (case-sensitive: createDbClient is the real spelling)
    (r'\bcreateDbClient\b',
     'createDbClient() is deprecated. Use addDbClient() instead (HttpAppFramework.h).'),
    # Coroutine misuse (P group) — AsyncTask that co_awaits without try/catch risks
    # std::terminate on uncaught exception. Best-effort: AsyncTask followed (within ~200 chars,
    # across newlines) by co_await. Single-line signature matching is unreliable for coroutines,
    # so this stays advisory. Task<HttpResponsePtr> is intentionally NOT flagged (framework-safe).
    (r'\bAsyncTask\b(?:(?!\btry\b).){0,200}?\bco_await\b',
     'AsyncTask with co_await: wrap the body in try/catch — uncaught exception calls '
     'std::terminate. Prefer Task<HttpResponsePtr> (framework handles response+exceptions). '
     'See drogon-gen-coroutine-handler skill.', re.DOTALL),
    (r'class\s+\w+\s*:\s*public\s+HttpMiddleware\s*<\s*\w+\s*,\s*false\s*>[^}]*\bco_await\b',
     'co_await inside a callback-style HttpMiddleware. Coroutine middleware must derive from '
     'HttpCoroMiddleware<T, false>, not HttpMiddleware<T, false> (HttpMiddleware.h:111). See drogon-gen-coroutine-handler skill.'),
    # HttpClient sync sendRequest deadlock (Q group)
    # Matches the 2-arg sync overload client->sendRequest(req) / sendRequest(req, timeout)
    # (no callback parameter) — has a deadlock assert when called from the loop thread.
    (r'->\s*sendRequest\s*\(\s*[^,)]+(?:,\s*[\d.]+\s*)?\)',
     'HttpClient synchronous sendRequest(req [, timeout]) has a deadlock assert and must NOT be '
     'called in the event-loop thread / handler. Use the async overload sendRequest(req, callback) '
     'or sendRequestCoro() (HttpClient.h:133). See drogon-gen-http-client skill.'),
    # Session naked subscript (M group) — matches req->session()->operator[](...) and
    # session(Ptr)->operator[](...). Variable names vary, so anchor on session.
    (r'session\b\w*(?:\s*\)|\s*)*->\s*operator\s*\[\s*\]|->\s*session\s*\(\s*\)\s*->\s*operator\s*\[\s*\]',
     'session->operator[] returns std::any& and needs any_cast — error-prone. '
     'Use getOptional<T>() or modify<T>() instead (Session.h). See drogon-gen-session-auth skill.'),
    # Advice registered inside handler (O group) — case-sensitive C++ identifiers
    (r'\bregister(SyncAdvice|PreRoutingAdvice|PostRoutingAdvice|PreHandlingAdvice|'
     r'PostHandlingAdvice|PreSendingAdvice|BeginningAdvice|NewConnectionAdvice|'
     r'HttpResponseCreationAdvice|SessionStartAdvice|SessionDestroyAdvice)\s*\(',
     'Advice must be registered before app().run(), never dynamically inside a handler. '
     'See drogon-gen-advice skill (HttpAppFramework.h:273-441, 920-928).'),
]

# CSP template files (.csp) — genuinely case-insensitive patterns keep IGNORECASE
CSP_VIOLATIONS: List[Violation] = [
    (r'\{\{.*\}\}',
     '{{ }} is Jinja2/Mustache syntax, not supported by drogon CSP. Use [[ key ]] for inline output.'),
    (r'<%raw%>|<\/%raw%>',
     '<%raw%>...</%raw%> does not exist in drogon CSP.'),
    (r'<%viewpath\s',
     '<%viewpath> does not exist. Use <%view name %> to include a sub-view.'),
    (r'@@\w+@@',
     '@@key@@ wrapping syntax does not exist. @@ is a standalone reference to HttpViewData, '
     'used only inside <%c++ %> blocks.'),
    (r'<%extends\s',
     '<%extends> does not exist. Use <%layout name %> at the top of the .csp file.'),
    (r'\{%\s*if\b|\{%\s*for\b|\{%\s*end\b',
     '{% if %}/{% for %}/{% end %} block tags are not supported by drogon CSP. '
     'Use <%c++ %> blocks for control flow. (Single-value {% key %} is valid for interpolation.)'),
]

# Config files (config.json, config.yaml, config.yml) — JSON/YAML keys are case-sensitive
CONFIG_VIOLATIONS: List[Violation] = [
    (r'"password"\s*:',
     '"password" key found — drogon uses "passwd" for database password in config. '
     'Change to "passwd". (See ConfigLoader.cc)'),
    (r'"username"\s*:',
     '"username" key found — drogon uses "user" for database user in config. '
     'Change to "user". (See ConfigLoader.cc)'),
    # ssl must be boolean true/false, not a string
    (r'"ssl"\s*:\s*"[^"]*"',
     '"ssl" must be a boolean (true/false), not a string. See drogon-setup-config skill.'),
]

# Test files (*test*.cc, *test*.cpp, files in test/ or tests/)
# C++ identifiers — case-sensitive to avoid isDone() / task.done() false positives (review §4.2)
TEST_VIOLATIONS: List[Violation] = [
    (r'\bdone\s*\(\s*\)',
     'done() callback does not exist in DROGON_TEST. Use CHECK/REQUIRE/MANDATE assertions '
     'inside async callbacks, or queueInLoop() for event-loop scheduling.'),
    (r'\bASSERT_(EQ|NE|TRUE|FALSE|STREQ|STRNE|THROW|NO_THROW)\b',
     'ASSERT_* macros (gtest style) are not drogon test macros. '
     'Use CHECK(), REQUIRE(), MANDATE(), CHECK_THROWS(), etc. (drogon_test.h)'),
    (r'\bcreateDbClient\b',
     'createDbClient() is deprecated. Use addDbClient() before test::run() instead.'),
]

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

    # Test files — by path or name pattern
    if ext_lower in EXT_CPP:
        path_lower = file_path.lower()
        # Path contains test/ or tests/ directory, or starts with test/tests
        if any(seg in path_lower for seg in ('/test/', '/tests/', '\\test\\', '\\tests\\')):
            return 'test'
        if path_lower.startswith('test/') or path_lower.startswith('tests/'):
            return 'test'
        if 'test' in base.lower() or base.lower().endswith('_test.cc') or base.lower().endswith('_test.cpp'):
            return 'test'
        return 'cpp'

    return None


def scan_text(text: str, violations: List[Violation]) -> List[str]:
    """Scan text against a list of violation entries.

    Each entry is (pattern, message) or (pattern, message, flags). Flags default
    to 0 (case-sensitive); only patterns that opt in carry re.IGNORECASE.
    """
    matches = []
    for entry in violations:
        pattern = entry[0]
        message = entry[1]
        flags = entry[2] if len(entry) > 2 else 0
        try:
            if re.search(pattern, text, flags):
                matches.append(message)
        except re.error:
            pass
    return matches


def extract_new_text(tool_input: dict) -> Optional[str]:
    """Extract the new/changed text from tool_input depending on tool type."""
    # Write tool: 'content' field has the full new file content
    content = tool_input.get('content')
    if content is not None:
        return content

    # Edit tool: 'new_string' field
    new_string = tool_input.get('new_string')
    if new_string is not None:
        return new_string

    # MultiEdit tool: concatenate edits
    edits = tool_input.get('edits')
    if edits:
        return ' '.join(e.get('new_string', '') for e in edits)

    return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, IOError):
        print(json.dumps({}))
        sys.exit(0)

    tool_name = input_data.get('tool_name', '')
    if tool_name not in ('Write', 'Edit', 'MultiEdit'):
        # Only scan file-mutating tools
        print(json.dumps({}))
        sys.exit(0)

    tool_input = input_data.get('tool_input', {})
    file_path = tool_input.get('file_path', '')
    if not file_path:
        print(json.dumps({}))
        sys.exit(0)

    category = file_category(file_path)
    if category is None:
        print(json.dumps({}))
        sys.exit(0)

    new_text = extract_new_text(tool_input)
    if not new_text:
        print(json.dumps({}))
        sys.exit(0)

    # Select violation list by category
    violations_map = {
        'cpp':    CPP_VIOLATIONS,
        'csp':    CSP_VIOLATIONS,
        'config': CONFIG_VIOLATIONS,
        'test':   TEST_VIOLATIONS + CPP_VIOLATIONS,  # test files inherit C++ rules too
    }
    violations = violations_map.get(category, [])

    findings = scan_text(new_text, violations)
    if not findings:
        print(json.dumps({}))
        sys.exit(0)

    # Build warning message
    header = f"🔍 **Drogon API violations detected in `{os.path.basename(file_path)}`**"
    items = '\n'.join(f'- {m}' for m in findings)
    message = f"{header}\n\n{items}"

    output = {"systemMessage": message}
    print(json.dumps(output))
    sys.exit(0)


if __name__ == '__main__':
    main()
