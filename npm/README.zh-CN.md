# drogon-claude-plugin

> **Drogon C++ 后端开发的 Claude Code 插件** 安装器 —— 一条命令把 17 个代码生成技能、2 个自动化检测钩子与顶层开发纪律装进你的项目。

简体中文 | [English](README.md)

[![npm version](https://img.shields.io/npm/v/drogon-claude-plugin.svg)](https://www.npmjs.com/package/drogon-claude-plugin)
[![CI](https://github.com/voidvec/drogon-claude-plugin/actions/workflows/ci.yml/badge.svg)](https://github.com/voidvec/drogon-claude-plugin/actions/workflows/ci.yml)

该插件帮助 [Claude Code](https://docs.anthropic.com/en/docs/claude-code/plugins) 为 [Drogon](https://github.com/drogonframework/drogon) C++ HTTP 框架编写**正确的异步代码**，避开回调 / 事件循环等高频陷阱。

## 安装

```bash
# 全局安装（推荐）
npm install -g drogon-claude-plugin

# 或免安装直跑
npx drogon-claude-plugin install
```

## 使用

```bash
# 把插件资产拷贝到当前项目并提示启用
drogon-claude-plugin install

# 校验已安装插件结构（技能数 / 钩子 / 清单）
drogon-claude-plugin verify

# 卸载（绝不触碰你的业务代码）
drogon-claude-plugin uninstall
```

启用插件（Claude Code marketplace 官方机制）：

```bash
claude plugin marketplace add https://github.com/voidvec/drogon-claude-plugin
claude plugin install drogon
```

## 包内含什么

本包内置完整插件资产（`assets/`）：`skills/`（17 个技能）+ `hooks/`（SessionStart + PostToolUse）+ `CLAUDE.md` + `.claude-plugin/` manifest，与 GitHub 仓库保持同步。

## 许可

MIT — 完整插件说明见 [GitHub 仓库](https://github.com/voidvec/drogon-claude-plugin)。