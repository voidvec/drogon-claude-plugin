"""基线内事实错误守卫（v1.9.13）。

这些用例锁死的不是"风格"，而是**当年核对不严留下的假陈述**：不存在的 API 名、
不存在的配置键、方向反了的禁令。每条都已在 drogon v1.9.13 tag 原文实证，
证据坐标见 docs/BASELINE-V1.9.13-FACT-ERRORS.md。

两道防线:
1. FORBIDDEN —— 假 token 一旦回流(或被同步进宿主产物)立即变红。
2. REQUIRED —— 被纠正的高危结论必须以正确形态留在文档里,防止"删掉错的就算改完"。

Run:  python -m pytest tests/test_skills_facts.py
"""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

# 只扫事实源:技能正文 + CLAUDE.md(宿主产物由 gen-host-artifacts.py 从这里生成)。
# 生成资产目录(npm/assets、src/.../drogon_plugin_assets)由 sync-assets 门禁单独对拍。
#
# README*.md 是人手写的,曾经单独写过假能力声明(路径参数 `:param`),首轮扫描面不含它
# 所以漏了;AGENTS.md/GEMINI.md 是生成产物,放进来只多拦一种情况——假 token 已被 CLAUDE.md
# 改掉但产物没重生成时,这里会再红一次。("产物与事实源整体不同步"本身已由
# tests/test_hosts.py::test_generator_check_passes_on_repo 拦住,不靠本用例。)
SCAN_GLOBS = ("skills/**/*.md", "CLAUDE.md", "README*.md", "AGENTS.md", "GEMINI.md")

# token -> 为什么是假的(v1.9.13 实证)
FORBIDDEN = {
    "logfile_size": "drogon 无此配置键,真实键是 log_size_limit(ConfigLoader.cc:164)",
    "findByCriteria": "Mapper<T> 无此方法(全树 0 命中),真实是 findBy/findOne/findByPrimaryKey",
    "req->getLoop": "HttpRequest 公共接口无 getLoop,按此生成即编译失败",
    ":param": "drogon 路径参数没有冒号语法,占位符是 {} / {N} / {N:name}",
    "drogon::orm_lib": "只导出 Drogon::Drogon 一个 imported target,ORM/Redis 都编在主库里",
    "drogon::redis_client": "同上,Redis 无独立导出目标",
    "registerPathAdvice": "全树 0 命中,控制器注册走 pathRegistrator + initPathRouting()",
    "execCommand<": "RedisClient 无裸 execCommand 重载,只有 execCommandAsync/Sync/Coro",
    "只接受一个字符串参数": "PATH_ADD(path, ...) 是变参宏(HttpSimpleController.h:27),此禁令会诱导删掉合法约束",
    "`{param}` 模板引擎语法": "{id} 命名占位是 drogon 支持的写法(HttpControllersRouter.cc:346),禁用它等于禁掉正解",
    "无消息大小上限配置": "v1.9.13 已有 setClientMaxWebSocketMessageSize(HttpAppFramework.h:1301),默认 128K",
    "setWebSocketMaxMessageSize": "该名字不存在;真实 API 是 setClientMaxWebSocketMessageSize",
    "client->get(": "RedisClient 没有 get/set/lpush 这类命令方法,命令名只能作为字符串参数传入",
    "client->set(": "同上,RedisClient 无按命令命名的成员方法",
    "抛异常进 catch 即触发回滚": "TransactionImpl 析构无条件 commit(TransactionImpl.cc:37-88),"
                             "照此写法半截失败的批量写会被提交进库",
    "无法区分 HTTP 方法": "PATH_ADD 的变参位就是 HttpConstraint,simple 控制器可以限定方法"
                       "(HttpControllersRouter.cc:193-225 processSimpleControllerParams)",
    "HttpRequestPtr(const HttpRequestPtr&)": "sync advice 回的是 HttpResponsePtr,"
                                         "返回请求指针的签名不存在(HttpAppFramework.h:356-358)",
    "Alias for `[[ key ]]`": "{% %} 编译成 C++ 表达式(create_view.cc:537-538),不是按键取值的别名",
    "is valid for variable interpolation only": "同上:单值 {% key %} 走的是表达式而非键查找",
    "must be exactly a single space": "[[ ]] 的键名解析是跳前导空格后截到下一个空格"
                                   "(create_view.cc:155-164),方括号内并无'必须只有一个空格'的规则",
    "递归扫描": "ParseAndAddDrogonTests 只读 target 的 SOURCES 属性"
             "(cmake/ParseAndAddDrogonTests.cmake:74-79),不扫目录",
    "自动注册为单独的测试目标": "它注册的是 ctest 条目(add_test),不是每宏一个可执行目标",
    "默认 `Restful*Ctrl`": "class_name 的代码默认值是 \"/*\"(create_model.cc:1451),"
                        "`Restful*Ctrl` 只是模板示例里的显式值",
    "替换为表名": "`*` 替换的是模型类名 tableInfo[\"className\"](create_model.cc:1443-1456),不是表名",
    "examples/pay-server": "drogon v1.9.13 的 examples/ 下没有 pay-server 目录(该目录共 15 个示例子目录,无此项),"
                           "把它写成 drogon 路径等于给出用户永远打不开的证据坐标",
    # —— 以下为补审组 E/F/G(余下 11 个技能)实证后的新增项 ——
    "连接数（默认 10）": "db_clients 的 connection_number 默认是 1(ConfigLoader.cc:557 "
                      "`client.get(\"connection_number\", 1)`),照'默认 10'理解会以为不写就有 10 条连接",
    "connection_number` 必须为 1": "SQLite 并无此约束:DbClientImpl.cc:87-96 按 numberOfConnections_ 建 N 条连接,"
                                   "只是 loops 被压成 1(:62-67)并由 SharedMutex 串行——说成'必须为 1'是把合法配置判成非法",
    "连接失败时抛": "loadConfigFile 抛的 runtime_error 全是配置文件层面错误(ConfigLoader.cc:113/117/124/139/301),"
                  "数据库连不上发生在运行期,try/catch 拦不到",
    "trantor::EventLoop::TimerId": "trantor 的 TimerId 是命名空间级别名 `using TimerId = uint64_t`"
                                   "(trantor/net/EventLoop.h:40),EventLoop 内没有嵌套别名,照抄即编译失败",
    'forwardCoro(req, "backend.example.com:8080")': "hostString 必须以 http:// 或 https:// 开头,"
                                                   "否则 HttpClientImpl.cc:171-184 直接 return,域名/端口都不设置——静默失败",
    'getOptional<bool>("loggedIn")': "同文档的 login 模板只写 userId、logout 只 erase userId,"
                                     "从没写过 loggedIn 这个键;Session.h:81-91 键不存在即返回 nullopt,照抄后门禁永远 401",
    "std::vector<HttpFile>& getFiles()": "真实签名带尾部 const:MultiPart.h:131 "
                                         "`const std::vector<HttpFile> &getFiles() const;`",
    "Json::Value({{": "jsoncpp 的 Value 没有 initializer_list 构造(1.9.5/1.9.6/1.9.7/master 的 value.h 均 0 命中),"
                      "`Json::Value({{\"a\",\"b\"}})` 会匹配 Value(const String&) 并用两个无关字面量首尾指针"
                      "构造 std::string(begin,end)——未定义行为且不是 JSON 对象",
}

# 中文散文型 token 只在**特定文件**里说过错话(例如把 PATH_ADD 写成单参数)。
# 同一句措辞换个文件出现,很可能是另一条无害甚至正确的表述,所以这类 token 按
# 目录限定作用域;API 名/配置键型 token 是硬事实,全扫描面一律禁止。
FILE_SCOPE = {
    "只接受一个字符串参数": ("skills/drogon-create-controller/",),
    "递归扫描": ("skills/drogon-gen-test/",),
    "连接失败时抛": ("skills/drogon-gen-db-config/",),
}

# (文件相对路径, 必须出现的正确表述) —— 防止"删掉错的"被当成"改对了"
REQUIRED = [
    ("skills/drogon-setup-config/references/code-guide.md", "log_size_limit"),
    ("skills/drogon-setup-config/references/code-guide.md", "max_files"),
    ("skills/drogon-create-controller/references/code-guide.md", "getRoutingParameters"),
    ("skills/drogon-create-controller/references/code-guide.md", "PATH_ADD(path, ...)"),
    ("skills/drogon-create-controller/references/code-guide.md", "simpleCtrlMap_"),
    ("skills/drogon-gen-websocket/references/code-guide.md", "setClientMaxWebSocketMessageSize"),
    ("skills/drogon-gen-websocket/references/code-guide.md", "client_max_websocket_message_size"),
    ("skills/drogon-gen-orm-crud/references/code-guide.md", "updateBy"),
    ("skills/drogon-gen-orm-crud/references/code-guide.md", "trans->rollback()"),
    ("skills/drogon-gen-redis-config/references/code-guide.md", "execCommandSync"),
    ("skills/drogon-gen-redis-config/references/code-guide.md", "newTransactionCoro"),
    ("skills/drogon-gen-cmake/references/code-guide.md", "find_package(Drogon CONFIG REQUIRED)"),
    ("skills/drogon-gen-cmake/references/code-guide.md", "DrogonConfig.cmake.in:14-20"),
    ("skills/drogon-gen-plugin/references/code-guide.md", "app().run()` 内部"),
    ("skills/drogon-gen-advice/references/code-guide.md", "HttpResponsePtr(const HttpRequestPtr&)"),
    ("skills/drogon-gen-csp-view/references/code-guide.md", "create_view.cc:537-538"),
    ("skills/drogon-gen-csp-view/references/code-guide.md", "create_view.cc:155-164"),
    ("skills/drogon-gen-test/references/code-guide.md", "ParseAndAddDrogonTests.cmake:74-79"),
    ("skills/drogon-gen-test/references/code-guide.md", "enable_testing()"),
    ("skills/drogon-gen-orm-model/references/code-guide.md", "create_model.cc:1443"),
    ("skills/drogon-gen-orm-crud/references/code-guide.md", "TransactionImpl.cc:37-88"),
    ("skills/drogon-create-controller/references/code-guide.md", "create_controller.cc:28-59"),
    ("skills/drogon-create-controller/references/code-guide.md", "HttpSimpleController.h:27"),
    ("skills/drogon-setup-config/references/code-guide.md", "ConfigLoader.cc:168-184"),
    ("skills/drogon-setup-config/references/code-guide.md", "ConfigLoader.cc:266"),
    ("skills/drogon-setup-config/references/code-guide.md", "bytesSize"),
    ("skills/drogon-gen-websocket/references/code-guide.md", "ConfigLoader.cc:487-491"),
    ("skills/drogon-gen-session-auth/references/code-guide.md", "根本没有 `operator[]`"),
    # —— 补审组 E/F/G ——
    ("skills/drogon-gen-db-config/references/code-guide.md", "ConfigLoader.cc:557"),
    ("skills/drogon-gen-db-config/references/code-guide.md", "合法回落键"),
    ("skills/drogon-gen-db-config/references/code-guide.md", "静默丢弃"),
    ("skills/drogon-gen-db-config/references/code-guide.md", "配置文件层面"),
    ("skills/drogon-gen-coroutine-handler/references/code-guide.md",
     'forwardCoro(req, "http://backend.example.com:8080")'),
    ("skills/drogon-gen-coroutine-handler/references/code-guide.md", "HttpRequestPtr req)"),
    ("skills/drogon-gen-session-auth/references/code-guide.md", 'getOptional<std::string>("userId")'),
    ("skills/drogon-gen-file-upload/references/code-guide.md", "&getFiles() const"),
    ("skills/drogon-gen-stream/references/code-guide.md", "trantor::TimerId"),
    ("skills/drogon-gen-monitoring/references/code-guide.md", "不在源码核对范围内"),
    # —— 交付前评审补漏:B7/B40 原先只写了"随 xxx 一并覆盖",实际没有任何 needle ——
    ("skills/drogon-setup-config/references/code-guide.md", "ConfigLoader.cc:43-106"),
    ("skills/drogon-setup-config/references/code-guide.md", "数字白名单"),
    ("skills/drogon-gen-websocket/references/code-guide.md", "数字白名单"),
    ("skills/drogon-gen-session-auth/references/code-guide.md", "const std::string &value) = 0;"),
    ("skills/drogon-setup-config/SKILL.md", "drogon 自身默认 `DEBUG`"),
    ("skills/drogon-setup-config/references/code-guide.md", "不是 drogon 的键名"),
    # —— 补审组 H:jsoncpp 花括号构造(外部依赖,已取证) ——
    ("skills/drogon-gen-filter/references/code-guide.md", "no `initializer_list` constructor"),
    ("skills/drogon-gen-filter/references/code-guide.md", 'Json::Value body; body["k"] = "v";'),
]


def _scanned_files():
    seen = []
    for pattern in SCAN_GLOBS:
        for path in sorted(REPO_ROOT.glob(pattern)):
            if path.is_file():
                seen.append(path)
    return seen


def _scoped_files(token):
    """token 实际被扫描的文件:散文型 token 只看登记过的目录,其余看全扫描面。"""
    prefixes = FILE_SCOPE.get(token)
    files = _scanned_files()
    if not prefixes:
        return files
    return [p for p in files
            if p.relative_to(REPO_ROOT).as_posix().startswith(prefixes)]


# 文档里"**没有** `foo()` 这个东西 / 写它是错的"这类反面示例是有意的教学内容,
# 但它和"回归成假陈述"在子串层面长得一样。唯一放行方式是行尾显式写出**被豁免的
# token 名**,让放行成为一次可 grep、可评审、且只对该 token 生效的动作——
# 行级裸标记会让同一行上的其它假 token 一起被放掉。
WAIVER_PREFIX = "<!-- fact-guard-waived:"
WAIVER_SUFFIX = " -->"
# 标记的共同前缀(不含冒号):凡是写过这个前缀的行尾注释都必须能被解析成点名形式,
# 否则就是"裸标记"——它不豁免任何东西,却会在 diff 里看起来像一次已评审的放行。
MARKER_HEAD = "<!-- fact-guard-waived"


def _waived_names(line):
    """按出现顺序返回该行点名的豁免 token 名(只解析,不判断合法性)。

    未闭合的标记(漏了 ` -->`)不会被返回,于是 `_waiver_problems` 里"写了几个 / 认出几个"
    对不上,同样会红。
    """
    names = []
    rest = line
    while WAIVER_PREFIX in rest:
        name, sep, rest = rest.split(WAIVER_PREFIX, 1)[1].partition(WAIVER_SUFFIX)
        if not sep:
            break
        names.append(name)
    return names


def _strip_markers(line):
    """剥掉该行所有豁免标记文本,只留正文。

    标记的写法就是 `<!-- fact-guard-waived:TOKEN -->`,TOKEN 是标记文本的一部分;
    不先剥掉就直接判"这行有没有写这个 token",那条断言永远为真。
    未闭合的标记连同其后的内容一起丢掉(它已由"写了几个 / 认出几个"对不上而变红)。
    """
    out = []
    rest = line
    while WAIVER_PREFIX in rest:
        head, rest = rest.split(WAIVER_PREFIX, 1)
        out.append(head)
        _name, sep, rest = rest.partition(WAIVER_SUFFIX)
        if not sep:
            rest = ""
            break
    out.append(rest)
    return "".join(out)


def _offending_lines(text, token):
    """返回 token 的**未豁免**出现行号。token 不含换行,故按行切分与全文匹配等价。"""
    return [i for i, line in enumerate(text.splitlines(), 1)
            if token in line and token not in _waived_names(line)]


def _token_hits(token):
    # as_posix():失败信息里的路径要能直接复制去 grep,Windows 反斜杠不行。
    return [f"{p.relative_to(REPO_ROOT).as_posix()}:{n}"
            for p in _scoped_files(token)
            for n in _offending_lines(p.read_text(encoding="utf-8"), token)]


def test_waiver_marker_only_lifts_the_line_it_marks():
    """正向对照:同一 token,标了豁免才放行,没标必须照红。"""
    waived = "没有 `foo_bar()` 这个东西 " + WAIVER_PREFIX + "foo_bar(" + WAIVER_SUFFIX
    assert _offending_lines(waived, "foo_bar(") == []
    assert _offending_lines("照抄 `foo_bar()` 调用", "foo_bar(") == [1]


def test_waiver_for_one_token_does_not_lift_another_on_the_same_line():
    """正向对照:豁免按 token 生效,同一行的其它假 token 必须照红。"""
    both = ("既没有 `client->get(` 也没有 `findByCriteria`,只豁免前者 "
            + WAIVER_PREFIX + "client->get(" + WAIVER_SUFFIX)
    assert _offending_lines(both, "client->get(") == []
    assert _offending_lines(both, "findByCriteria") == [1]


def test_waiver_decoration_is_always_a_problem():
    """反向对照补漏:装饰性豁免必须被抓出,否则"标了豁免"看着像已评审其实没保护。

    四种装饰:①不带 token 名的裸标记;②闭合缺失;③在不扫描该 token 的文件里豁免它
    (FILE_SCOPE 之外的文件根本不会被检查,标记只骗过读 diff 的人);
    ④点名了一个**正文里根本没有**的 token——标记自带 token 名,所以判定前必须先把标记
    本身从这一行里剥掉,否则"该行确实写了它"这条腿永远成立(评审实测出的死分支)。
    """
    bare = "这里没有 `client->get(` <!-- fact-guard-waived -->"
    assert _waiver_problems("README.md", bare), "裸标记没被抓出"

    unclosed = "这里没有 `client->get(` <!-- fact-guard-waived:client->get("
    assert _waiver_problems("README.md", unclosed), "未闭合标记没被抓出"

    decoration = "本工具递归扫描目录 <!-- fact-guard-waived:递归扫描 -->"
    assert _waiver_problems("README.md", decoration), "scope 外的装饰性豁免没被抓出"

    # ④正文里没有这个词,只把标记名贴了上去——剥掉标记后该行应该看不见 token
    phantom = "本技能会注册测试 <!-- fact-guard-waived:递归扫描 -->"
    rel = "skills/drogon-gen-test/references/code-guide.md"
    assert _waiver_problems(rel, phantom), "豁免了正文里不存在的 token 却没被抓出(死分支)"

    # 正向对照:同一标记写在真正扫描该 token 的文件里就不算问题
    assert _waiver_problems(rel, decoration) == [], _waiver_problems(rel, decoration)


def _waiver_problems(rel_path, text):
    """返回该文本里**无效豁免标记**的描述列表(纯函数,便于用合成文本做正反对照)。

    一个标记只有在"点名了 FORBIDDEN 里真实存在的 token、该 token 确实出现在这一行的
    正文里(把标记本身剥掉之后还看得见)、而且这个文件确实会为该 token 跑扫描"时,
    才算一次可评审的放行。
    """
    problems = []
    here = REPO_ROOT / rel_path
    for line_no, line in enumerate(text.splitlines(), 1):
        names = _waived_names(line)
        written = line.count(MARKER_HEAD)
        if written == 0:
            continue
        body = _strip_markers(line)
        if written != len(names):
            problems.append(f"{rel_path}:{line_no} 写了 {written} 个豁免标记,只认出 {len(names)} 个"
                            "(裸标记 `<!-- fact-guard-waived -->` 或未闭合)")
        for name in names:
            if name not in FORBIDDEN:
                problems.append(f"{rel_path}:{line_no} 豁免了未知 token {name!r}")
            elif name not in body:
                problems.append(f"{rel_path}:{line_no} 豁免了 {name!r} 但剥掉标记后该行并没有它"
                                "(标记名自己就含 token,必须对正文判存在)")
            elif here not in _scoped_files(name):
                problems.append(f"{rel_path}:{line_no} 豁免的 {name!r} 在本文件不参与扫描,"
                                "标记只是装饰(FILE_SCOPE 已把这个 token 限定到别的目录)")
    return problems


def test_no_zombie_waiver_marker():
    """反向对照:全扫描面里不许有装饰性豁免(检测器本身由合成文本对照锁住)。"""
    bad = []
    for path in _scanned_files():
        rel = path.relative_to(REPO_ROOT).as_posix()
        bad += _waiver_problems(rel, path.read_text(encoding="utf-8"))
    assert not bad, (
        "以下豁免标记无效,应写成 `<!-- fact-guard-waived:TOKEN -->` 且点名该行真实存在、"
        "且本文件确实会扫描的 token: " + str(bad)
    )


def test_file_scope_narrows_without_emptying():
    """守卫方向:散文型 token 的目录限定必须真的生效,但不能把守卫 scope 成 0 个文件。"""
    total = len(_scanned_files())
    for token, prefixes in FILE_SCOPE.items():
        files = _scoped_files(token)
        assert files, f"{token} 的 scope {prefixes} 一个文件都没匹配上,等于删掉了守卫"
        assert len(files) < total, f"{token} 的 scope {prefixes} 覆盖了全部文件,限定形同不存在"


def test_fact_registries_have_declared_sizes():
    """守卫方向:FORBIDDEN/REQUIRED 是用 parametrize 展开的,删一条就少一条用例且不会变红。

    所以数量本身也要写明——新增/删除条目时必须同一次改动里改这个数字,
    让"削弱守卫"成为一次显式、可评审的动作,而不是顺手清理。

    数量之外还要判**内容不退化**:把 needle 改成空串或纯空白、把 token 改成打不中的
    串,用例数一条不少却全部失去作用,只有数量 canary 拦不住。
    """
    assert len(FORBIDDEN) == 33, f"FORBIDDEN 现为 {len(FORBIDDEN)} 条;要增减请同时改动测试与报告"
    assert len(REQUIRED) == 46, f"REQUIRED 现为 {len(REQUIRED)} 条;同上"
    assert len(FILE_SCOPE) == 3, f"FILE_SCOPE 现为 {len(FILE_SCOPE)} 条;散文 token 的目录限定要逐条评审"
    assert set(FILE_SCOPE) <= set(FORBIDDEN), "FILE_SCOPE 点名了不在 FORBIDDEN 里的 token"
    for token, reason in FORBIDDEN.items():
        assert token and token.strip(), f"FORBIDDEN 里有空白 token {token!r},子串匹配等于永不命中"
        assert reason and reason.strip(), f"{token!r} 的理由被清空:红灯会变成没有结论的噪音"
    for rel, needle in REQUIRED:
        assert needle and needle.strip(), f"{rel} 的 needle 是空串,该用例只会空洞通过"
    assert len(set(REQUIRED)) == len(REQUIRED), "REQUIRED 里有重复条目,数量 canary 会被同一含义撑虚"
    for prefixes in FILE_SCOPE.values():
        for prefix in prefixes:
            assert prefix.startswith("skills/") and prefix.endswith("/"), (
                f"scope 前缀 {prefix!r} 必须是 skills/ 下的目录前缀(以 / 结尾),"
                "否则会随文件名改名而静默失配")


def test_scan_surface_still_covers_every_fact_source():
    """守卫方向:扫描面本身不能缩水。

    假 API 写在 README 或没重新生成的 AGENTS.md/GEMINI.md 里也曾是红灯之外的盲区,
    所以这里把"事实源必须在扫描面内"钉住。三条各有分工,别混着声称:
    ① `SCAN_GLOBS` 被改小 → ②③ 之外的根文件断言立刻红;
    ② REQUIRED 点名的文件改名/丢失 → 那条 needle 用例红(改名后仍留在 `skills/**/*.md`
      里也照样红,因为 needle 找不到文件);没有任何 needle 的文件改名则**不会红**,
      这条盲区如实登记在报告 §4;
    ③ 技能数 != 22 会红——那是"口径变更"信号(新增技能必须同时改 22、报告与 README
      矩阵),不是盲区检测;`>= 49` 是同方向的下界。
    """
    scanned = {p.relative_to(REPO_ROOT).as_posix() for p in _scanned_files()}
    for required in ("CLAUDE.md", "AGENTS.md", "GEMINI.md", "README.md", "README.zh-CN.md"):
        assert required in scanned, f"{required} 不在扫描面内,SCAN_GLOBS 被改小了"
    on_disk = {p.relative_to(REPO_ROOT).as_posix()
               for p in REPO_ROOT.glob("skills/**/*.md") if p.is_file()}
    assert on_disk <= scanned, f"技能文档漏出扫描面: {sorted(on_disk - scanned)}"
    guides = {p for p in on_disk if p.endswith("/SKILL.md")}
    assert len(guides) == 22, f"技能数与基线口径(22)不符,当前 {len(guides)}:先确认是否整体改了口径"
    assert len(scanned) >= 49, f"扫描面只有 {len(scanned)} 个文件,低于基线 49"


@pytest.mark.parametrize("token", sorted(FORBIDDEN))
def test_false_token_never_returns(token):
    """假 API 名/假配置键/反向禁令一旦写回文档就红。"""
    hits = _token_hits(token)
    assert not hits, f"{token} 是 v1.9.13 下不成立的说法({FORBIDDEN[token]});仍出现在 {hits}"


@pytest.mark.parametrize("rel_path,needle", REQUIRED)
def test_corrected_claim_stays_in_place(rel_path, needle):
    """纠正后的正确结论必须还在原文件里。"""
    path = REPO_ROOT / rel_path
    assert path.is_file(), f"文件不存在: {rel_path}"
    assert needle in path.read_text(encoding="utf-8"), (
        f"{rel_path} 缺少正确表述 {needle!r}——删掉错的不等于改对了"
    )
