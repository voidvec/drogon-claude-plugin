# Release — drogon-claude-plugin

## What's new

本版本收口第四轮正确性评审（批次①–④），完整清单见仓库 `CHANGELOG.md` 的对应小节。

- **钩子扫描去 ReDoS**：`posttooluse` 的两条内容类正则此前对病态 C++ 文件呈 O(n²)（实测 280KB 文件 42s、100KB 连排花括号 62s，每次 Edit 都会被卡住），现已上界化并配 1s 预算守卫。
- **安装/升级事务化**：改名备份成功才销毁旧状态，回滚失败不再毁在用 bundle、备份或用户技能内容；崩溃留下的 `*.old-<pid>` 由下次 install 主动回收，`verify` 只提示不删。
- **npm ↔ PyPI 互操作收敛**：`uninstall` 判定前置（混合宿主不动 bundle）、`upgrade` 认 v2 bundle 布局不再凭空落 8 家产物、非 UTF-8 用户文件按"读不动=不碰"处理。
- **verify 逐技能对账**：按安装戳逐项核对宿主产物，缺 `SKILL.md` 的空壳技能目录与共享 `AGENTS.md` 造成的假阳性不再整体放行；POSIX 下钩子入口显式补执行位。
- **CI 供应链守卫**：workflow 全部 action 按 commit SHA 固定，并由 `scripts/check-action-pinning.py` 联网核实 SHA 与行尾注释版本互相吻合（取不回 refs 即 fail-closed）。
- **跨产物一致性门禁扩到 15 项**：双语 README 与宿主矩阵对拍、两个 CLI 的能力契约、两份资产同步器常量等价、CHANGELOG 归档校验等，漂移即红。
- **宿主覆盖**：Qoder（`.qoder/skills`）与 CodeBuddy（`.codebuddy/skills`）技能目录落地，中英 README 同步标注。

## Assets

### PyPI — `drogon-claude-plugin`

```bash
pipx install drogon-claude-plugin   # 或 pip install
drogon-claude-plugin install
```

依赖内置资产（22 个技能 + 2 hooks + CLAUDE.md）。

### npm — `drogon-claude-plugin`

```bash
npx drogon-claude-plugin install
# 或全局: npm i -g drogon-claude-plugin && drogon-claude-plugin install
```

### Claude Code marketplace

```bash
claude plugin marketplace add https://github.com/voidvec/drogon-claude-plugin
claude plugin install drogon
```

## Checksums

- `dist/drogon_claude_plugin-*.whl` / `.tar.gz`（本 Release 附件）
- npm tarball 请见 npmjs.com 的 integrity 字段
