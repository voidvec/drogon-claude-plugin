"""Multi-host integration tests: generator artifacts, CLI v3 per-host
install/uninstall, instruction-file three-state protection, scan contract,
and version consistency across every host manifest.

Run:  python -m pytest tests/test_hosts.py
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from drogon_plugin import cli as cli_mod  # noqa: E402

# 加载生成器模块(与 posttooluse 测试同法)
_spec = importlib.util.spec_from_file_location(
    "gen_host_artifacts", REPO_ROOT / "scripts" / "gen-host-artifacts.py"
)
gen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gen)

MARKER_BEGIN = "<!-- drogon-plugin begin -->"


# ---------------------------------------------------------------------------
# 生成器产物
# ---------------------------------------------------------------------------


def _version():
    return (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()


def test_agents_md_is_transformed_from_claude_md():
    text = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    # 去宿主专有:安装/升级章节必须被剥离
    assert "## 安装 / 升级" not in text
    # 规则主体保留
    for marker in ("异步回调模型", "Skill 路由表", "drogon-gen-orm-model", "防错兜底"):
        assert marker in text, f"missing {marker}"
    # 生成说明 + 路由表可用性说明
    assert "自动生成" in text and "请勿手改" in text
    assert "领域地图" in text


def test_host_artifacts_exist_and_valid_json():
    for rel in (
        ".codex-plugin/plugin.json",
        ".agents/plugins/marketplace.json",
        "gemini-extension.json",
    ):
        p = REPO_ROOT / rel
        assert p.is_file(), f"missing {rel}"
        data = json.loads(p.read_text(encoding="utf-8"))
        assert isinstance(data, dict)


def test_codex_manifest_fields():
    m = json.loads((REPO_ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert m["name"] == "drogon"
    assert m["skills"] == "./skills/"
    assert m["hooks"] == "./hooks/hooks.json"
    assert m["interface"]["displayName"]


def test_codex_marketplace_policy_fields():
    """Codex marketplace 条目必填三件套 + category(developers.openai.com)。"""
    mp = json.loads((REPO_ROOT / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8"))
    entry = mp["plugins"][0]
    assert entry["name"] == "drogon"
    assert entry["policy"]["installation"] == "AVAILABLE"
    assert entry["policy"]["authentication"] == "ON_INSTALL"
    assert entry["category"]
    assert entry["source"]["source"] == "local"


def test_gemini_extension_fields():
    g = json.loads((REPO_ROOT / "gemini-extension.json").read_text(encoding="utf-8"))
    assert g["name"] == "drogon"
    assert g["contextFileName"] == "GEMINI.md"
    assert (REPO_ROOT / "GEMINI.md").is_file()


def test_gemini_md_content_matches_agents_md():
    a = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    g = (REPO_ROOT / "GEMINI.md").read_text(encoding="utf-8")
    assert a.strip() == g.strip()


def test_all_manifest_versions_match_version_file():
    v = _version()
    checks = {
        ".claude-plugin/plugin.json": lambda d: d["version"],
        ".zcode-plugin/plugin.json": lambda d: d["version"],
        ".claude-plugin/marketplace.json": lambda d: d["plugins"][0]["version"],
        ".codex-plugin/plugin.json": lambda d: d["version"],
        ".agents/plugins/marketplace.json": lambda d: d["plugins"][0]["version"],
        "gemini-extension.json": lambda d: d["version"],
        "npm/package.json": lambda d: d["version"],
    }
    for rel, get in checks.items():
        data = json.loads((REPO_ROOT / rel).read_text(encoding="utf-8"))
        assert get(data) == v, f"{rel} version != VERSION({v})"

    init_py = (REPO_ROOT / "src" / "drogon_plugin" / "__init__.py").read_text(encoding="utf-8")
    assert f'__version__ = "{v}"' in init_py
    assert f'PLUGIN_VERSION = "{v}"' in init_py
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert f'version = "{v}"' in pyproject


def test_generator_check_passes_on_repo():
    assert gen.check(_version()) == [], gen.check(_version())


def test_agents_md_reproducible():
    claude_md = (REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert gen.build_agents_md(claude_md, _version()) == (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI v3:多宿主安装 / 三态保护 / 卸载
# ---------------------------------------------------------------------------


def _run_cli(*argv):
    return cli_mod.main(list(argv))


def _make_project(tmp_path, with_user_agents=False):
    p = tmp_path / "proj"
    p.mkdir()
    if with_user_agents:
        (p / "AGENTS.md").write_text("# 我的项目规则\n\n- 自有规则\n", encoding="utf-8")
    return p


def test_install_all_hosts_artifacts(tmp_path):
    p = _make_project(tmp_path)
    assert _run_cli("install", "--target", str(p)) == 0

    assert (p / ".drogon-plugin" / ".claude-plugin" / "plugin.json").is_file()
    assert len(list((p / ".cursor" / "skills").iterdir())) == 22
    assert (p / ".cursor" / "rules" / "drogon-plugin.mdc").is_file()
    assert (p / ".trae" / "rules" / "drogon-plugin.mdc").is_file()
    for name in ("AGENTS.md", "GEMINI.md", "CODEBUDDY.md"):
        f = p / name
        assert f.is_file() and MARKER_BEGIN in f.read_text(encoding="utf-8")
    # 互斥规则:all 不落 .agents/skills
    assert not (p / ".agents").exists()
    # mdc 带 frontmatter
    mdc = (p / ".cursor" / "rules" / "drogon-plugin.mdc").read_text(encoding="utf-8")
    assert mdc.startswith("---") and "alwaysApply: true" in mdc


def test_install_preserves_user_agents_md(tmp_path):
    p = _make_project(tmp_path, with_user_agents=True)
    assert _run_cli("install", "--target", str(p)) == 0
    text = (p / "AGENTS.md").read_text(encoding="utf-8")
    assert text == "# 我的项目规则\n\n- 自有规则\n"  # 一字未动

    # force-agents → 追加标记段,用户内容仍在
    assert _run_cli("install", "--target", str(p), "--host", "qoder", "--force-agents") == 0
    text = (p / "AGENTS.md").read_text(encoding="utf-8")
    assert text.startswith("# 我的项目规则") and MARKER_BEGIN in text

    # 全量卸载 → 只删标记段,用户文件完整保留
    assert _run_cli("uninstall", "--target", str(p)) == 0
    assert (p / "AGENTS.md").read_text(encoding="utf-8") == "# 我的项目规则\n\n- 自有规则\n"


def test_copilot_host_opt_in(tmp_path):
    p = _make_project(tmp_path)
    assert _run_cli("install", "--target", str(p), "--host", "copilot") == 0
    assert len(list((p / ".agents" / "skills").iterdir())) == 22
    assert MARKER_BEGIN in (p / "AGENTS.md").read_text(encoding="utf-8")
    # 按宿主卸载
    assert _run_cli("uninstall", "--target", str(p), "--host", "copilot") == 0
    assert not (p / ".agents" / "skills").exists()
    assert not (p / ".agents").exists()


def test_full_uninstall_removes_everything_but_user_files(tmp_path):
    p = _make_project(tmp_path, with_user_agents=True)
    _run_cli("install", "--target", str(p))
    _run_cli("install", "--target", str(p), "--host", "copilot")
    assert _run_cli("uninstall", "--target", str(p)) == 0
    left = sorted(x.name for x in p.iterdir())
    assert left == ["AGENTS.md"], f"residue: {left}"


def test_unknown_host_rejected(tmp_path):
    p = _make_project(tmp_path)
    assert _run_cli("install", "--target", str(p), "--host", "notahost") == 1


def test_verify_reports_hosts(tmp_path, capsys):
    p = _make_project(tmp_path)
    _run_cli("install", "--target", str(p))
    assert _run_cli("verify", "--target", str(p)) == 0
    out = capsys.readouterr().out
    assert "cursor✅" in out and "copilot—" in out


# ---------------------------------------------------------------------------
# scan
# ---------------------------------------------------------------------------


def test_scan_finds_fixture_violations(tmp_path, capsys):
    p = _make_project(tmp_path)
    fixtures = REPO_ROOT / "tests" / "fixtures" / "scan"
    (p / "src").mkdir()
    (p / "src" / "bad.cc").write_text(
        (fixtures / "src" / "bad.cc").read_text(encoding="utf-8"), encoding="utf-8"
    )
    assert _run_cli("scan", "--target", str(p)) == 0
    out = capsys.readouterr().out
    assert "FILTER_ADD" in out

    assert _run_cli("scan", "--target", str(p), "--strict") == 1


def test_scan_rejects_outside_path(tmp_path, capsys):
    p = _make_project(tmp_path)
    assert _run_cli("scan", "--target", str(p), "..", "x.cc") == 2


def test_posttooluse_scan_cli_json_contract(tmp_path, capsys):
    fixtures = REPO_ROOT / "tests" / "fixtures" / "scan"
    p = tmp_path / "scanroot"
    (p / "src").mkdir(parents=True)
    (p / "src" / "bad.cc").write_text(
        (fixtures / "src" / "bad.cc").read_text(encoding="utf-8"), encoding="utf-8"
    )
    import os

    old = os.getcwd()
    os.chdir(p)
    try:
        rc = gen.__name__  # placeholder to keep referrer honest; actual call below
        import subprocess

        r = subprocess.run(
            [sys.executable, str(REPO_ROOT / "hooks" / "posttooluse.py"),
             "--scan", "--format", "json", "."],
            capture_output=True, text=True, encoding="utf-8", shell=False,
        )
        assert r.returncode == 0
        data = json.loads(r.stdout)
        assert data["total"] >= 3
        assert any("bad.cc" in f["file"] for f in data["findings"])
    finally:
        os.chdir(old)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))
