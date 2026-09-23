# 贡献指南

感谢你对 drogon-claude-plugin 的关注！

## 项目结构

- `CLAUDE.md` — 插件注入的顶层规则（精简路由，不放置详细知识）。`AGENTS.md` / `GEMINI.md` 由生成器从它派生，**禁止手改**
- `skills/<name>/` — 每个技能目录含 `SKILL.md`（frontmatter + 触发说明）与 `references/code-guide.md`（详细模板 / API 速查 / 禁止模式清单）
- `hooks/` — `hooks.json`（hook 注册）+ `posttooluse.py`（Drogon API 违规检测，规则带稳定 `rule_id`）
- `src/drogon_plugin/` — PyPI CLI 安装器源码（**参考实现**）
- `npm/` — npm CLI 安装器源码
- `scripts/` — 宿主产物生成器（`gen-host-artifacts.py`）、资产同步（`sync-assets.{py,mjs}`）、跨产物一致性门禁（`check-consistency.py`）、冒烟脚本
- `tests/` — pytest 套件（结构 / 钩子规则正反例 / 多宿主 / 端到端）
- `src/drogon_plugin/` 与 `npm/` 的资产由 `scripts/sync-assets.*` 生成，**不要手改生成目录**
- **[`docs/SKILL-AUTHORING.md`](docs/SKILL-AUTHORING.md) — 技能作者手册（新增 / 修改技能前必读）**
- [`docs/PROFESSIONALIZATION-REVIEW.md`](docs/PROFESSIONALIZATION-REVIEW.md) — 仓库专业化体检报告与改进清单
- [`docs/SPEC-CORRECTNESS-COMPAT-REVIEW.md`](docs/SPEC-CORRECTNESS-COMPAT-REVIEW.md) — 第二轮评审（规范符合性 / 功能正确性 / 多宿主兼容性），含**需真机核实清单**与**被反证、不予整改的推测项**

## 真机核实清单（无法静态定论，需人工验证）

以下行为依赖宿主实现细节，静态分析无法给定论，需按 `docs/INTEGRATION-PLAN-v0.3.0.md` Phase C 的"每宿主真安装一次"流程人工验证，并回填到
[`docs/SPEC-CORRECTNESS-COMPAT-REVIEW.md`](docs/SPEC-CORRECTNESS-COMPAT-REVIEW.md) §5：

- Codex 是否容忍 `hooks.json` 中的 `shell` 字段与 matcher 中的 `MultiEdit`（Claude 专有工具名）；
- Codex 的 `interface` 块是否需要更多字段（官方文档称"其余字段可选"，未给必填清单）；
- `.agents/plugins/marketplace.json` 的 `source.path: "./"` 在 Codex 缓存安装下的解析基准；
- ~~Trae 是否识别 `.mdc`~~ 已于第三轮评审证伪（官方规则为 `.trae/rules/*.md`），Trae 已改走 `.trae/skills` + `AGENTS.md`；Cursor 空值 `globs:` 的行为仍待真机。

第三轮新增待真机项（见 [`docs/ROUND3-SPEC-HOST-PLATFORM-CORRECTNESS-REVIEW.md`](docs/ROUND3-SPEC-HOST-PLATFORM-CORRECTNESS-REVIEW.md) §5）：V7 = pip 解包 wheel 后钩子脚本可执行位是否保留；V8 = Codex `additionalContext` token 上限下中文规则全文注入是否降级。

## 开发约定

- **知识下沉**：顶层规则只写跨任务的纪律 + Skill 路由表；具体模板、API、禁止模式一律放在技能的 `references/code-guide.md`
- **单一事实源**：技能数量由 `skills/` 目录**实枚举**派生，禁止在代码或文档里硬编码；版本唯一来源是 `VERSION` 文件
- **钩子规则区分大小写**：C++ 标识符（`done()`、`createDbClient`）必须大小写敏感，避免 `isDone()` 误报；纯文本/CSP 标签可用 `re.IGNORECASE`
- **每条钩子规则都要有正反例**：新增规则须在 `tests/test_posttooluse.py::RULE_FIXTURES` 同时补 1 个正例与 1 个反例（缺反例 = 误报无人守护）
- **双向引用**：`CLAUDE.md` 顶层纪律与 Skill 文档互相引用，改动一侧需同步修订另一侧
- **版本号不要手改**：改 `VERSION` 后跑生成器，它会同步全部清单（`.claude-plugin/plugin.json`、`.zcode-plugin/plugin.json`、`.claude-plugin/marketplace.json`、`pyproject.toml`、`npm/package.json`、`src/drogon_plugin/__init__.py` 的 `__version__` 与 `PLUGIN_VERSION`）
- **生成物不手改**：`AGENTS.md` / `GEMINI.md` / 各宿主清单 / 打包资产目录均属生成物，改事实源后重新生成

## 技能新增 / 修改

见 **[docs/SKILL-AUTHORING.md](docs/SKILL-AUTHORING.md)**：字段白名单、触发词写法、code-guide 结构契约、四处双向同步清单、可执行的步骤与校验命令。

## 提交信息

采用 Conventional Commits：`feat:` / `fix:` / `refactor:` / `docs:` / `chore:`。

## 发布

版本变更走 Git tag（如 `v0.4.0`），GitHub Actions 自动发布到 PyPI、npm 并生成 GitHub Release。

```bash
$EDITOR VERSION                            # 唯一版本来源
$EDITOR CHANGELOG.md                       # 按 Keep a Changelog 补条目
python scripts/gen-host-artifacts.py       # 同步全部清单版本
python scripts/gen-host-artifacts.py --check
git tag v0.4.0 && git push origin v0.4.0   # publish.yml 会断言 tag == VERSION
```

## 本地验证（与 CI 等价）

```bash
pip install -r requirements-dev.txt             # 固定版本的开发依赖（运行时依赖为零）

python scripts/gen-host-artifacts.py --check    # 生成物与事实源一致
python scripts/check-consistency.py             # 跨产物一致性门禁（技能清单/计数/版本/能力矩阵/双语 README）
python scripts/sync-assets.py                   # 生成随包资产（PyPI 侧）
python -m pytest tests/ -q                      # 全量测试套件

node scripts/sync-assets.mjs                    # 生成随包资产（npm 侧）
node scripts/sync-assets.mjs --check            # npm 侧一致性
node npm/bin/cli.js --capabilities              # CLI 能力声明（受门禁比对）
```

`drogon-claude-plugin verify --target <项目>` 可校验已安装产物的结构、版本与**资产漂移**（被改动/缺失/多余）。
