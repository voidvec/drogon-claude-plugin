# 贡献指南

感谢你对 drogon-claude-plugin 的关注！

## 项目结构

- `CLAUDE.md` — 插件注入的顶层规则（精简路由，不放置详细知识）
- `skills/<name>/` — 每个技能目录含 `SKILL.md`（frontmatter + 触发说明）与 `references/code-guide.md`（详细模板/API 速查）
- `hooks/` — `hooks.json`（hook 注册）+ `posttooluse.py`（Drogon API 违规检测）
- `src/drogon_plugin/` — PyPI CLI 安装器源码
- `npm/` — npm CLI 安装器源码

## 开发约定

- **知识下沉**：顶层规则只写跨任务的纪律 + Skill 路由表；具体模板、API、禁止模式一律放在技能的 `references/code-guide.md`
- **钩子规则明确区分大小写**：C++ 标识符（`done()`、`createDbClient`）必须大小写敏感，避免 `isDone()` 误报；纯文本/CSP 标签可用 `re.IGNORECASE`
- **双向引用**：CLAUDE.md 顶层纪律与 Skill 文档互相引用，改动一侧需同步修订另一侧
- 插件版本在 `.claude-plugin/plugin.json`、PyPI `src/drogon_plugin/__init__.py`、npm `npm/package.json` 三处同步更新

## 技能新增流程

1. 在 `skills/` 下创建 `<drogon-xxx>/SKILL.md`（YAML frontmatter：name / description / 触发词）
2. 补充 `<drogon-xxx>/references/code-guide.md`（详尽的模板 / API 签名 / 禁止模式）
3. 在 `CLAUDE.md` 的 Skill 路由表登记一行
4. 在 `README.md` 技能表格登记一行
5. 若涉及新检测，同步扩充 `hooks/posttooluse.py` 并补充验证用例

## 提交信息

采用 Conventional Commits：`feat:` / `fix:` / `refactor:` / `docs:` / `chore:`。

## 发布

版本变更走 Git tag（如 `v0.4.0`），GitHub Actions 自动发布到 PyPI、npm 并生成 GitHub Release。tag 前先更新 CHANGELOG.md 与三处版本号。

## 本地验证

```bash
# 插件结构校验（CI 同款）
drogon-plugin verify        # 或 npm 包: npx drogon-claude-plugin verify

# 冒烟测试
python scripts/dev-smoke-test.py
```