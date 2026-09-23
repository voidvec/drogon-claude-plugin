"""Structural validation of the plugin: manifests, skill inventory, hook
scripts, CLAUDE.md routing table and version consistency across the four
release files (plugin.json / __init__.py / pyproject.toml / npm/package.json).

Run:  python -m pytest tests/test_structure.py
"""

import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

# 技能数量不硬编码:单一事实源是 skills/ 目录本身(见 scripts/gen-host-artifacts.py)。
# 这里只保留下限哨兵——防止误删整个技能目录却无人察觉。
MIN_EXPECTED_SKILLS = 20

EXPECTED_NEW_SKILLS = (
    "drogon-gen-orm-model",
    "drogon-gen-rate-limiter",
    "drogon-gen-monitoring",
    "drogon-gen-websocket",
    "drogon-gen-stream",
)

EXPECTED_HOOK_FILES = (
    "hooks.json",
    "run-hook.cmd",
    "session-start",
    "post-tool-use",
    "posttooluse.py",
)


def _skills():
    d = REPO_ROOT / "skills"
    return sorted(p.name for p in d.iterdir() if p.is_dir())


def _version_from_pyproject():
    text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.M)
    return m.group(1)


def test_skill_inventory():
    skills = _skills()
    assert len(skills) >= MIN_EXPECTED_SKILLS, f"skills: {len(skills)} < {MIN_EXPECTED_SKILLS}: {skills}"
    for name in EXPECTED_NEW_SKILLS:
        assert name in skills, f"missing new skill {name}"


# Agent Skills 规范允许的 SKILL.md frontmatter 字段白名单。
# 依据:Claude Code 文档明确 —— claude.ai 上传 / Skills API / package_skill.py 打包路径
# 只接受 name / description / license / compatibility / metadata / allowed-tools，
# 出现其它键是**硬失败**(Unexpected key(s) in SKILL.md frontmatter),不是忽略。
# 本仓库技能同时经 .agents/skills 分发,所以必须严格限定在该白名单内。
ALLOWED_FRONTMATTER_KEYS = frozenset(
    {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
)
# description 在技能列表中的截断上限(Claude Code 文档:与 when_to_use 合计 1536 字符)。
MAX_DESCRIPTION_CHARS = 1536


def _frontmatter_of(name: str) -> str:
    text = (REPO_ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
    assert text.startswith("---"), f"{name}: SKILL.md must start with frontmatter"
    return text.split("---", 2)[1]


def _frontmatter_keys(fm: str) -> set:
    keys = set()
    for line in fm.splitlines():
        m = re.match(r"^([A-Za-z0-9_-]+)\s*:", line)
        if m:
            keys.add(m.group(1))
    return keys


def test_every_skill_has_skill_md_with_frontmatter():
    for name in _skills():
        skill_md = REPO_ROOT / "skills" / name / "SKILL.md"
        assert skill_md.is_file(), f"{name}: missing SKILL.md"
        fm = _frontmatter_of(name)
        m = re.search(r"^name:\s*(\S+)", fm, re.M)
        assert m and m.group(1) == name, f"{name}: frontmatter name mismatch"
        assert re.search(r"^description:\s*\S", fm, re.M), f"{name}: missing description"
        assert re.search(r"^license:\s*\S", fm, re.M), f"{name}: missing license"
        # 规范级约束:只允许白名单键(自定义键会导致打包/上传硬失败)
        extra = _frontmatter_keys(fm) - ALLOWED_FRONTMATTER_KEYS
        assert not extra, f"{name}: disallowed frontmatter keys {sorted(extra)}"


def test_skill_description_is_trigger_first_and_within_cap():
    for name in _skills():
        fm = _frontmatter_of(name)
        desc = re.search(r"^description:\s*(.+)$", fm, re.M).group(1).strip()
        assert len(desc) <= MAX_DESCRIPTION_CHARS, f"{name}: description too long ({len(desc)})"
        # 触发词优先:统一"需要……时，…"句式,便于模型按场景匹配
        assert desc.startswith("需要") and "时" in desc, (
            f"{name}: description should be trigger-first ('需要……时，…'): {desc[:48]}"
        )


# code-guide 的结构契约:每个技能的知识文档必须含"禁止模式清单"章节与至少一个
# 围栏模板块 —— SKILL.md 的「参考文件」行正是这样向模型承诺的(声明必须为真)。
MIN_CODE_GUIDE_LINES = 70
REQUIRED_GUIDE_SECTION = "## 禁止模式清单"


def test_every_skill_has_code_guide():
    for name in _skills():
        guide = REPO_ROOT / "skills" / name / "references" / "code-guide.md"
        assert guide.is_file(), f"{name}: missing references/code-guide.md"
        content = guide.read_text(encoding="utf-8")
        n = len(content.splitlines())
        assert n >= MIN_CODE_GUIDE_LINES, (
            f"{name}: code-guide.md suspiciously thin ({n} < {MIN_CODE_GUIDE_LINES})"
        )
        assert REQUIRED_GUIDE_SECTION in content, (
            f"{name}: code-guide.md missing '{REQUIRED_GUIDE_SECTION}' "
            "(SKILL.md 的「参考文件」行声明了该章节)"
        )
        assert "```" in content, f"{name}: code-guide.md has no fenced template block"


def test_claude_md_routes_every_skill():
    text = (REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    for name in _skills():
        assert name in text, f"CLAUDE.md routing table missing {name}"


# 回归(R7):技能模板是模型逐字照抄的样本,内容错误会被直接放大成用户代码
# 崩溃/行为错误。两条都已对照 drogon v1.9.13 / trantor 头文件核实:
#   - trantor EventLoop.h:getEventLoopOfCurrentThread() 在无循环线程返回 nullptr
#   - drogon HttpAppFramework.h:forward 系列第三参是 timeout(double),端口写进 hostString
GUIDE_FORBIDDEN = (
    (re.compile(r"getEventLoopOfCurrentThread\s*\(\s*\)\s*->"),
     "非事件循环线程返回 nullptr,直接 -> 解引用必崩;应在进入线程前捕获 req->getLoop() 再 queueInLoop"),
    (re.compile(r"forwardCoro\s*\(\s*[^)]*?,\s*\"[^\"]+\"\s*,\s*[\d.]+"),
     "forwardCoro 第三参是 timeout(double) 非端口;目标端口须写进 host 字符串(\"host:port\")"),
    (re.compile(r"forwardCoro\s*\(\s*[^)]*\bport\b\s*\)"),
     "forwardCoro 第三参是 timeout 非端口;签名应说明 hostString 含端口"),
)


def test_skill_guides_free_of_known_bad_api_patterns():
    offenders = []
    for name in _skills():
        for md in (REPO_ROOT / "skills" / name).rglob("*.md"):
            text = md.read_text(encoding="utf-8", errors="ignore")
            for pat, why in GUIDE_FORBIDDEN:
                for m in pat.finditer(text):
                    line = text[: m.start()].count("\n") + 1
                    offenders.append(
                        f"{md.relative_to(REPO_ROOT)}:{line}: “{m.group(0)[:72]}” — {why}"
                    )
    assert not offenders, "技能文档含已知错误 API 用法:\n" + "\n".join(offenders)


def test_hook_scripts_present():
    for name in EXPECTED_HOOK_FILES:
        p = REPO_ROOT / "hooks" / name
        assert p.is_file(), f"missing hooks/{name}"


def test_manifests_valid_json():
    for rel in (
        ".claude-plugin/plugin.json",
        ".claude-plugin/marketplace.json",
        ".zcode-plugin/plugin.json",
        "hooks/hooks.json",
        "npm/package.json",
    ):
        data = json.loads((REPO_ROOT / rel).read_text(encoding="utf-8"))
        assert isinstance(data, dict), f"{rel} not a JSON object"


def test_zcode_manifest_mirrors_claude_manifest():
    claude = json.loads((REPO_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    zcode = json.loads((REPO_ROOT / ".zcode-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert zcode["name"] == claude["name"]
    assert zcode["version"] == claude["version"]
    # Per the ZCode plugin reference: skills points at ./skills, hooks at
    # hooks/hooks.json; both must resolve inside the plugin root.
    assert zcode.get("skills") in ("skills", "./skills")
    assert zcode.get("hooks") == "hooks/hooks.json"
    assert (REPO_ROOT / "hooks" / "hooks.json").is_file()


def test_versions_are_synced():
    plugin = json.loads((REPO_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    npm = json.loads((REPO_ROOT / "npm" / "package.json").read_text(encoding="utf-8"))
    init_py = (REPO_ROOT / "src" / "drogon_plugin" / "__init__.py").read_text(encoding="utf-8")
    versions = {
        "plugin.json": plugin["version"],
        "marketplace": json.loads(
            (REPO_ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8")
        ).get("plugins", [{}])[0].get("version", plugin["version"]),
        "npm/package.json": npm["version"],
        "pyproject.toml": _version_from_pyproject(),
        "__init__.py": re.search(r'__version__\s*=\s*"([^"]+)"', init_py).group(1),
        "PLUGIN_VERSION": re.search(r'PLUGIN_VERSION\s*=\s*"([^"]+)"', init_py).group(1),
    }
    unique = set(versions.values())
    assert len(unique) == 1, f"version drift: {versions}"


def test_marketplace_lists_plugin():
    data = json.loads((REPO_ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    names = [p["name"] for p in data["plugins"]]
    assert "drogon" in names


def test_run_hook_cmd_is_polyglot():
    text = (REPO_ROOT / "hooks" / "run-hook.cmd").read_text(encoding="utf-8")
    assert text.startswith(": << 'CMDBLOCK'"), "batch section must be guarded by a bash no-op heredoc"
    assert "@echo off" in text
    assert "session-start" in text and "post-tool-use" in text


def test_session_start_is_python_free():
    text = (REPO_ROOT / "hooks" / "session-start").read_text(encoding="utf-8")
    assert "additionalContext" in text
    # The whole point: no interpreter dependency for rules injection.
    assert "python" not in text.lower()


def test_post_tool_use_launcher_falls_back_silently():
    text = (REPO_ROOT / "hooks" / "post-tool-use").read_text(encoding="utf-8")
    assert "python3" in text and "DROGON_PLUGIN_PYTHON" in text
    assert "exit 0" in text


# Mirrors the official ZCode plugin-creator preflight rule: unresolved
# placeholders (TODO / FIXME / <your-...> / YOUR_API_KEY) in plugin-facing
# files fail `zcode plugins validate`.
PLACEHOLDER = re.compile(r"\bTODO\b|\bFIXME\b|<your[-_ ][^>]+>|YOUR_API_KEY")


def test_no_unresolved_placeholders_in_plugin_assets():
    targets = [REPO_ROOT / "CLAUDE.md", REPO_ROOT / "AGENTS.md", REPO_ROOT / "GEMINI.md"]
    for root in ("skills", "hooks", ".claude-plugin", ".zcode-plugin", ".codex-plugin", ".agents"):
        base = REPO_ROOT / root
        if base.is_dir():
            targets += [p for p in base.rglob("*") if p.is_file() and "__pycache__" not in p.parts]
    offenders = []
    for f in targets:
        text = f.read_text(encoding="utf-8", errors="ignore")
        m = PLACEHOLDER.search(text)
        if m:
            offenders.append(f"{f.relative_to(REPO_ROOT)}: '{m.group(0)}'")
    assert not offenders, f"unresolved placeholders: {offenders}"


def test_marketplace_entry_has_catalog_fields():
    data = json.loads((REPO_ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    entry = data["plugins"][0]
    for field in ("name", "source", "version", "description", "displayName", "category"):
        assert field in entry, f"marketplace entry missing {field}"
    assert entry["version"] == json.loads(
        (REPO_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
    )["version"]


def test_local_marketplace_sources_start_with_dot_slash():
    """回归(R1):官方文档硬约束 —— "Local plugin sources must start with ./"。

    `"."` 会让 `claude plugin marketplace update/install` 解析失败;两个
    marketplace(Claude 系字符串 source、Codex 系 {source:local,path})都盖进去。
    """
    claude_mp = json.loads(
        (REPO_ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8")
    )
    for e in claude_mp["plugins"]:
        assert isinstance(e["source"], str) and e["source"].startswith("./"), (
            f"claude marketplace: {e['name']} source={e['source']!r} 必须以 ./ 开头"
        )
    codex_mp = json.loads(
        (REPO_ROOT / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8")
    )
    for e in codex_mp["plugins"]:
        src = e["source"]
        if isinstance(src, dict) and src.get("source") == "local":
            assert src["path"].startswith("./"), (
                f"codex marketplace: {e['name']} source.path={src['path']!r} 必须以 ./ 开头"
            )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))
