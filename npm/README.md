# drogon-claude-plugin

> CLI installer for the **Drogon C++ backend Claude Code plugin** — one command drops 17 code-generation skills, 2 automatic detection hooks, and top-level development discipline into your project.

**English** | [简体中文](README.zh-CN.md)

[![npm version](https://img.shields.io/npm/v/drogon-claude-plugin.svg)](https://www.npmjs.com/package/drogon-claude-plugin)
[![CI](https://github.com/voidvec/drogon-claude-plugin/actions/workflows/ci.yml/badge.svg)](https://github.com/voidvec/drogon-claude-plugin/actions/workflows/ci.yml)

The plugin helps [Claude Code](https://docs.anthropic.com/en/docs/claude-code/plugins) write **correct asynchronous
code** for the [Drogon](https://github.com/drogonframework/drogon) C++ HTTP framework — avoiding classic callback /
event-loop pitfalls.

## Install

```bash
# Global install (recommended)
npm install -g drogon-claude-plugin

# Or run on the fly — no installation needed
npx drogon-claude-plugin install
```

## Usage

```bash
# Copy the plugin assets into the current project and prompt to enable
drogon-claude-plugin install

# Validate the installed structure (skill count / hooks / manifests)
drogon-claude-plugin verify

# Remove the installed assets (never touches your code)
drogon-claude-plugin uninstall
```

Enable the plugin through the official Claude Code mechanism:

```bash
claude plugin marketplace add https://github.com/voidvec/drogon-claude-plugin
claude plugin install drogon
```

## What's in the box

This package bundles the complete plugin assets (`assets/`): `skills/` (17 skills) + `hooks/` (SessionStart +
PostToolUse) + `CLAUDE.md` + `.claude-plugin/` manifests, always kept in sync with the GitHub repository.

## License

MIT — full plugin documentation lives in the [GitHub repository](https://github.com/voidvec/drogon-claude-plugin).