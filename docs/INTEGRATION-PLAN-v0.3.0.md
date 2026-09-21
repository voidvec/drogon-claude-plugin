# 多宿主接入方案 v0.3.0 — 主流 Coding Agent 工具全覆盖(评审修订版)

> 日期:2026-09-21。初版经对抗性评审修订,评审记录见 `docs/INTEGRATION-REVIEW-v0.3.0.md`。
> 事实基础:Codex/Gemini/Cursor 官方文档已实读(评审记录 §0);插件资产(22 技能 + 规则层)为 [Agent Skills 开放标准](https://agentskills.io)原生格式。
> **版本拆分(评审 #19)**:v0.3.0 = Codex + Cursor + VS Code/Copilot + 通用兜底;v0.4.0 = Gemini + Qoder + CodeBuddy + Trae。

---

## 1. 目标工具与分批

| 批次 | 宿主 | 机制(官方文档核实) | 规则注入 | 钩子 |
|------|------|--------------------|---------|------|
| ✅ 已发布 | Claude Code | `.claude-plugin/` + marketplace | SessionStart hook | ✅ |
| ✅ 已发布 | ZCode | `.zcode-plugin/` + marketplace | SessionStart hook | ✅ |
| **v0.3.0** | Codex CLI | `.codex-plugin/plugin.json` + **双 marketplace**(`.agents/plugins/marketplace.json` 原生格式,policy 三件套必填;`.claude-plugin/` legacy 兼容由 Codex 自行处理) | AGENTS.md(项目级,见 §3.1 非破坏策略) | ✅ hooks/hooks.json 同布局,**需用户 trust** |
| **v0.3.0** | Cursor | `.cursor/skills/` 放 SKILL.md | .cursor/rules(MDC) | ⚠️ 事件模型待实测,v0.3 不做 |
| **v0.3.0** | Copilot (VS Code) | `.agents/skills` 开放标准(VS Code 原生识别) | AGENTS.md | ⚠️ 有限 |
| **v0.3.0** | 通用兜底 | `.agents/skills` + AGENTS.md | AGENTS.md | ❌(scan 命令替代) |
| **v0.4.0** | Gemini CLI | `gemini-extension.json`(name/version/description/contextFileName)+ `skills/` **自动发现** + `GEMINI.md` 每会话注入;`gemini extensions install <git-url>` | GEMINI.md(原生 contextFileName) | 部分 |
| **v0.4.0** | Qoder(阿里) | AGENTS.md 官方兼容 | AGENTS.md | ❌ |
| **v0.4.0** | CodeBuddy(腾讯) | `CODEBUDDY.md` 项目指令 | CODEBUDDY.md | ⚠️ |
| **v0.4.0** | Trae(字节) | `.trae/rules/` | .trae/rules | ❌ |

**维护分层承诺(评审 #12)**:一级维护 = Claude/ZCode/Codex/Cursor/VS Code+兜底;尽力维护 = Gemini/Qoder/CodeBuddy/Trae。README 明示。

## 2. 架构原则(评审修订后)

1. **单一事实源 + 版本单一来源**:`skills/` 与 `CLAUDE.md` 手工维护;**所有宿主清单的 version 由生成器从单一 VERSION 常量派生**(评审 #5)——publish.yml 断言改为「全部清单版本一致」。
2. **规则层派生链**:CLAUDE.md →(去宿主专有措辞)→ AGENTS.md →(改名)GEMINI.md / CODEBUDDY.md 等。生成物首行注明来源,禁止手改。
3. **AGENTS.md 非破坏策略(评审 #6,必改)**:
   - 目标文件不存在 → 落盘完整文件;
   - 已存在 → **默认跳过并打印合并指引**;仅 `--force-agents` 允许追加 `<!-- drogon-plugin begin/end -->` 标记段;
   - uninstall 只删标记段,绝不动用户自有内容。
4. **落盘互斥(评审 #7)**:`--host all` 时,凡宿主有专有清单(Claude/ZCode/Codex/Gemini/Cursor)则**不落** `.agents/skills`,避免同名技能重复发现;`.agents/skills` 仅服务无专有机制的宿主(`--host agents`)。
5. **scan 替代无钩子宿主的兜底(评审 #11,必改)**:`drogon-claude-plugin scan [--path ...]` 输入为**文件路径列表/glob**(复用 posttooluse.py 抽出的共享扫描模块,非 hook 负载);限制在 `--root`(默认 cwd)之内,拒绝路径逃逸(评审 #15);输出 human / `--format json`。

## 3. 工作分解

### Phase A — 资产层

| # | 任务 | 要点 |
|---|------|------|
| A1 | 生成器 `scripts/gen-host-artifacts.{py,mjs}`:VERSION 单一来源 → 各宿主清单/规则文件 | AGENTS.md、`.codex-plugin/plugin.json`、`.agents/plugins/marketplace.json`(policy 三件套 + interface 块)、`.cursor/` 结构、(v0.4)gemini-extension.json + GEMINI.md、CODEBUDDY.md、`.trae/rules/drogon.md` |
| A2 | Codex 双 marketplace 落地 + 本机真安装验证(`codex plugin marketplace add <本地路径>`) | 记录 legacy `.claude-plugin/marketplace.json` 在 Codex 的实际兼容度(评审待实测项) |
| A3 | sync-assets 扩展:发行包含全部生成宿主产物;`--check` 校验 | CI 断言「所有清单 version 一致」 |

### Phase B — CLI 安装器 v3(PyPI + npm)

| # | 任务 |
|---|------|
| B1 | `install --host <claude\|zcode\|codex\|cursor\|copilot\|agents\|gemini\|qoder\|codebuddy\|trae\|all>`(v0.3 实现 v0.3 批;v0.4 扩展),all 按 §2.4 互斥落盘 |
| B2 | AGENTS.md 非破坏写入(§2.3);各宿主落点;uninstall 对应清理(标记段/整文件按归属) |
| B3 | `scan` 子命令:共享扫描模块 + 路径边界 + human/json 输出 |
| B4 | 安装提示按宿主精确化:Codex 打印 `codex plugin marketplace add` + **trust 提醒**(评审 #14);Gemini 打印 `gemini extensions install` |
| B5 | 双实现(python/node)一致性测试 |

### Phase C — 接入验证(两级验收,评审 #16)

| 级别 | 内容 | 方式 |
|------|------|------|
| 结构性(自动化,进 CI,仅 ubuntu,评审 #13) | install 后各宿主落点/清单/技能数断言;生成物与源一致;scan 对 fixture 的输出契约 | pytest |
| 行为性(手动,一次性,记录进评审文档) | 每宿主真安装一次(`codex plugin marketplace add` / `gemini extensions install` / VS Code 打开项目 / Cursor 打开项目);新会话问「给 /api/users 写控制器」,确认响应体现路由纪律;记录技能列表上下文增量(评审 #10) | 人工清单,结果记入 INTEGRATION-REVIEW |

### Phase D — 质量与发布

- 测试:per-host 落点/清理/AGENTS.md 三态(不存在/存在/force)测试、scan 契约测试、清单版本一致性测试
- CI:三平台跑宿主无关测试;ubuntu 追加 per-host 套件
- 文档:README 宿主矩阵 + 分层维护承诺 + 各宿主安装段落(含 Codex trust 步骤);CHANGELOG
- 版本:0.3.0(四宿主+兜底)→ 0.4.0(Gemini+国内三家)

## 4. 风险与未决(评审后收敛)

| 风险 | 状态 |
|------|------|
| Cursor hooks 事件模型与 Claude 不同 | v0.3 不做 hooks,实测后作为 0.3.x 增量 |
| `.agents/skills` 与专有目录重复发现 | 已用互斥策略规避;实测项保留 |
| Codex legacy marketplace 兼容度 | A2 实测;原生清单为主要路径,legacy 仅加分项 |
| 各宿主 SKILL.md frontmatter 兼容(`version:` 键) | C 阶段逐宿主实测;生成器预留 per-host 裁剪能力 |
| 22 技能上下文增量 | 行为性验收记录;超预期则考虑按宿主裁剪技能集 |
| Gemini 免费 CLI 被 Antigravity 替代的受众问题 | 已降入 v0.4.0 第二批 |

## 5. 排期(修订)

1. Phase A + B 核心(生成器/安装器/scan/AGENTS.md 策略)— ~2 天
2. v0.3 宿主验证(Codex/Cursor/VS Code 结构性+行为性)— ~1 天
3. Phase D(v0.3.0 发布)— ~0.5 天
4. v0.4.0(Gemini + 国内三家,纯生成器产物 + 真机验证)— ~1 天
