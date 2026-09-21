# drogon-claude-plugin

> **Drogon C++ 后端开发 coding agent 插件**（Claude Code 与 ZCode 双宿主）安装器 —— 一条命令把 22 个代码生成技能、2 个自动化检测钩子与顶层开发纪律装进你的项目。

简体中文 | [English](README.md)

[![npm version](https://img.shields.io/npm/v/drogon-claude-plugin.svg)](https://www.npmjs.com/package/drogon-claude-plugin)
[![CI](https://github.com/voidvec/drogon-claude-plugin/actions/workflows/ci.yml/badge.svg)](https://github.com/voidvec/drogon-claude-plugin/actions/workflows/ci.yml)

该插件帮助 [Claude Code](https://docs.anthropic.com/en/docs/claude-code/plugins) 与 [ZCode](https://z.ai) 为 [Drogon](https://github.com/drogonframework/drogon) C++ HTTP 框架编写**正确的异步代码**，避开回调 / 事件循环等高频陷阱。Windows / Linux / macOS 全平台可用。

## 安装

```bash
# 全局安装（推荐）
npm install -g drogon-claude-plugin

# 或免安装直跑
npx drogon-claude-plugin install
```

## 使用

```bash
# 把插件资产装入 <项目>/.drogon-plugin/（绝不触碰项目自有文件）
drogon-claude-plugin install

# 校验已安装插件结构（技能数 / 钩子 / 清单 / 版本一致性）
drogon-claude-plugin verify

# 升级到随包版本（自动迁移 v0.1.x 根目录布局）
drogon-claude-plugin upgrade

# 卸载（逐项归属校验，绝不误删你的业务代码）
drogon-claude-plugin uninstall
```

通过宿主官方机制启用插件（CLI 也会打印这些提示）：

```bash
# Claude Code —— 注册本地副本：
claude plugin install .drogon-plugin --scope project
# 或走 marketplace：
claude plugin marketplace add https://github.com/voidvec/drogon-claude-plugin
claude plugin install drogon
```

**ZCode**：在插件管理中添加 marketplace `https://github.com/voidvec/drogon-claude-plugin`，安装 `drogon` 插件。

## 包内含什么

本包内置完整插件资产（`assets/`）：`skills/`（22 个技能）+ `hooks/`（SessionStart + PostToolUse，跨平台启动器）+ `CLAUDE.md` + `.claude-plugin/` / `.zcode-plugin/` 清单，与 GitHub 仓库保持同步。

## 许可

MIT — 完整插件说明见 [GitHub 仓库](https://github.com/voidvec/drogon-claude-plugin)。
