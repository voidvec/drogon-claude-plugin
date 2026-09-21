#!/usr/bin/env python3
"""宿主产物生成器 — 从单一事实源生成各 coding agent 宿主的接入产物.

事实源:skills/(22 技能)+ CLAUDE.md(规则层)+ VERSION(版本单一来源)。

生成(仓库内、随 git 提交):
  AGENTS.md                        通用规则文件(CLAUDE.md 去宿主专有内容)
  GEMINI.md                        Gemini CLI 扩展上下文(内容同 AGENTS.md)
  gemini-extension.json            Gemini CLI 扩展清单(skills/ 自动发现)
  .codex-plugin/plugin.json        Codex 插件清单
  .agents/plugins/marketplace.json Codex 原生 marketplace(policy 三件套必填)

版本同步(改写既有文件的 version 字段):
  .claude-plugin/plugin.json / .zcode-plugin/plugin.json /
  .claude-plugin/marketplace.json / pyproject.toml / npm/package.json /
  src/drogon_plugin/__init__.py(__version__ 与 PLUGIN_VERSION)

用法:
  python scripts/gen-host-artifacts.py           生成/同步
  python scripts/gen-host-artifacts.py --check   只校验是否最新(CI 用)

注意:.agents/ 只服务 Codex 对本仓库的发现,**不进入** sync-assets 发行资产
(不能被 CLI 装进用户项目)。
"""
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
VERSION_FILE = REPO / "VERSION"

REPO_URL = "https://github.com/voidvec/drogon-claude-plugin"
DESCRIPTION = (
    "Drogon C++ 后端开发规则与技能: 基于 Drogon 框架编写正确的异步代码, "
    "避开回调/事件循环等高频陷阱。适用于 Claude Code、ZCode、Codex、Cursor、"
    "VS Code (Copilot)、Gemini CLI 等 coding agent。"
)
DESCRIPTION_EN = (
    "Drogon C++ backend rules & skills: correct async code, avoiding "
    "callback / event-loop pitfalls. Works with Claude Code, ZCode, Codex, "
    "Cursor, VS Code (Copilot), Gemini CLI and any AGENTS.md-compatible agent."
)
KEYWORDS = ["drogon", "cpp", "c++", "web-framework", "async", "http-server", "orm", "backend"]

GENERATED_HEADER_NOTE = (
    "> 本文件由 drogon-claude-plugin v{v} 自动生成,请勿手改(源:CLAUDE.md;"
    "重新生成:python scripts/gen-host-artifacts.py)。适用于任何读取 AGENTS.md "
    "的 coding agent。"
)


def read_version() -> str:
    return VERSION_FILE.read_text(encoding="utf-8").strip()


# ---------------------------------------------------------------------------
# AGENTS.md / GEMINI.md:CLAUDE.md → 宿主中立规则文件
# ---------------------------------------------------------------------------


def build_agents_md(claude_md: str, version: str) -> str:
    """CLAUDE.md 去宿主专有内容:剥离标题与引言块、剥离「安装 / 升级」节。"""
    # 1) 去掉尾部宿主专有的安装/升级章节
    body = claude_md.split("\n## 安装 / 升级\n")[0].rstrip()
    # 2) 剥离原标题行与其后的 blockquote 引言
    lines = body.split("\n")
    i = 1 if lines and lines[0].startswith("# ") else 0
    while i < len(lines) and (lines[i].startswith(">") or lines[i].strip() == ""):
        i += 1
    content = "\n".join(lines[i:]).lstrip("\n")

    header = "# Drogon 后端开发规则\n\n"
    note = GENERATED_HEADER_NOTE.format(v=version) + "\n"
    skills_note = (
        ">\n> 下文的 Skill 路由表指向随插件分发的 22 个技能"
        "(Claude Code / ZCode / Codex / Cursor / VS Code / Gemini CLI 经各自机制安装后可用)。"
        "若当前环境只落了规则文件,路由表仍可作为 drogon 领域地图使用。\n"
    )
    return header + note + skills_note + "\n" + content + "\n"


# ---------------------------------------------------------------------------
# JSON 产物
# ---------------------------------------------------------------------------


def build_codex_plugin_json(version: str) -> str:
    data = {
        "name": "drogon",
        "version": version,
        "description": DESCRIPTION,
        "author": {"name": "voidvec"},
        "homepage": REPO_URL + "#readme",
        "repository": REPO_URL,
        "license": "MIT",
        "keywords": KEYWORDS,
        "skills": "./skills/",
        # hooks 位于默认路径 hooks/hooks.json,Codex 会自动发现;显式声明以自文档化
        "hooks": "./hooks/hooks.json",
        "interface": {
            "displayName": "Drogon C++ Backend",
            "shortDescription": "Drogon C++ 后端开发规则与技能(异步回调/事件循环纪律 + 22 个代码生成技能)",
            "category": "Software development",
        },
    }
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def build_codex_marketplace_json(version: str) -> str:
    data = {
        "name": "drogon-claude-plugin",
        "interface": {"displayName": "drogon-claude-plugin"},
        "plugins": [
            {
                "name": "drogon",
                # 本仓库即插件根(skills/ hooks/ .codex-plugin/ 都在根)
                "source": {"source": "local", "path": "./"},
                # Codex marketplace 条目必填三件套(developers.openai.com/codex/plugins/build)
                "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
                "category": "Software development",
                "version": version,
                "description": DESCRIPTION,
            }
        ],
    }
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def build_gemini_extension_json(version: str) -> str:
    data = {
        "name": "drogon",
        "version": version,
        "description": DESCRIPTION_EN,
        # Gemini CLI:启用 skills/ 自动发现 + GEMINI.md 每会话上下文注入
        "contextFileName": "GEMINI.md",
    }
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


# ---------------------------------------------------------------------------
# 既有文件版本同步
# ---------------------------------------------------------------------------

SYNC_RULES = (
    # (path, kind)  kind: json-field | py-assign | toml-version
    (".claude-plugin/plugin.json", "json-field:version"),
    (".zcode-plugin/plugin.json", "json-field:version"),
    (".claude-plugin/marketplace.json", "json-field:plugins[0].version"),
    ("pyproject.toml", "toml-version"),
    ("npm/package.json", "json-field:version"),
    ("src/drogon_plugin/__init__.py", "py-assign:__version__"),
    ("src/drogon_plugin/__init__.py", "py-assign:PLUGIN_VERSION"),
)


def _sync_json_field(text: str, field: str, version: str) -> str:
    if field == "version":
        return re.sub(
            r'("version"\s*:\s*")[^"]+(")', r"\g<1>" + version + r"\g<2>", text, count=1
        )
    if field == "plugins[0].version":
        return re.sub(
            r'("plugins"\s*:\s*\[[\s\S]*?"version"\s*:\s*")[^"]+(")',
            r"\g<1>" + version + r"\g<2>",
            text,
            count=1,
        )
    raise ValueError(field)


def sync_file(path: Path, kind: str, version: str) -> bool:
    """按规则改写文件中的版本;返回是否有变化。"""
    text = path.read_text(encoding="utf-8")
    new = text
    if kind.startswith("json-field:"):
        new = _sync_json_field(text, kind.split(":", 1)[1], version)
    elif kind == "toml-version":
        new = re.sub(
            r'(^version\s*=\s*")[^"]+(")', r"\g<1>" + version + r"\g<2>", text, count=1, flags=re.M
        )
    elif kind.startswith("py-assign:"):
        name = kind.split(":", 1)[1]
        new = re.sub(
            rf'(^{name}\s*=\s*")[^"]+(")', r"\g<1>" + version + r"\g<2>", text, count=1, flags=re.M
        )
    else:
        raise ValueError(kind)
    if new != text:
        path.write_text(new, encoding="utf-8")
        return True
    return False


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------


def generate(version: str) -> list:
    written = []
    claude_md = (REPO / "CLAUDE.md").read_text(encoding="utf-8")
    agents_md = build_agents_md(claude_md, version)

    outputs = {
        "AGENTS.md": agents_md,
        "GEMINI.md": agents_md,
        "gemini-extension.json": build_gemini_extension_json(version),
        ".codex-plugin/plugin.json": build_codex_plugin_json(version),
        ".agents/plugins/marketplace.json": build_codex_marketplace_json(version),
    }
    for rel, content in outputs.items():
        p = REPO / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        old = p.read_text(encoding="utf-8") if p.is_file() else None
        if old != content:
            p.write_text(content, encoding="utf-8")
            written.append(rel)

    for rel, kind in SYNC_RULES:
        if sync_file(REPO / rel, kind, version):
            written.append(rel)
    return written


def check(version: str) -> list:
    """返回不一致项列表(空 = 全部最新)。"""
    problems = []
    claude_md = (REPO / "CLAUDE.md").read_text(encoding="utf-8")
    expect = {
        "AGENTS.md": build_agents_md(claude_md, version),
        "GEMINI.md": build_agents_md(claude_md, version),
        "gemini-extension.json": build_gemini_extension_json(version),
        ".codex-plugin/plugin.json": build_codex_plugin_json(version),
        ".agents/plugins/marketplace.json": build_codex_marketplace_json(version),
    }
    for rel, content in expect.items():
        p = REPO / rel
        if not p.is_file():
            problems.append(f"缺失 {rel}")
        elif p.read_text(encoding="utf-8") != content:
            problems.append(f"{rel} 与事实源不一致")

    for rel, kind in SYNC_RULES:
        text = (REPO / rel).read_text(encoding="utf-8")
        if kind == "json-field:version":
            m = re.search(r'"version"\s*:\s*"([^"]+)"', text)
        elif kind == "json-field:plugins[0].version":
            m = re.search(r'"plugins"\s*:\s*\[[\s\S]*?"version"\s*:\s*"([^"]+)"', text)
        elif kind == "toml-version":
            m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.M)
        else:
            name = kind.split(":", 1)[1]
            m = re.search(rf'^{name}\s*=\s*"([^"]+)"', text, re.M)
        if not m or m.group(1) != version:
            problems.append(f"{rel} 版本 != {version}")
    return problems


def _utf8_stdio() -> None:
    # Windows 下 stdout 为管道时默认 cp1252,print ✅/中文 会抛 UnicodeEncodeError
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass


def main() -> int:
    _utf8_stdio()
    version = read_version()
    if "--check" in sys.argv:
        problems = check(version)
        if problems:
            print("❌ 宿主产物不一致:")
            for p in problems:
                print("  -", p)
            return 1
        print(f"✅ 宿主产物与事实源一致(版本 {version})")
        return 0
    written = generate(version)
    print(f"✅ 生成完成(版本 {version}):{', '.join(written) if written else '无变化'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
