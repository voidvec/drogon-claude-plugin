"""Multi-host integration tests: generator artifacts, CLI v3 per-host
install/uninstall, instruction-file three-state protection, scan contract,
and version consistency across every host manifest.

Run:  python -m pytest tests/test_hosts.py
"""

import importlib.util
import json
import re
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

# 跨产物一致性门禁:与 CI 共用同一实现(scripts/check-consistency.py)
_cspec = importlib.util.spec_from_file_location(
    "check_consistency", REPO_ROOT / "scripts" / "check-consistency.py"
)
consistency = importlib.util.module_from_spec(_cspec)
_cspec.loader.exec_module(consistency)

MARKER_BEGIN = "<!-- drogon-plugin begin -->"

# 技能数量单一事实源:仓库 skills/ 目录(禁止硬编码)。
SKILL_COUNT = len([d for d in (REPO_ROOT / "skills").iterdir() if d.is_dir()])


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
    problems = gen.check(_version())
    assert problems == [], problems


# ---------------------------------------------------------------------------
# 跨产物一致性门禁(与 CI 同源)
# ---------------------------------------------------------------------------


def test_cross_artifact_consistency_gate_passes():
    problems = consistency.run_checks()
    assert problems == [], problems


def test_consistency_gate_covers_every_check():
    """门禁的检查项不得被静默清空(空列表 = 失效的护栏)。"""
    assert len(consistency.CHECKS) >= 6


# ---------------------------------------------------------------------------
# CLI 能力契约(PyPI = 参考实现;npm 的缺口必须显式登记)
# ---------------------------------------------------------------------------


def _capabilities():
    return json.loads((REPO_ROOT / "scripts" / "plugin-capabilities.json").read_text(encoding="utf-8"))


def test_pypi_commands_match_capability_declaration():
    decl = _capabilities()
    assert sorted(cli_mod.available_commands()) == sorted(decl["cli"]["pypi"]["commands"])


def test_npm_commands_match_capability_declaration():
    npm_src = (REPO_ROOT / "npm" / "bin" / "cli.js").read_text(encoding="utf-8")
    m = re.search(r"const COMMANDS = \[([^\]]*)\]", npm_src)
    assert m, "npm/bin/cli.js must expose a single COMMANDS constant"
    npm_cmds = sorted(re.findall(r"'([^']+)'", m.group(1)))
    assert npm_cmds == sorted(_capabilities()["cli"]["npm"]["commands"])


def test_npm_gap_is_declared_not_accidental():
    decl = _capabilities()
    gap = sorted(set(decl["cli"]["pypi"]["commands"]) - set(decl["cli"]["npm"]["commands"]))
    assert gap == sorted(decl["known_gaps"]["npm"]["commands"])
    assert decl["known_gaps"]["npm"]["reason"]


# ---------------------------------------------------------------------------
# verify 的资产漂移检测
# ---------------------------------------------------------------------------


def test_verify_detects_modified_asset(tmp_path, capsys):
    p = _make_project(tmp_path)
    assert _run_cli("install", "--target", str(p), "--host", "claude") == 0
    (p / ".drogon-plugin" / "CLAUDE.md").write_text("# tampered\n", encoding="utf-8")
    capsys.readouterr()
    assert _run_cli("verify", "--target", str(p)) == 1
    assert "资产被改动" in capsys.readouterr().out


def test_verify_detects_missing_asset(tmp_path, capsys):
    p = _make_project(tmp_path)
    assert _run_cli("install", "--target", str(p), "--host", "claude") == 0
    (p / ".drogon-plugin" / "CLAUDE.md").unlink()
    capsys.readouterr()
    assert _run_cli("verify", "--target", str(p)) == 1
    assert "资产缺失" in capsys.readouterr().out


def test_verify_clean_install_has_no_drift(tmp_path, capsys):
    p = _make_project(tmp_path)
    assert _run_cli("install", "--target", str(p), "--host", "claude") == 0
    capsys.readouterr()
    assert _run_cli("verify", "--target", str(p)) == 0
    out = capsys.readouterr().out
    assert "资产被改动" not in out and "资产缺失" not in out


# ---------------------------------------------------------------------------
# npm CLI 端到端(回归:曾出现"删了常量但漏改引用点"→ install 抛 ReferenceError,
# 而当时只查字面量的门禁与只跑 py 侧断言的测试都不会发现)
# ---------------------------------------------------------------------------


def _node():
    import shutil

    return shutil.which("node")


@pytest.mark.skipif(_node() is None, reason="node not available")
def test_npm_cli_install_verify_uninstall(tmp_path):
    import subprocess

    cli_js = str(REPO_ROOT / "npm" / "bin" / "cli.js")
    p = tmp_path / "npm_proj"
    p.mkdir()
    (p / "CLAUDE.md").write_text("# 我的项目\n", encoding="utf-8")

    def run(*argv):
        return subprocess.run(
            [_node(), cli_js, *argv], capture_output=True, text=True, encoding="utf-8"
        )

    r = run("install", "--target", str(p))
    assert r.returncode == 0, r.stdout + r.stderr
    assert (p / ".drogon-plugin" / ".claude-plugin" / "plugin.json").is_file()
    assert (p / ".drogon-plugin" / "skills").is_dir()

    # 回归(C4):无论走打包资产还是源码树回退,都**不得**把仓库级的非受管条目
    # 复制进用户项目(此前回退模式会把 .git / node_modules / tests 整仓拖进来)
    for unmanaged in ("scripts", "tests", "npm", "docs", ".github", ".git", "package.json"):
        assert not (p / ".drogon-plugin" / unmanaged).exists(), f"整仓复制: {unmanaged}"

    r = run("verify", "--target", str(p))
    assert r.returncode == 0, r.stdout + r.stderr

    r = run("uninstall", "--target", str(p))
    assert r.returncode == 0, r.stdout + r.stderr
    assert not (p / ".drogon-plugin").exists()
    assert (p / "CLAUDE.md").read_text(encoding="utf-8") == "# 我的项目\n"


# ---------------------------------------------------------------------------
# 按宿主卸载的对称性与共享资源保护
# ---------------------------------------------------------------------------


ALL_HOSTS = sorted(cli_mod.HOSTS)


@pytest.mark.parametrize("host", ALL_HOSTS)
def test_uninstall_per_host_leaves_no_residue(tmp_path, host):
    """install --host X 与 uninstall --host X 必须严格互逆(回归 C1:bundle 曾静默空操作)。"""
    p = _make_project(tmp_path)
    assert _run_cli("install", "--target", str(p), "--host", host) == 0
    assert sorted(x.name for x in p.iterdir()) != [], f"{host}: install 未产生任何产物"
    assert _run_cli("uninstall", "--target", str(p), "--host", host) == 0
    left = sorted(x.name for x in p.iterdir())
    assert left == [], f"{host}: 卸载后残留 {left}"


def test_uninstall_bundle_host_removes_dot_drogon_plugin(tmp_path):
    p = _make_project(tmp_path)
    assert _run_cli("install", "--target", str(p), "--host", "claude") == 0
    assert (p / ".drogon-plugin").is_dir()
    assert _run_cli("uninstall", "--target", str(p), "--host", "claude") == 0
    assert not (p / ".drogon-plugin").exists()


def test_uninstall_one_host_keeps_shared_instruction_file(tmp_path):
    """回归(C2):卸载单个宿主不得删掉仍被其它宿主使用的 AGENTS.md(也不得剥其标记段)。"""
    p = _make_project(tmp_path)
    assert _run_cli("install", "--target", str(p), "--host", "codex") == 0
    assert _run_cli("install", "--target", str(p), "--host", "qoder") == 0
    ag = p / "AGENTS.md"
    assert ag.is_file() and MARKER_BEGIN in ag.read_text(encoding="utf-8")

    assert _run_cli("uninstall", "--target", str(p), "--host", "qoder") == 0
    assert ag.is_file(), "AGENTS.md 被误删(codex 仍在使用)"
    assert MARKER_BEGIN in ag.read_text(encoding="utf-8"), "标记段被误剥(codex 仍在使用)"
    stamp = json.loads((p / ".drogon-plugin-install.json").read_text(encoding="utf-8"))
    assert "qoder" not in stamp["hosts"] and "codex" in stamp["hosts"]

    # 最后一个使用者被卸载 → 整份删除(文件由我们创建)
    assert _run_cli("uninstall", "--target", str(p), "--host", "codex") == 0
    assert not ag.exists()
    assert sorted(x.name for x in p.iterdir()) == [], "codex 卸载后仍有残留"


def test_uninstall_never_installed_shared_skills_host_is_noop(tmp_path):
    """回归(H2):copilot 与 agents 共用 .agents/skills —— 卸载未安装的那个不得清空已装的。"""
    p = _make_project(tmp_path)
    assert _run_cli("install", "--target", str(p), "--host", "copilot") == 0
    n_before = len(list((p / ".agents" / "skills").iterdir()))
    assert n_before == SKILL_COUNT

    assert _run_cli("uninstall", "--target", str(p), "--host", "agents") == 0
    assert (p / ".agents" / "skills").is_dir(), ".agents/skills 被误删"
    assert len(list((p / ".agents" / "skills").iterdir())) == n_before, "copilot 的技能被误删"
    assert (p / "AGENTS.md").is_file(), "copilot 的 AGENTS.md 被误删"


def test_uninstall_marker_only_host_removes_install_stamp(tmp_path):
    """回归(M1):预置用户自有 AGENTS.md 时,卸载应剥标记段且不残留安装戳。"""
    p = _make_project(tmp_path, with_user_agents=True)
    assert _run_cli("install", "--target", str(p), "--host", "qoder", "--force-agents") == 0
    assert MARKER_BEGIN in (p / "AGENTS.md").read_text(encoding="utf-8")

    assert _run_cli("uninstall", "--target", str(p), "--host", "qoder") == 0
    assert (p / "AGENTS.md").read_text(encoding="utf-8") == "# 我的项目规则\n\n- 自有规则\n"
    assert sorted(x.name for x in p.iterdir()) == ["AGENTS.md"], "安装戳残留"


def test_reinstall_after_damaged_marker_section_repairs_it(tmp_path):
    """回归(H3):标记段半损坏(只有 begin 没有 end)时,返回 marker 必须名副其实。"""
    p = _make_project(tmp_path)
    (p / "AGENTS.md").write_text(
        "# 我的项目规则\n\n<!-- drogon-plugin begin -->\n(用户手改坏了,没有 end)\n",
        encoding="utf-8",
    )
    assert _run_cli("install", "--target", str(p), "--host", "qoder") == 0
    text = (p / "AGENTS.md").read_text(encoding="utf-8")
    assert "我的项目规则" in text, "用户自有内容被破坏"
    assert text.count(MARKER_BEGIN) == 1 and "<!-- drogon-plugin end -->" in text, "标记段未被修复"
    # 修复后卸载能真正剥干净
    assert _run_cli("uninstall", "--target", str(p), "--host", "qoder") == 0
    rest = (p / "AGENTS.md").read_text(encoding="utf-8")
    assert MARKER_BEGIN not in rest and "我的项目规则" in rest


@pytest.mark.skipif(_node() is None, reason="node not available")
def test_npm_cli_declares_capabilities(tmp_path):
    import subprocess

    r = subprocess.run(
        [_node(), str(REPO_ROOT / "npm" / "bin" / "cli.js"), "--capabilities"],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["cli"] == "npm"
    assert data["commands"] == _capabilities()["cli"]["npm"]["commands"]


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
    assert len(list((p / ".cursor" / "skills").iterdir())) == SKILL_COUNT
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
    assert len(list((p / ".agents" / "skills").iterdir())) == SKILL_COUNT
    assert MARKER_BEGIN in (p / "AGENTS.md").read_text(encoding="utf-8")
    # 按宿主卸载
    assert _run_cli("uninstall", "--target", str(p), "--host", "copilot") == 0
    assert not (p / ".agents" / "skills").exists()
    assert not (p / ".agents").exists()


def test_full_action_not_downgraded_by_marker(tmp_path):
    """回归:full(我们创建的文件)不因后装宿主的 marker 记录而降级,
    否则全量卸载只剥标记段、残留空文件。"""
    p = _make_project(tmp_path)  # 无 AGENTS.md
    _run_cli("install", "--target", str(p), "--host", "codex")  # → full
    _run_cli("install", "--target", str(p), "--host", "copilot")  # → marker(覆盖风险点)
    assert _run_cli("uninstall", "--target", str(p)) == 0
    assert not (p / "AGENTS.md").exists(), "full 创建的文件应被完整删除"
    left = sorted(x.name for x in p.iterdir())
    assert left == []


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
