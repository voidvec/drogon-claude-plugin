# drogon-claude-plugin

> **Claude Code plugin for Drogon C++ backend development** — AI-assisted development rules and code-generation skills that keep the assistant writing *correct* asynchronous code, avoiding classic callback / event-loop pitfalls.

**English** | [简体中文](README.zh-CN.md)

[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![CI](https://github.com/voidvec/drogon-claude-plugin/actions/workflows/ci.yml/badge.svg)](https://github.com/voidvec/drogon-claude-plugin/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/drogon-claude-plugin.svg)](https://pypi.org/project/drogon-claude-plugin/)
[![npm version](https://img.shields.io/npm/v/drogon-claude-plugin.svg)](https://www.npmjs.com/package/drogon-claude-plugin)
[![Claude Code](https://img.shields.io/badge/Claude%20Code-plugin-8A2BE2)](https://docs.anthropic.com/en/docs/claude-code/plugins)

A [Claude Code plugin](https://docs.anthropic.com/en/docs/claude-code/plugins) for application projects built on the [Drogon](https://github.com/drogonframework/drogon) C++ HTTP framework. It provides AI-assisted development rules and **code-generation skills** so the assistant produces correct, idiomatic asynchronous code and avoids the frequent traps around callbacks and the event loop.

## Installation

### Option A: Marketplace (recommended)

```bash
# Add the marketplace source (first time only)
claude plugin marketplace add https://github.com/voidvec/drogon-claude-plugin

# Install the plugin
claude plugin install drogon

# Update to the latest version
claude plugin update drogon
```

### Option B: npm / PyPI (CLI installer)

The npm and PyPI packages **bundle the exact same plugin assets** and expose a single `drogon-claude-plugin` command with `install` / `verify` / `uninstall` / `version` subcommands. No need to clone this repository.

```bash
# npm (no installation needed, run on the fly)
npx drogon-claude-plugin install

# or PyPI (recommended for persistent use)
pipx install drogon-claude-plugin
drogon-claude-plugin install
```

> The installer only **distributes and materializes** the assets. It does not replace Claude Code's official plugin mechanism — the plugin is still enabled with `claude plugin install` (the installer will tell you to run it).

### Option C: Install from source

```bash
git clone https://github.com/voidvec/drogon-claude-plugin
cd <your drogon project>
claude plugin install ../drogon-claude-plugin --scope project
```

### Verify the installation

```bash
claude plugin details drogon
```

You should see **17 skills** and **2 hooks** (SessionStart + PostToolUse).

## The CLI installer

`drogon-claude-plugin` is published on both [npm](https://www.npmjs.com/package/drogon-claude-plugin) and [PyPI](https://pypi.org/project/drogon-claude-plugin/). Both packages ship the same plugin assets (`skills/`, `hooks/`, `CLAUDE.md`, `.claude-plugin/`) and provide the same command-line interface:

| Command | What it does |
|---------|--------------|
| `drogon-claude-plugin install [--scope project\|user\|local]` | Copies the plugin assets into the current project (or the given scope) and prompts you to run `claude plugin install` |
| `drogon-claude-plugin verify` | Validates the installed structure (skills / hooks / manifests) and prints a report |
| `drogon-claude-plugin uninstall` | Removes the installed plugin assets from the current project (or the `--target` directory) |
| `drogon-claude-plugin version` | Prints the CLI and the bundled plugin version |

### Typical usage

```bash
# Run at the root of your drogon project
npx drogon-claude-plugin install             # npm, on the fly
drogon-claude-plugin install                 # after pipx / npm -g install

drogon-claude-plugin verify                  # confirm all 17 skills + 2 hooks
drogon-claude-plugin uninstall               # remove the assets (never touches your code)
```

## What's inside

The plugin is organised in three layers, each with a single responsibility:

| Layer | Location | Purpose |
|-------|----------|---------|
| **Rules** | `CLAUDE.md` | Top-level discipline auto-injected into every session (async callback model, event-loop model) |
| **Skills** | `skills/` (17) | On-demand drogon code generation / configuration skills, backed by deep knowledge in `references/code-guide.md` |
| **Detection** | `hooks/` (2) | Scans files after edits, flags drogon API violations, prompts fixes |

### Rules layer — `CLAUDE.md`

A **slim-router** design: only the discipline that applies to *every* task (async callback model, event-loop model) plus a skill routing table stay in `CLAUDE.md`. Everything else — templates, API cheat-sheets, config formats, forbidden patterns — lives in each skill's `references/code-guide.md` and is loaded **on demand**, keeping the context window lean.

Top-level discipline covers:

- **A. Async callback model** — callback exactly once, capture by value, no blocking, prefer coroutines, exception-safe
- **B. Event-loop model (Trantor IO)** — never block the loop, offload heavy work to the thread pool, lock shared state across loops
- **General** — all I/O async, async ops take two callbacks, no exceptions escape handlers, config loading wrapped in try/catch, strict key names

### Code-generation skills (17)

Each skill provides accurate drogon API usage, code templates, and warnings for common mistakes. The assistant invokes the matching skill when it meets the task, loading detailed knowledge only then:

| Skill | Purpose |
|-------|---------|
| `drogon-create-controller` | Controllers (Simple/Http/WebSocket), path-prefix differences, `:param`, auto-registration |
| `drogon-gen-cmake` | CMakeLists.txt, incl. Conan and filter-based compilation |
| `drogon-gen-csp-view` | CSP view templates, the `drogon_ctl create view` pipeline, layouts |
| `drogon-gen-db-config` | Database configuration, key-name blacklist, SQL-injection guards, runtime exceptions |
| `drogon-gen-filter` | Filter request interceptors |
| `drogon-gen-middleware` | Middleware processing chains |
| `drogon-gen-plugin` | System-level plugins (connection pools / SDK init) and the boundary between the three |
| `drogon-gen-orm-crud` | ORM CRUD code — banned `execSqlSync`, transaction discipline |
| `drogon-gen-redis-config` | Redis config + leak-safe singleton / async / subscription usage |
| `drogon-gen-test` | DROGON_TEST tests, assert macros, CMake test scanning |
| `drogon-setup-config` | Complete config files, path resolution, key-name blacklist, multiple environments |
| `drogon-gen-session-auth` | Session login / logout / auth handlers (fixation-safe) |
| `drogon-gen-file-upload` | File-upload handlers (MultiPartParser + validation + persistence) |
| `drogon-gen-advice` | AOP Advice (11 aspects, intercepting and observing) |
| `drogon-gen-coroutine-handler` | Coroutine handlers / middleware / ORM (params by value, Task vs AsyncTask, `forwardCoro`) |
| `drogon-gen-http-client` | Outbound HttpClient calls (async / coroutine / reverse proxy) |
| `drogon-gen-lambda-handler` | `registerHandler` lambda routes (`{N}` parameter binding) |

### Detection hooks (`PostToolUse`)

After the assistant edits a file, the hook scans for drogon API violations:

| File type | Checks |
|-----------|--------|
| `.h/.cc/.cpp` | `FILTER_ADD`, `ADD_MIDDLEWARE`, `METHOD_LIST_ADD`, `createDbClient`, missing exception wrapping around `AsyncTask` + `co_await`, `co_await` inside a callback-style `HttpMiddleware`, blocking `sendRequest`, `session->operator[]`, Advice registered inside a handler |
| `.csp` | `{{ }}`, `<%raw%>`, `<%viewpath`, `@@key@@`, `<%extends`, `{% if %}` |
| `config.json/.yaml` | `"password"`, `"username"`, `"ssl"` as a string |
| `test*.cc` | `done()`, `ASSERT_*`, `createDbClient` |

> Fixed in v0.2.0: C++ identifier checks are now case-sensitive (no more false positives on `isDone()`); the hard callback-variable-naming rule that conflicted with CLAUDE.md examples was removed.

## Usage

Once the plugin is enabled in a drogon project it applies automatically. Typical conversations:

```
> Create a REST controller for /api/users
AI: [uses drogon-create-controller] generates UserController.h + UserController.cc...

> Add a JWT auth filter
AI: [uses drogon-gen-filter] generates JwtAuthFilter.h + the registration call...

> Write a test for the user registration endpoint
AI: [uses drogon-gen-test] generates a DROGON_TEST(UserRegister) case...

> Is this handler correct?
AI: [consulting CLAUDE.md async discipline] This handler's early-return path never invokes the callback...
```

## Requirements

- Claude Code CLI installed
- A project that **depends on the drogon framework** (drogon installed as a library)
- A Python 3 interpreter on `PATH` (required by the PostToolUse hook)

## Repository structure

```
├── .claude-plugin/
│   ├── plugin.json
│   └── marketplace.json
├── .github/workflows/
│   ├── ci.yml             # plugin structure + CLI smoke tests
│   └── publish.yml        # tag-triggered → PyPI + npm + GitHub Release
├── scripts/               # build helpers (asset sync + smoke tests)
│   ├── sync-assets.py/.mjs
│   └── dev-smoke-test.py/.mjs
├── hooks/
│   ├── hooks.json
│   └── posttooluse.py
├── src/drogon_plugin/     # PyPI package (CLI installer)
│   ├── __init__.py
│   └── cli.py
├── npm/                   # npm package (CLI installer)
│   ├── package.json
│   └── bin/cli.js
├── skills/                # 17 code-generation skills
│   ├── drogon-create-controller/
│   ├── drogon-gen-advice/
│   ├── drogon-gen-cmake/
│   ├── drogon-gen-coroutine-handler/
│   ├── drogon-gen-csp-view/
│   ├── drogon-gen-db-config/
│   ├── drogon-gen-file-upload/
│   ├── drogon-gen-filter/
│   ├── drogon-gen-http-client/
│   ├── drogon-gen-lambda-handler/
│   ├── drogon-gen-middleware/
│   ├── drogon-gen-orm-crud/
│   ├── drogon-gen-plugin/
│   ├── drogon-gen-redis-config/
│   ├── drogon-gen-session-auth/
│   ├── drogon-gen-test/
│   └── drogon-setup-config/
├── CLAUDE.md
├── LICENSE
├── README.md
├── README.zh-CN.md
└── pyproject.toml           # PyPI packaging config
```

## License

MIT — see [LICENSE](LICENSE).