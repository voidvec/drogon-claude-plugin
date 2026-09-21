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

EXPECTED_SKILLS = 22

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
    assert len(skills) == EXPECTED_SKILLS, f"skills: {len(skills)} != {EXPECTED_SKILLS}: {skills}"
    for name in EXPECTED_NEW_SKILLS:
        assert name in skills, f"missing new skill {name}"


def test_every_skill_has_skill_md_with_frontmatter():
    for name in _skills():
        skill_md = REPO_ROOT / "skills" / name / "SKILL.md"
        assert skill_md.is_file(), f"{name}: missing SKILL.md"
        text = skill_md.read_text(encoding="utf-8")
        assert text.startswith("---"), f"{name}: SKILL.md must start with frontmatter"
        fm = text.split("---", 2)[1]
        m = re.search(r"^name:\s*(\S+)", fm, re.M)
        assert m and m.group(1) == name, f"{name}: frontmatter name mismatch"
        assert re.search(r"^description:\s*\S", fm, re.M), f"{name}: missing description"
        assert re.search(r"^version:\s*\S", fm, re.M), f"{name}: missing version"


def test_every_skill_has_code_guide():
    for name in _skills():
        guide = REPO_ROOT / "skills" / name / "references" / "code-guide.md"
        assert guide.is_file(), f"{name}: missing references/code-guide.md"
        content = guide.read_text(encoding="utf-8")
        assert len(content.splitlines()) >= 40, f"{name}: code-guide.md suspiciously thin"


def test_claude_md_routes_every_skill():
    text = (REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    for name in _skills():
        assert name in text, f"CLAUDE.md routing table missing {name}"


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
    assert zcode.get("skills") == "skills"


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


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))
