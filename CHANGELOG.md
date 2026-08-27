# Changelog

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 与 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

发布流程：**更新本文件 → 同步三处版本号（`plugin.json` / `__init__.py` / `npm/package.json`）→ 打 tag `vX.Y.Z`**，CI 自动发布 PyPI + npm + GitHub Release。

## [Unreleased]

### Added
- PyPI 发行包（`drogon-claude-plugin`，CLI 命令 `drogon-plugin`）：`install` / `verify` / `uninstall` / `version`
- npm 发行包（`drogon-claude-plugin`，bin 名 `drogon-plugin`）：与 PyPI 同构的 CLI
- 插件资产（skills / hooks / CLAUDE.md / .claude-plugin）双端打包进发行包，实现一条命令安装
- GitHub Actions 流水线：`ci.yml`（结构校验 + 双端 CLI 冒烟测试）、`publish.yml`（tag 触发 → PyPI + npm + Release）
- 仓库基建：`.gitignore`、`CONTRIBUTING.md`、`CHANGELOG.md`

### Changed

- 仓库品牌统一为 `voidvec/drogon-claude-plugin`（README / plugin.json / marketplace.json 同步）

## [0.3.0] - 2026-07-03

首次公开发布。

- 17 个 drogon 开发技能（控制器 / ORM / 协程 / 中间件 / 插件 / 测试等）
- 精简路由 CLAUDE.md：顶层纪律 + Skill 路由表，详细知识下沉到各 skill 的 `references/code-guide.md`
- PostToolUse 钩子：编辑后自动扫描 drogon API 违规并告警

[Unreleased]: https://github.com/voidvec/drogon-claude-plugin/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/voidvec/drogon-claude-plugin/releases/tag/v0.3.0