# 技能作者手册（SKILL-AUTHORING）

> 面向本仓库的维护者与贡献者。目标：**新增或修改一个技能时，不需要凭记忆同步任何东西**——所有约束都有对应的校验，改错会立刻被门禁拦住。
>
> 约束的事实来源：Agent Skills 规范 / Claude Code 技能文档（字段白名单、描述截断与上下文预算）、本仓库的 `tests/test_structure.py` 与 `scripts/check-consistency.py`。

---

## 1. 目录结构

每个技能是一个目录，名字必须与 `SKILL.md` 的 `name` 完全一致：

```
skills/
└── drogon-gen-xxx/
    ├── SKILL.md                    # 元数据 + 触发说明 + 索引（保持精简）
    └── references/
        └── code-guide.md           # 真正的知识：模板、API 速查、禁止模式清单
```

设计原则是**知识下沉**：`SKILL.md` 只写"什么时候用、要什么参数、产出什么、去哪看细节"；一切模板/API/禁止模式写进 `references/code-guide.md`，由模型按需加载，避免占用上下文。

**技能目录内不要放可执行脚本。** 当前 22 个技能全部是纯 Markdown（零可执行资产），这是安全性的重要前提（供应链扫描的结论）。

---

## 2. SKILL.md 规范

### 2.1 frontmatter 字段白名单（硬约束）

```yaml
---
name: drogon-gen-xxx
description: 需要……时，生成……
license: MIT
---
```

允许的键**仅**以下六个（由 `tests/test_structure.py::test_every_skill_has_skill_md_with_frontmatter` 强制）：

| 键 | 必需 | 说明 |
|----|------|------|
| `name` | 是 | 必须等于目录名 |
| `description` | 是 | 触发依据，见 §2.2 |
| `license` | 是 | 本仓库统一 `MIT` |
| `allowed-tools` | 否 | 一般不用 |
| `compatibility` | 否 | 环境要求（≤500 字符） |
| `metadata` | 否 | 自由键值，供自身工具读取 |

**为什么不能用 `version`**：Agent Skills 规范在打包/上传路径上只接受上述六个字段，出现其它键是**硬失败**（`Unexpected key(s) in SKILL.md frontmatter`），不是被忽略；而本仓库的技能同时经 `.agents/skills` 分发给 VS Code / 通用兜底宿主，因此必须落在这个交集内。技能随插件整体版本发布，**不需要**独立的版本号；确有每技能版本诉求时，写进 `metadata`（例如 `metadata: {version: 1}`）。

> 历史教训：v0.3.x 的 22 个 SKILL.md 都带着 `version`，没有任何测试引用它，结果漂移成 `0.1.0`（11 个）与 `0.2.0`（11 个）两套值，且无人察觉。

### 2.2 description：触发词优先

- 句式统一为 **「需要……时，…」**（由 `test_skill_description_is_trigger_first_and_within_cap` 强制）。
- 把**用户会说的场景词**放进去（如"文件上传"、"限流"、"WebSocket 广播"、"流式下载"），因为模型就是靠它决定要不要加载这个技能。
- 不要在 `description` 里堆 API 名当卖点；API 名放 `SKILL.md` 正文与 `code-guide.md`。
- 长度：与 `when_to_use`（本仓库不使用）合计在技能列表中**截断于 1536 字符**；另外技能列表整体有上下文预算（默认为模型上下文窗口的 1%）。因此**描述要短而准**，不要写成长段落。

### 2.3 正文结构（保持统一）

```
# <skill-name>

<一句话定位>

## 使用场景          # 什么时候该用它
## 输入参数          # 参数名 / 取值 / 默认值
## 输出              # 会产出哪些文件与代码
## 示例              # 可直接照抄的调用示例
## 参考文件          # 指向 references/code-guide.md，并说明该文件包含哪些章节
```

`## 参考文件` 里**声明了 code-guide 有哪些章节，就必须真的有**——门禁会校验（见 §3）。

---

## 3. code-guide.md 规范

必须满足下列结构契约（由 `test_every_skill_has_code_guide` 强制）：

| 约束 | 要求 |
|------|------|
| 行数 | ≥ 70 行（过薄说明知识没沉淀下来） |
| 模板 | 至少一个围栏代码块（```cpp / ```json / ```cmake …） |
| 章节标题 | 必须含 **`## 禁止模式清单`**（标题必须完全一致，不要写 "Forbidden patterns"、不要带 "5." 序号） |

`## 禁止模式清单` 是最高价值的章节：它把"AI 最容易写错、且错了不报错"的写法列出来（不存在的宏、同步阻塞、漏回调、错误键名、注入面……）。写这一节时遵循：

- 每条以 **禁止** 开头，紧跟"正确做法"或指向正确 API。
- 只写**真实存在**的陷阱；不要为了凑数写通用编程常识。
- 涉及源码行号时注明 drogon 版本（本仓库以 **v1.9.13** 源码为准；文档与源码冲突时以源码为准并在文档里指出差异）。

推荐章节骨架：

```
## 输入解析
## 参数验证
## 代码模板 / 配置模板
## 文件生成
## 关键 API / 字段速查
## 禁止模式清单      <-- 必需
## 错误处理
```

---

## 4. 四处双向同步清单

新增或重命名一个技能，需要同时改四处（门禁会校验前两处的完整性）：

| # | 位置 | 改什么 | 谁来校验 |
|---|------|--------|----------|
| 1 | `skills/<name>/` | 新建目录 + `SKILL.md` + `references/code-guide.md` | `tests/test_structure.py` |
| 2 | `CLAUDE.md` | 在 **Skill 路由表**登记一行（任务 / Skill / 说明） | `test_claude_md_routes_every_skill` |
| 3 | `README.md` | 在技能表格登记一行（英文） | `scripts/check-consistency.py` |
| 4 | `README.zh-CN.md` | 在技能表格登记一行（中文） | `scripts/check-consistency.py` |

**技能数量不需要在别处同步。** 数量一律由 `skills/` 目录实枚举派生：`AGENTS.md` / `GEMINI.md` / `.codex-plugin/plugin.json` 由生成器写入，CLI 与测试运行时枚举；README 里的数字由门禁校验（写错了 CI 会指出具体文件与原文）。

---

## 5. 新增技能：可执行步骤

```bash
# 1) 建目录与两个文件
mkdir -p skills/drogon-gen-xxx/references
$EDITOR skills/drogon-gen-xxx/SKILL.md
$EDITOR skills/drogon-gen-xxx/references/code-guide.md

# 2) 登记路由表与双语 README（共三处，见 §4）

# 3) 本地全量校验（等价于 CI 的 validate-plugin 作业）
python scripts/gen-host-artifacts.py --check
python scripts/check-consistency.py
python scripts/sync-assets.py
python -m pytest tests/ -q

# 4) 若要新增钩子规则，见 §6
```

`sync-assets.py` 会把技能同步进 PyPI 包的资产目录；npm 侧由 `npm pack` 的 `prepack` 自动完成。

---

## 6. 新增钩子规则

规则住在 `hooks/posttooluse.py`，每条是 `Rule`：

```python
Rule(
    "CPP.010",                 # rule_id：稳定编号，报告/测试/门禁都按它引用
    "error",                   # severity: "error" | "warning"
    r"\bBadApi\b",             # pattern：默认大小写敏感(flags=0)
    "一句话说明错在哪 + 正确写法（附源码位置）",
    "drogon-gen-xxx",          # guide：修复指向的 skill（模型据此按需加载知识）
)
```

编号约定：`CPP.NNN` / `CSP.NNN` / `CFG.NNN` / `TEST.NNN`，**只新增、不复用、不改语义**（改了语义就换新号），因为文档与测试会按号引用。

新增规则必须同时做两件事：

1. 在 `tests/test_posttooluse.py::RULE_FIXTURES` 里补 **1 个正例 + 1 个反例**。缺任何一侧测试都会失败——缺反例意味着"误报没有人守护"，而误报会直接消耗用户对钩子的信任。
2. 确认 `rule_id` 唯一（`scripts/check-consistency.py` 会校验）。

写正则时的纪律：

- **C++ 标识符必须大小写敏感**（`done()`、`ASSERT_*`、`createDbClient`）。历史回归：全局 `re.IGNORECASE` 让 `isDone()` / `task.done` 被误报为 `done()`。
- 只有**确实**大小写不敏感的模式（CSP 标签）才传 `re.IGNORECASE`；**不要在注释里声称用了而代码里没用**。
- 避免灾难性回溯（嵌套量词 + 回溯性断言组合）；扫描是逐文件一次，规则总量要克制。
- 宁可收窄匹配范围（提高精度）也不要大面积误报。示例：`CPP.009`（Advice 注册）被收窄为"出现在带 `HttpRequestPtr`/`HttpResponsePtr` 参数的函数体内"，这样 `main()` 里合法注册不会被误报。

---

## 7. `--scan` 输出契约（不可破坏）

`python hooks/posttooluse.py --scan --format json PATH` 的输出是**向后兼容的超集**：

```json
{
  "findings": [
    {
      "file": "src/bad.cc",
      "violations": ["<人类可读消息>"],
      "rules": [{"rule_id": "CPP.001", "severity": "error", "guide": "drogon-gen-filter"}]
    }
  ],
  "total": 1
}
```

- `file` / `violations` / `total` 的**名字与语义不得变更**（v0.3.x 起就是契约，`tests/test_posttooluse.py::test_scan_json_contract_is_backward_compatible_superset` 守护）。
- 新增信息一律**只增不改**。

---

## 8. 提交与发布

- 提交信息用 Conventional Commits：`feat:` / `fix:` / `docs:` / `refactor:` / `chore:`。
- 版本只有一个事实源 —— `VERSION` 文件：

```bash
# 发布前
$EDITOR VERSION            # 例如 0.4.0
$EDITOR CHANGELOG.md       # 按 Keep a Changelog 补条目
python scripts/gen-host-artifacts.py      # 同步全部清单版本
python scripts/gen-host-artifacts.py --check
python scripts/check-consistency.py
git tag v0.4.0 && git push origin v0.4.0  # publish.yml 断言 tag == VERSION
```

> 不要手工去改 `AGENTS.md` / `GEMINI.md` / 各宿主清单里的版本号 —— 它们是生成物，改 `VERSION` 后重跑生成器即可。
