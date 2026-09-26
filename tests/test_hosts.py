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

    # 回归(P2):copyFileSync 不携带源 mode,Linux/macOS 上钩子脚本丢可执行位
    # → 宿主直接执行 command 时 Permission denied、钩子静默失效。
    if sys.platform != "win32":
        import stat

        for rel in ("hooks/run-hook.cmd", "hooks/session-start",
                    "hooks/post-tool-use", "hooks/posttooluse.py"):
            f = p / ".drogon-plugin" / rel
            assert f.is_file(), f"缺少 {rel}"
            assert stat.S_IXUSR & f.stat().st_mode, f"{rel}: 丢可执行位(copyFileSync 不保 mode)"

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


@pytest.mark.skipif(_node() is None, reason="node not available")
def test_npm_uninstall_removes_pypi_v3_stamp(tmp_path):
    """回归 L1:PyPI CLI 装的 v3 安装戳,npm uninstall 须一并清除,不得永久残留。

    两个 CLI 共用 `.drogon-plugin/`,但 v3 戳 `.drogon-plugin-install.json` 落在
    项目根、由 PyPI CLI 独占写入;此前 npm uninstall 只删目录、不识别 v3 戳。
    """
    import subprocess

    p = tmp_path / "interop"
    p.mkdir()
    # 用 PyPI CLI 装 bundle 宿主(claude):产生 .drogon-plugin/ 与根目录 v3 戳
    assert _run_cli("install", "--target", str(p), "--host", "claude") == 0
    v3 = p / ".drogon-plugin-install.json"
    assert (p / ".drogon-plugin").is_dir()
    assert v3.is_file(), "前提:PyPI 安装应写 v3 戳"

    r = subprocess.run(
        [_node(), str(REPO_ROOT / "npm" / "bin" / "cli.js"), "uninstall", "--target", str(p)],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert not (p / ".drogon-plugin").exists()
    assert not v3.exists(), "L1 复发:npm uninstall 未清除 PyPI 写的 v3 安装戳"
    assert sorted(x.name for x in p.iterdir()) == [], f"互操作卸载后残留 {sorted(x.name for x in p.iterdir())}"


@pytest.mark.skipif(_node() is None, reason="node not available")
def test_npm_target_missing_value_errors_not_silent_cwd(tmp_path):
    """回归 L2:npm `--target` 缺值应报错退出(与 py argparse 对齐),不得静默按 cwd 执行。"""
    import subprocess

    cli_js = str(REPO_ROOT / "npm" / "bin" / "cli.js")
    r = subprocess.run(
        [_node(), cli_js, "verify", "--target"],
        capture_output=True, text=True, encoding="utf-8", cwd=str(tmp_path),
    )
    assert r.returncode == 2, (
        f"L2 复发:--target 缺值应退出码 2(用法错误),实得 {r.returncode}\n{r.stdout}{r.stderr}"
    )
    assert "target" in (r.stdout + r.stderr).lower(), "缺值应给出指向 --target 的用法提示"


@pytest.mark.skipif(_node() is None, reason="node not available")
def test_npm_target_empty_or_option_like_value_errors(tmp_path):
    """L2 补漏(评审):空串取值经 `args.target || cwd` 仍会静默回退 cwd;
    取值形似选项(--foo)也必须报用法错误。两支都退出码 2。"""
    import subprocess

    cli_js = str(REPO_ROOT / "npm" / "bin" / "cli.js")
    for bad in ("", "--foo"):
        r = subprocess.run(
            [_node(), cli_js, "verify", "--target", bad],
            capture_output=True, text=True, encoding="utf-8", cwd=str(tmp_path),
        )
        assert r.returncode == 2, (
            f"L2 残留:--target {bad!r} 应退出码 2,实得 {r.returncode}\n{r.stdout}{r.stderr}"
        )


@pytest.mark.skipif(_node() is None, reason="node not available")
def test_npm_uninstall_keeps_mixed_host_v3_stamp(tmp_path):
    """L1 正向对照:混合宿主(含 bundle 之外)的 v3 戳不得被 npm uninstall 删除。

    根指令文件由各宿主安装器各自管理;npm 只清纯 bundle 安装,
    混合安装必须保留记录并提示用 PyPI CLI 收尾,否则会删掉别人依赖的账本。
    评审补漏:此前用 `--host claude --host agents`(argparse store 后者覆盖前者,
    实际只装了 agents)未构造真混合;现用逗号形式一次装两类通道。
    """
    import json
    import subprocess

    p = tmp_path / "mixed"
    p.mkdir()
    assert _run_cli("install", "--target", str(p), "--host", "claude,agents") == 0
    v3 = p / ".drogon-plugin-install.json"
    hosts_before = json.loads(v3.read_text(encoding="utf-8"))["hosts"]
    assert {"claude", "zcode", "agents"} <= set(hosts_before), f"前提:真混合安装 {hosts_before}"
    assert (p / ".drogon-plugin").is_dir(), "前提:claude 通道应落 bundle"
    agents_md = (p / "AGENTS.md").read_text(encoding="utf-8")

    r = subprocess.run(
        [_node(), str(REPO_ROOT / "npm" / "bin" / "cli.js"), "uninstall", "--target", str(p)],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert not (p / ".drogon-plugin").exists(), "npm 应清掉自己管的 bundle"
    assert v3.is_file(), "混合宿主戳被误删:npm 只应清除纯 bundle(claude/zcode)安装"
    assert json.loads(v3.read_text(encoding="utf-8"))["hosts"] == hosts_before, (
        "保留的戳内容被改写(账本必须原样)"
    )
    assert (p / "AGENTS.md").read_text(encoding="utf-8") == agents_md, (
        "agents 宿主的根指令文件应原样保留"
    )
    assert "drogon-claude-plugin uninstall" in (r.stdout + r.stderr), "应提示用 PyPI CLI 收尾"


# ---------------------------------------------------------------------------
# 回归(第三轮批次④-C):M4′ 残缺包放行 / L3 整删用户追加 / L5 半途孤儿
# ---------------------------------------------------------------------------


def test_verify_flags_zero_bundled_skill_count(tmp_path, capsys, monkeypatch):
    """回归(M4′):随包枚举为 0 = 包本身残缺,计数校验不得退化成"非空即过"。

    用已装好的项目 + monkeypatch 把 `_bundled_skill_count` 打成 0 来复现残缺包:
    verify 必须显式报问题,而不是静默按"目录非空"放行。
    """
    p = _make_project(tmp_path)
    assert _run_cli("install", "--target", str(p), "--host", "claude") == 0
    monkeypatch.setattr(cli_mod, "_bundled_skill_count", lambda: 0)
    capsys.readouterr()
    assert _run_cli("verify", "--target", str(p)) == 1, "残缺包(expected=0)verify 被静默放行"
    out = capsys.readouterr().out
    assert "随包" in out and "0" in out, f"缺少残缺包诊断: {out}"


def test_host_skill_dir_check_not_silently_passed_when_broken(tmp_path, monkeypatch):
    """M4′ 同源:expected==0 时 _skills_ok 不得返回 True(残缺包"非空即过")。"""
    p = _make_project(tmp_path)
    assert _run_cli("install", "--target", str(p), "--host", "agents") == 0
    monkeypatch.setattr(cli_mod, "_bundled_skill_count", lambda: 0)
    skills_dir = p / ".agents" / "skills"
    assert skills_dir.is_dir() and any(skills_dir.iterdir()), "前提:agents 宿主应落了技能目录"
    assert not cli_mod._skills_ok(skills_dir), "_skills_ok 在随包枚举=0 时仍放行(M4′ 复发)"


@pytest.mark.skipif(_node() is None, reason="node not available")
def test_npm_verify_fails_loudly_on_broken_package(tmp_path):
    """M4′ 的 npm 侧:随包 skills 枚举为 0(找不到资产)时 verify 必须报错退出。

    把 cli.js 复制到一个既无 assets/ 也非仓库子树的目录 → findAssets() 抛错 →
    bundledSkillCount()=0;对一个完好安装的项目跑 verify,不得因"非空即过"放行。
    """
    import shutil as _sh
    import subprocess

    proj = tmp_path / "proj"
    proj.mkdir()
    assert _run_cli("install", "--target", str(proj), "--host", "claude") == 0

    pkg = tmp_path / "broken"
    (pkg / "bin").mkdir(parents=True)
    _sh.copy(REPO_ROOT / "npm" / "bin" / "cli.js", pkg / "bin" / "cli.js")
    (pkg / "package.json").write_text('{"name":"x","version":"0"}', encoding="utf-8")

    r = subprocess.run(
        [_node(), str(pkg / "bin" / "cli.js"), "verify", "--target", str(proj)],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert r.returncode == 1, f"残缺包下 npm verify 静默放行(M4′ 复发):\n{r.stdout}{r.stderr}"
    assert "随包" in (r.stdout + r.stderr), f"缺少残缺包诊断: {r.stdout}{r.stderr}"


def test_uninstall_keeps_foreign_content_added_to_full_instruction(tmp_path, capsys):
    """回归(L3):full 归属的指令文件被用户追加内容后,卸载不得整删。

    此前 v3 戳不记哈希,uninstall 见 action==full 就 unlink → 用户追加的自有
    章节一起消失。修复方向:标记段之外仍有实质内容 → 只剥标记段 + 显式告警。
    """
    p = _make_project(tmp_path)
    assert _run_cli("install", "--target", str(p), "--host", "agents") == 0
    f = p / "AGENTS.md"
    assert f.is_file(), "前提:agents 宿主应创建 AGENTS.md"
    assert f.read_text(encoding="utf-8").startswith(MARKER_BEGIN), "前提:full 归属=整文件标记段"
    f.write_text(
        f.read_text(encoding="utf-8") + "\n## 项目自有部署说明\n务必保留我写的这段。\n",
        encoding="utf-8",
    )
    capsys.readouterr()
    assert _run_cli("uninstall", "--target", str(p), "--host", "agents") == 0
    out = capsys.readouterr().out
    assert f.is_file() and "务必保留我写的这段" in f.read_text(encoding="utf-8"), (
        f"L3 复发:含用户追加内容的 full 指令文件被整删\n{out}"
    )
    assert MARKER_BEGIN not in f.read_text(encoding="utf-8"), "标记段应已被剥离"
    assert "自有内容" in out or "告警" in out or "⚠" in out, f"删前未告警: {out}"


def test_uninstall_pure_full_instruction_still_fully_removed(tmp_path):
    """L3 正向对照:用户没动过的 full 指令文件(剥掉标记段即空)仍须整删,不留空壳。"""
    p = _make_project(tmp_path)
    assert _run_cli("install", "--target", str(p), "--host", "agents") == 0
    f = p / "AGENTS.md"
    assert _run_cli("uninstall", "--target", str(p), "--host", "agents") == 0
    assert not f.exists(), "纯插件产物未整删:留下无主空壳文件"
    assert sorted(x.name for x in p.iterdir()) == [], "卸载残留(正向对照)"


def test_uninstall_full_instruction_with_undecodable_bytes_keeps_file(tmp_path, capsys):
    """L3 边界(评审补漏):full 归属指令文件非 UTF-8(如用户转了 GBK 编码)→
    uninstall 不得 UnicodeDecodeError 崩溃;读不动就当"含用户内容":原样保留 + 告警。"""
    p = _make_project(tmp_path)
    assert _run_cli("install", "--target", str(p), "--host", "agents") == 0
    f = p / "AGENTS.md"
    raw = b"\xff\xfe" + "我的规则".encode("gbk", errors="replace")
    f.write_bytes(raw)
    capsys.readouterr()
    assert _run_cli("uninstall", "--target", str(p), "--host", "agents") == 0, (
        "非 UTF-8 指令文件令 uninstall 崩溃(应保守保留)"
    )
    assert f.read_bytes() == raw, "读不动的文件被改动/删除(应原样保留)"
    out = capsys.readouterr().out
    assert "⚠" in out or "保留" in out, f"未告警: {out}"


def test_install_midway_failure_leaves_no_orphans(tmp_path, capsys, monkeypatch):
    """回归(L5):install 循环中途抛异常 → 已落盘产物必须回滚,不得留孤儿。

    此前异常一路冒到 main() 的兜底 except:退出码对了,但前面宿主写下的
    技能目录留在项目里,而 v3 戳未更新 → 无人认领的孤儿文件。
    """
    import shutil as _sh

    real_copytree = _sh.copytree
    state = {"n": 0}

    def flaky(src, dst, *a, **kw):
        # 只数顶层技能目录(real copytree 递归会带 7 个位置参数回调本函数)
        s = Path(src)
        if s.name.startswith("drogon-") and s.parent.name == "skills":
            state["n"] += 1
            if state["n"] >= 3:
                raise OSError("注入:磁盘写失败")
        return real_copytree(src, dst, *a, **kw)

    monkeypatch.setattr(_sh, "copytree", flaky)
    p = _make_project(tmp_path)
    rc = _run_cli("install", "--target", str(p), "--host", "agents")
    assert rc == 1, f"半途失败未返回非零? rc={rc}"

    base = p / ".agents" / "skills"
    leftovers = [d.name for d in base.iterdir()] if base.is_dir() else []
    assert leftovers == [], f"L5 复发:失败安装留下孤儿技能目录 {leftovers}"
    assert not (p / "AGENTS.md").exists(), "L5 复发:失败安装留下指令文件孤儿"
    assert not (p / ".drogon-plugin-install.json").exists(), "失败安装不得更新安装戳"


def test_install_midway_failure_restores_preexisting_instruction(tmp_path, capsys, monkeypatch):
    """L5 正向对照:回滚只清"本次新增",不得动用户原有文件的内容。

    用户对已存在的 AGENTS.md 只有我们写的标记段时,marker 编辑回滚等价于剥段;
    这里验证用户自有内容原样保留。
    """
    import shutil as _sh

    p = _make_project(tmp_path)
    (p / "AGENTS.md").write_text("# 我的项目规则\n\n- 自有规则\n", encoding="utf-8")

    real_copytree = _sh.copytree
    state = {"n": 0}

    def flaky(src, dst, *a, **kw):
        s = Path(src)
        if s.name.startswith("drogon-") and s.parent.name == "skills":
            state["n"] += 1
            if state["n"] >= 3:
                raise OSError("注入:磁盘写失败")
        return real_copytree(src, dst, *a, **kw)

    monkeypatch.setattr(_sh, "copytree", flaky)
    assert _run_cli("install", "--target", str(p), "--host", "agents") == 1
    text = (p / "AGENTS.md").read_text(encoding="utf-8")
    assert text == "# 我的项目规则\n\n- 自有规则\n", f"回滚动了用户原文件:\n{text!r}"


def test_install_midway_failure_strips_marker_from_user_instruction(tmp_path, monkeypatch):
    """L5 marker 回滚分支覆盖(评审补漏,此前零覆盖)。

    单宿主 install 时技能先于指令文件落盘,失败点永远够不到 marker 编辑;
    这里让第一个宿主(agents)完整走完技能+标记段追加,第二个宿主(cursor)
    技能复制时才炸 —— 回滚必须剥掉本次追加的标记段、用户内容一字不动。
    """
    import shutil as _sh

    p = _make_project(tmp_path, with_user_agents=True)
    real_copytree = _sh.copytree
    state = {"n": 0}

    def flaky(src, dst, *a, **kw):
        s = Path(src)
        if s.name.startswith("drogon-") and s.parent.name == "skills":
            state["n"] += 1
            if state["n"] > SKILL_COUNT:  # 进入第二个宿主的技能复制才炸
                raise OSError("注入:磁盘写失败")
        return real_copytree(src, dst, *a, **kw)

    monkeypatch.setattr(_sh, "copytree", flaky)
    rc = _run_cli("install", "--target", str(p), "--host", "agents,cursor", "--force-agents")
    assert rc == 1, f"半途失败未返回非零? rc={rc}"

    text = (p / "AGENTS.md").read_text(encoding="utf-8")
    assert "# 我的项目规则" in text and "- 自有规则" in text, f"用户内容被动了:\n{text!r}"
    assert MARKER_BEGIN not in text, f"回滚未剥掉本次追加的标记段:\n{text!r}"
    base = p / ".agents" / "skills"
    leftovers = [d.name for d in base.iterdir()] if base.is_dir() else []
    assert leftovers == [], f"回滚留下孤儿技能目录 {leftovers}"
    assert not (p / ".cursor" / "skills").exists() or not any((p / ".cursor" / "skills").iterdir()), (
        "cursor 半途产物未清"
    )
    assert not (p / ".drogon-plugin-install.json").exists(), "失败安装不得更新安装戳"


def test_install_failure_restores_previous_bundle(tmp_path, monkeypatch):
    """L5 评审补漏:重装 claude 半途失败,此前实现先 rmtree 旧 bundle → 回滚只删
    残缺新 bundle,旧 bundle 永久丢失而旧戳仍宣称已装。修复方向:旧 bundle 改名
    备份,成功删备份、失败原样恢复。"""
    import shutil as _sh

    p = _make_project(tmp_path)
    assert _run_cli("install", "--target", str(p), "--host", "claude") == 0
    bundle = p / ".drogon-plugin"
    sentinel = bundle / "OLD-SENTINEL.txt"
    sentinel.write_text("old-bundle", encoding="utf-8")

    real_copy2 = _sh.copy2
    state = {"n": 0}

    def flaky(src, dst, *a, **kw):
        state["n"] += 1
        if state["n"] >= 5:
            raise OSError("注入:磁盘写失败")
        return real_copy2(src, dst, *a, **kw)

    monkeypatch.setattr(_sh, "copy2", flaky)
    assert _run_cli("install", "--target", str(p), "--host", "claude") == 1
    assert sentinel.is_file(), "旧 bundle 未随回滚恢复(被 rmtree 摧毁,不可回退)"
    assert (bundle / "CLAUDE.md").is_file(), "恢复后的旧 bundle 应完整可用"
    leftovers = [x.name for x in p.iterdir() if ".old-" in x.name]
    assert leftovers == [], f"备份目录残留: {leftovers}"


def test_install_keyboard_interrupt_rolls_back(tmp_path, monkeypatch):
    """L5 评审补漏:except Exception 不捕 KeyboardInterrupt → Ctrl+C 场景孤儿依旧。
    中断也必须回滚本次写入,退出码 130。"""
    import shutil as _sh

    p = _make_project(tmp_path)
    real_copytree = _sh.copytree
    state = {"n": 0}

    def flaky(src, dst, *a, **kw):
        s = Path(src)
        if s.name.startswith("drogon-") and s.parent.name == "skills":
            state["n"] += 1
            if state["n"] >= 3:
                raise KeyboardInterrupt
        return real_copytree(src, dst, *a, **kw)

    monkeypatch.setattr(_sh, "copytree", flaky)
    rc = _run_cli("install", "--target", str(p), "--host", "agents")
    assert rc == 130, f"Ctrl+C 应返回 130,实得 {rc}"
    base = p / ".agents" / "skills"
    leftovers = [d.name for d in base.iterdir()] if base.is_dir() else []
    assert leftovers == [], f"中断留下孤儿技能目录 {leftovers}"
    assert not (p / "AGENTS.md").exists(), "中断留下指令文件孤儿"
    assert not (p / ".drogon-plugin-install.json").exists(), "中断不得更新安装戳"


# ---------------------------------------------------------------------------
# 回归(第三轮批次④ N4/N5):qoder / codebuddy 的官方技能发现通道
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "host,skills_dir,instruction",
    [
        ("qoder", ".qoder/skills", "AGENTS.md"),
        ("codebuddy", ".codebuddy/skills", "CODEBUDDY.md"),
    ],
)
def test_qoder_codebuddy_use_official_skill_channel(tmp_path, host, skills_dir, instruction):
    """N4/N5:此前两宿主 kind=instruction,只落规则文件,官方技能通道整体空置。

    增强方向(加法,不改既有通道):技能按宿主专属目录投放,指令文件照旧,
    宿主不认该目录时用户仅得冗余副本 —— 与 cursor/copilot/trae 的既有做法同构。
    """
    p = _make_project(tmp_path)
    assert _run_cli("install", "--target", str(p), "--host", host) == 0

    base = p / skills_dir
    assert base.is_dir(), f"{host}: 未投放官方技能通道 {skills_dir}"
    assert len([d for d in base.iterdir() if d.is_dir()]) == SKILL_COUNT, f"{host}: 技能数不全"
    assert (base / "drogon-create-controller" / "SKILL.md").is_file()
    assert (p / instruction).is_file(), f"{host}: 指令文件通道被改坏(应为加法非替换)"

    assert _run_cli("verify", "--target", str(p)) == 0, f"{host}: 新通道未纳入 verify"
    assert _run_cli("uninstall", "--target", str(p), "--host", host) == 0
    left = sorted(x.name for x in p.iterdir())
    assert left == [], f"{host}: 卸载残留 {left}"


def test_qoder_skill_uninstall_keeps_host_shared_by_others(tmp_path):
    """N4 守卫方向:qoder 的技能目录不得被别的宿主卸载连带删除。

    copilot/agents 共用 .agents/skills;qoder 独占 .qoder/skills。卸载 copilot
    只应动 .agents/skills,.qoder/skills 必须原样留下。
    """
    p = _make_project(tmp_path)
    assert _run_cli("install", "--target", str(p), "--host", "qoder") == 0
    assert _run_cli("install", "--target", str(p), "--host", "copilot") == 0

    assert _run_cli("uninstall", "--target", str(p), "--host", "copilot") == 0
    qskills = p / ".qoder" / "skills"
    assert qskills.is_dir() and len(list(qskills.iterdir())) == SKILL_COUNT, (
        "卸载 copilot 后 qoder 独占技能目录应完整保留(数量不减)"
    )
    assert (qskills / "drogon-create-controller" / "SKILL.md").is_file(), (
        "卸载 copilot 连带删掉了 qoder 独占的技能目录"
    )
    assert not (p / ".agents" / "skills" / "drogon-create-controller").exists(), (
        "copilot 自身技能未清"
    )


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
    # 回归(R10):Trae 官方规则是 .trae/rules/*.md,文档零处 .mdc;改为
    # skills(.trae/skills)+ AGENTS.md 指令文件双通道,不再投放 inert 的 .mdc
    assert len(list((p / ".trae" / "skills").iterdir())) == SKILL_COUNT
    assert not (p / ".trae" / "rules").exists()
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


def test_trae_host_installs_skills_and_agents_md_not_mdc(tmp_path):
    """回归(R10):Trae 官方文档规则落点为 .trae/rules/*.md,从未支持 .mdc;
    旧产物 .trae/rules/drogon-plugin.mdc 是宿主不读的 inert 文件。
    新落点 = .trae/skills(技能)+ AGENTS.md(规则,Trae 官方兼容)。"""
    p = _make_project(tmp_path)
    assert _run_cli("install", "--target", str(p), "--host", "trae") == 0
    assert len(list((p / ".trae" / "skills").iterdir())) == SKILL_COUNT
    assert MARKER_BEGIN in (p / "AGENTS.md").read_text(encoding="utf-8")
    assert not (p / ".trae" / "rules").exists(), "仍投放 Trae 不读取的 .mdc"
    # 幂等卸载:对称互逆(参数化测试之外再钉死本宿主的空目录清理)
    assert _run_cli("uninstall", "--target", str(p), "--host", "trae") == 0
    assert sorted(x.name for x in p.iterdir()) == []


def test_upgrade_is_idempotent_for_installed_hosts(tmp_path):
    p = _make_project(tmp_path)
    assert _run_cli("install", "--target", str(p), "--host", "trae") == 0
    left_before = sorted(x.name for x in p.rglob("*") if x.is_file())
    assert _run_cli("upgrade", "--target", str(p)) == 0
    left_after = sorted(x.name for x in p.rglob("*") if x.is_file())
    assert left_after == left_before, "upgrade 应幂等,不新增/丢失文件"


def test_verify_reports_hosts(tmp_path, capsys):
    p = _make_project(tmp_path)
    _run_cli("install", "--target", str(p))
    assert _run_cli("verify", "--target", str(p)) == 0
    out = capsys.readouterr().out
    assert "cursor✅" in out and "copilot—" in out


# ---------------------------------------------------------------------------
# upgrade 语义(回归 R4:曾无条件 force_agents=True 且按 ALL_HOSTS 重装,
# 把标记段强推进用户自有 AGENTS.md,并给用户只装过 cursor 的项目凭空落下
# gemini/codebuddy/trae 等八个宿主的产物)
# ---------------------------------------------------------------------------


def test_upgrade_only_repairs_installed_hosts(tmp_path):
    p = _make_project(tmp_path)
    assert _run_cli("install", "--target", str(p), "--host", "cursor,gemini") == 0
    assert _run_cli("upgrade", "--target", str(p)) == 0
    # cursor/gemini 的产物完好
    assert (p / ".cursor" / "rules" / "drogon-plugin.mdc").is_file()
    assert (p / "GEMINI.md").is_file()
    # 未安装宿主不得被 upgrade 凭空落地
    assert not (p / "CODEBUDDY.md").exists(), "upgrade 按 ALL_HOSTS 重装:codebuddy 凭空出现"
    assert not (p / ".trae").exists(), "upgrade 按 ALL_HOSTS 重装:trae 凭空出现"
    assert not (p / "AGENTS.md").exists(), "upgrade 按 ALL_HOSTS 重装:codex/qoder 凭空出现"
    stamp = json.loads((p / ".drogon-plugin-install.json").read_text(encoding="utf-8"))
    assert sorted(stamp["hosts"]) == ["cursor", "gemini"]


def test_upgrade_never_forces_marker_into_user_instruction_files(tmp_path):
    """用户自有 AGENTS.md:upgrade 默认(不带 --force-agents)必须一字不动。"""
    p = _make_project(tmp_path, with_user_agents=True)
    assert _run_cli("install", "--target", str(p), "--host", "cursor") == 0
    assert _run_cli("upgrade", "--target", str(p)) == 0
    assert (p / "AGENTS.md").read_text(encoding="utf-8") == "# 我的项目规则\n\n- 自有规则\n"


def test_upgrade_accepts_explicit_host_and_force_agents(tmp_path):
    """upgrade 与 install 共享粒度参数:--host 指定范围,--force-agents 显式 opt-in。"""
    p = _make_project(tmp_path, with_user_agents=True)
    assert _run_cli("install", "--target", str(p), "--host", "cursor") == 0
    # 显式 --host codex → 落地 AGENTS.md(marker 追加需 --force-agents)
    assert _run_cli("upgrade", "--target", str(p), "--host", "codex", "--force-agents") == 0
    text = (p / "AGENTS.md").read_text(encoding="utf-8")
    assert text.startswith("# 我的项目规则") and MARKER_BEGIN in text
    stamp = json.loads((p / ".drogon-plugin-install.json").read_text(encoding="utf-8"))
    assert sorted(stamp["hosts"]) == ["codex", "cursor"]


def test_upgrade_without_stamp_falls_back_to_full_install(tmp_path):
    """无安装戳(手工删过 / 全新项目)→ upgrade 等价全量 install,保持向后兼容。"""
    p = _make_project(tmp_path)
    assert _run_cli("upgrade", "--target", str(p)) == 0
    assert (p / "GEMINI.md").is_file() and (p / ".cursor").is_dir()


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
