#!/usr/bin/env python3
"""PostToolUse hook for drogon plugin.
Detects common drogon API violations in C++/CSP/config files after edits.
Outputs warnings via systemMessage; never blocks (PostToolUse is post-hoc).
"""
import json
import os
import re
import sys
from typing import List, Optional, Tuple

# ---------------------------------------------------------------------------
# Violation database — (regex, message) keyed by file category
# ---------------------------------------------------------------------------

# C++ source files (.h, .cc, .cpp, .cxx, .hpp)
CPP_VIOLATIONS: List[Tuple[str, str]] = [
    # Nonexistent macros
    (r'\bFILTER_ADD\b',
     'FILTER_ADD macro does not exist. Use app().registerFilter(std::make_shared<YourFilter>()) instead.'),
    (r'\bADD_MIDDLEWARE\b',
     'ADD_MIDDLEWARE macro does not exist. Use app().registerMiddleware(std::make_shared<YourMiddleware>()) instead.'),
    (r'\bMETHOD_LIST_ADD\b',
     'METHOD_LIST_ADD does not exist. WebSocket controllers use WS_PATH_ADD(path, ...).'),
    # Deprecated APIs
    (r'\bcreateDbClient\b',
     'createDbClient() is deprecated. Use addDbClient() instead (HttpAppFramework.h).'),
    # Handler callback safety heuristics
    (r'std::function\s*<\s*void\s*\(\s*const\s+HttpResponsePtr\s*[&*]\s*\)\s*>\s*(?!.*\bcallback\b)',
     'HttpResponse callback parameter detected but "callback" not found nearby — '
     'ensure every code path calls the callback exactly once (A.1 rule).'),
]

# CSP template files (.csp)
CSP_VIOLATIONS: List[Tuple[str, str]] = [
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

# Config files (config.json, config.yaml, config.yml)
CONFIG_VIOLATIONS: List[Tuple[str, str]] = [
    (r'"password"\s*:',
     '"password" key found — drogon uses "passwd" for database password in config. '
     'Change to "passwd". (See ConfigLoader.cc)'),
    (r'"username"\s*:',
     '"username" key found — drogon uses "user" for database user in config. '
     'Change to "user". (See ConfigLoader.cc)'),
]

# Test files (*test*.cc, *test*.cpp, files in test/ or tests/)
TEST_VIOLATIONS: List[Tuple[str, str]] = [
    (r'\bdone\(\)',
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


def scan_text(text: str, violations: List[Tuple[str, str]]) -> List[str]:
    """Scan text against a list of (pattern, message) pairs. Returns matched messages."""
    matches = []
    for pattern, message in violations:
        try:
            if re.search(pattern, text, re.IGNORECASE):
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
