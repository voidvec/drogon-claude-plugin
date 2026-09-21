# drogon-claude-plugin

> CLI installer for the **Drogon C++ backend coding-agent plugin** (Claude Code & ZCode) — one command drops 22 code-generation skills, 2 automatic detection hooks, and top-level development discipline into your project.

**English** | [简体中文](README.zh-CN.md)

[![npm version](https://img.shields.io/npm/v/drogon-claude-plugin.svg)](https://www.npmjs.com/package/drogon-claude-plugin)
[![CI](https://github.com/voidvec/drogon-claude-plugin/actions/workflows/ci.yml/badge.svg)](https://github.com/voidvec/drogon-claude-plugin/actions/workflows/ci.yml)

The plugin helps [Claude Code](https://docs.anthropic.com/en/docs/claude-code/plugins) and [ZCode](https://z.ai) write **correct asynchronous
code** for the [Drogon](https://github.com/drogonframework/drogon) C++ HTTP framework — avoiding classic callback /
event-loop pitfalls. Works on Windows / Linux / macOS.

## Install

```bash
# Global install (recommended)
npm install -g drogon-claude-plugin

# Or run on the fly — no installation needed
npx drogon-claude-plugin install
```

## Usage

```bash
# Copy the plugin assets into <project>/.drogon-plugin/ (your own files are never touched)
drogon-claude-plugin install

# Validate the installed structure (skill count / hooks / manifests / version consistency)
drogon-claude-plugin verify

# Remove the installed assets (ownership-checked; never touches your code)
drogon-claude-plugin uninstall
```

> **v0.3.0 note**: the npm CLI covers Claude Code / ZCode bundle installation. Multi-host installation
> (`--host codex|cursor|copilot|gemini|qoder|codebuddy|trae|agents`) and `scan` are provided by the
> **PyPI CLI** (`pipx install drogon-claude-plugin`) — the reference implementation. Host-native
> installs (Codex marketplace, Gemini extensions) work directly from this repository without any CLI.

Enable the plugin through your host's official mechanism (the CLI prints these hints too):

```bash
# Claude Code — either register the local copy:
claude plugin install .drogon-plugin --scope project
# or use the marketplace flow:
claude plugin marketplace add https://github.com/voidvec/drogon-claude-plugin
claude plugin install drogon
```

For **ZCode**, add the marketplace `https://github.com/voidvec/drogon-claude-plugin` in ZCode's plugin manager and install the `drogon` plugin.

## What's in the box

This package bundles the complete plugin assets (`assets/`): `skills/` (22 skills) + `hooks/` (SessionStart +
PostToolUse, cross-platform launcher) + `CLAUDE.md` + `.claude-plugin/` / `.zcode-plugin/` manifests, always kept in sync with the GitHub repository.

## License

MIT — full plugin documentation lives in the [GitHub repository](https://github.com/voidvec/drogon-claude-plugin).
