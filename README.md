# drogon-claude-plugin

> **Coding-agent plugin for Drogon C++ backend development** — AI-assisted development rules and code-generation skills that keep the assistant writing *correct* asynchronous code, avoiding classic callback / event-loop pitfalls. Works with **Claude Code, ZCode, Codex, Cursor, VS Code (Copilot), Gemini CLI, Qoder, CodeBuddy, Trae** and any **AGENTS.md**-compatible agent on **Windows / Linux / macOS**.

**English** | [简体中文](README.zh-CN.md)

[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![CI](https://github.com/voidvec/drogon-claude-plugin/actions/workflows/ci.yml/badge.svg)](https://github.com/voidvec/drogon-claude-plugin/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/drogon-claude-plugin.svg)](https://pypi.org/project/drogon-claude-plugin/)
[![npm version](https://img.shields.io/npm/v/drogon-claude-plugin.svg)](https://www.npmjs.com/package/drogon-claude-plugin)
[![Claude Code](https://img.shields.io/badge/Claude%20Code-plugin-8A2BE2)](https://docs.anthropic.com/en/docs/claude-code/plugins)
[![ZCode](https://img.shields.io/badge/ZCode-plugin-8A2BE2)](https://z.ai)

A [Claude Code](https://docs.anthropic.com/en/docs/claude-code/plugins) / [ZCode](https://z.ai) plugin for application projects built on the [Drogon](https://github.com/drogonframework/drogon) C++ HTTP framework. It provides AI-assisted development rules and **22 code-generation skills** so the assistant produces correct, idiomatic asynchronous code and avoids the frequent traps around callbacks and the event loop.

## Installation

### Option A: Host-native installation (recommended)

| Host | Install | What you get |
|------|---------|--------------|
| **Claude Code** | `claude plugin marketplace add https://github.com/voidvec/drogon-claude-plugin` → `claude plugin install drogon` | skills + rules injection + PostToolUse hook |
| **ZCode** | Add the same marketplace in ZCode's plugin manager → install `drogon` | same as Claude Code |
| **Codex CLI** | `codex plugin marketplace add voidvec/drogon-claude-plugin` → `codex plugin install drogon@drogon-claude-plugin`; then **review & trust** in the `/plugins` panel (plugin hooks don't run until trusted) | skills + AGENTS.md rules + hooks |
| **Cursor** | `drogon-claude-plugin install --host cursor` in your project → `.cursor/skills/` + `.cursor/rules/` | skills + rules |
| **VS Code (Copilot)** | `drogon-claude-plugin install --host copilot` → `.agents/skills/` + `AGENTS.md` | skills + rules |
| **Gemini CLI** | `gemini extensions install https://github.com/voidvec/drogon-claude-plugin` | skills + GEMINI.md context |
| **Qoder** | `drogon-claude-plugin install` (drops `AGENTS.md`) | rules |
| **CodeBuddy** | `drogon-claude-plugin install` (drops `CODEBUDDY.md`) | rules |
| **Trae** | `drogon-claude-plugin install` (drops `.trae/skills/` + `AGENTS.md`) | skills + rules |

Maintenance tiers: **Tier 1** (actively maintained) — Claude Code, ZCode, Codex, Cursor, VS Code + `.agents` fallback. **Best effort** — Gemini CLI, Qoder, CodeBuddy, Trae.

### Option B: npm / PyPI (CLI installer)

The npm and PyPI packages **bundle the exact same plugin assets** and expose a single `drogon-claude-plugin` command. Multi-host installation (`--host`, `scan`, instruction-file protection) is implemented in the **PyPI CLI (reference implementation)**; the npm CLI installs the Claude/ZCode bundle (`.drogon-plugin/`).

```bash
# npm — bundle install for Claude Code / ZCode
npx drogon-claude-plugin install

# PyPI — multi-host installer (reference implementation)
pipx install drogon-claude-plugin
drogon-claude-plugin install                 # all hosts (mutual-exclusion aware)
drogon-claude-plugin install --host cursor   # one host
drogon-claude-plugin install --host copilot  # opt-in .agents/skills
```

> **Your own files are never touched**: if `AGENTS.md` / `GEMINI.md` / `CODEBUDDY.md` already exists, the CLI skips it and prints merge guidance; with `--force-agents` it appends a `<!-- drogon-plugin begin/end -->` marker section, and uninstall removes only that section.

### Option C: Install from source

```bash
git clone https://github.com/voidvec/drogon-claude-plugin
cd <your drogon project>
claude plugin install ../drogon-claude-plugin --scope project
```

### Verify the installation

```bash
claude plugin details drogon        # Claude Code
drogon-claude-plugin verify         # CLI installer (works for any host)
```

You should see **22 skills** and **2 hooks** (SessionStart + PostToolUse).

## The CLI installer

`drogon-claude-plugin` is published on both [npm](https://www.npmjs.com/package/drogon-claude-plugin) and [PyPI](https://pypi.org/project/drogon-claude-plugin/). Both packages ship the same plugin assets and provide the same command-line interface:

| Command | What it does |
|---------|--------------|
| `drogon-claude-plugin install [--host LIST] [--force-agents]` | Installs per host: bundle for Claude/ZCode, `.cursor/skills` + rules for Cursor, instruction files for Codex/Gemini/Qoder/CodeBuddy, `.trae/skills` + `AGENTS.md` for Trae; `all` respects mutual exclusion (no `.agents/skills` duplication) |
| `drogon-claude-plugin scan [--format json] [--strict] [PATH...]` | Violation scan for hosts without hooks and for CI (exit 1 with `--strict`); paths are boundary-checked to stay inside the project |
| `drogon-claude-plugin hosts` | Lists supported hosts and their install kind |
| `drogon-claude-plugin verify [--target DIR]` | Validates the installed structure and reports per-host status |
| `drogon-claude-plugin upgrade [--target DIR]` | Idempotent reinstall to the bundled version (marker sections refreshed) |
| `drogon-claude-plugin uninstall [--host LIST]` | Removes plugin artifacts — ownership-checked; your own instruction files keep everything except our marker section |

## What's inside

The plugin is organised in three layers, each with a single responsibility:

| Layer | Location | Purpose |
|-------|----------|---------|
| **Rules** | `CLAUDE.md` | Top-level discipline auto-injected into every session (async callback model, event-loop model) |
| **Skills** | `skills/` (22) | On-demand drogon code generation / configuration skills, backed by deep knowledge in `references/code-guide.md` |
| **Detection** | `hooks/` (2) | Scans files after edits, flags drogon API violations, prompts fixes |

### Rules layer — `CLAUDE.md`

A **slim-router** design: only the discipline that applies to *every* task (async callback model, event-loop model) plus a skill routing table stay in `CLAUDE.md`. Everything else — templates, API cheat-sheets, config formats, forbidden patterns — lives in each skill's `references/code-guide.md` and is loaded **on demand**, keeping the context window lean.

Top-level discipline covers:

- **A. Async callback model** — callback exactly once, capture by value, no blocking, prefer coroutines (params by value!), exception-safe
- **B. Event-loop model (Trantor IO)** — never block the loop, offload heavy work to a thread pool, lock shared state across loops
- **General** — all I/O async, async ops take two callbacks, no exceptions escape handlers, config loading wrapped in try/catch, strict key names, prefer built-ins (Hodor / PromExporter / AccessLogger), never hand-edit generated code

### Code-generation skills (22)

Every skill's `references/code-guide.md` was written against the **drogon v1.9.13 source tree** (not just the docs) — where the official docs disagree with the source, the source wins and the difference is called out.

| Skill | Purpose |
|-------|---------|
| `drogon-create-controller` | Controllers (Simple/Http/WebSocket), path-prefix differences, `:param`, auto-registration |
| `drogon-gen-lambda-handler` | `registerHandler` lambda routes (`{N}` parameter binding) |
| `drogon-gen-orm-crud` | ORM CRUD — callback + coroutine style; banned `execSqlSync`, transaction discipline |
| `drogon-gen-orm-model` | `drogon_ctl create model` workflow: model.json config, generated-code conventions, CMake integration, MSVC/C++20 codecvt shim |
| `drogon-gen-db-config` | Database configuration, key-name blacklist, SQL-injection guards, runtime exceptions |
| `drogon-gen-redis-config` | Redis config + `execCommandAsync` dual-callback patterns, subscriptions, coroutines |
| `drogon-setup-config` | Complete config files: HTTPS listeners, static files, `custom_config`/`getCustomConfig`, `loadConfigJson`, multi-environment |
| `drogon-gen-cmake` | CMakeLists.txt: `drogon_create_views`, drogon_ctl models, Conan 2, MSVC specifics |
| `drogon-gen-coroutine-handler` | Coroutine handlers / middleware / ORM (params by value, Task vs AsyncTask, `forwardCoro`) |
| `drogon-gen-http-client` | Outbound HttpClient calls (async / coroutine / reverse proxy) |
| `drogon-gen-csp-view` | CSP view templates, the `drogon_ctl create view` pipeline, layouts |
| `drogon-gen-filter` | Filter request interceptors |
| `drogon-gen-middleware` | Middleware processing chains |
| `drogon-gen-plugin` | System-level plugins: full lifecycle, `shutdown()` drain, dedicated `EventLoopThread` workers, static-lib registration pitfalls |
| `drogon-gen-advice` | AOP Advice (11 aspects, intercepting and observing) |
| `drogon-gen-file-upload` | File-upload handlers (MultiPartParser + validation + persistence) |
| `drogon-gen-stream` | Streaming uploads (RequestStream) and chunked streaming responses (`newStreamResponse` / `newAsyncStreamResponse`) |
| `drogon-gen-session-auth` | Session login / logout / auth (fixation-safe) + cookie security |
| `drogon-gen-websocket` | WebSocket controllers, connection management / broadcast, cross-thread send safety, heartbeats |
| `drogon-gen-rate-limiter` | Hodor plugin config + custom 429 responses, programmatic `RateLimiter`/`SafeRateLimiter`, Redis distributed limiting |
| `drogon-gen-monitoring` | Prometheus metrics via PromExporter (Counter/Gauge/Histogram) |
| `drogon-gen-test` | DROGON_TEST: assert macros, async tests, custom main, port isolation |

### Detection hooks (cross-platform, dependency-free rules injection)

After the assistant edits a file, the PostToolUse hook scans for drogon API violations; the SessionStart hook injects the rules layer. Hook execution is **bash-based via a polyglot launcher** (`hooks/run-hook.cmd`, the pattern proven by the superpowers plugin):

- **SessionStart is pure shell** — no Python, Node or other interpreter required, so rules injection works identically on Windows (Git Bash), Linux and macOS, in both Claude Code and ZCode.
- **PostToolUse** looks for a Python 3 interpreter (`python3` → `python` → `py`, overridable via `DROGON_PLUGIN_PYTHON`) and degrades silently when none exists — it never breaks the host.
- The v0.1.x hooks invoked bare `python`, which fails silently on Ubuntu 24.04+ (no `python` binary) and many Windows setups; this is fixed in v0.2.0.

| File type | Checks |
|-----------|--------|
| `.h/.cc/.cpp` | `FILTER_ADD`, `ADD_MIDDLEWARE`, `METHOD_LIST_ADD`, `createDbClient`, unwrapped `AsyncTask` + `co_await`, `co_await` inside callback-style `HttpMiddleware`, blocking `sendRequest`, `session->operator[]`, Advice registered inside a handler |
| `.csp` | `{{ }}`, `<%raw%>`, `<%viewpath`, `@@key@@`, `<%extends`, `{% if %}` |
| `config.json/.yaml` | `"password"`, `"username"`, `"ssl"` as a string |
| `test*.cc` | `done()`, `ASSERT_*`, `createDbClient` |

## Usage

Once the plugin is enabled in a drogon project it applies automatically. Typical conversations:

```
> Create a REST controller for /api/users
AI: [uses drogon-create-controller] generates UserController.h + UserController.cc...

> Add a JWT auth filter
AI: [uses drogon-gen-filter] generates JwtAuthFilter.h + the registration call...

> Generate the ORM models from the production schema
AI: [uses drogon-gen-orm-model] writes model.json, runs drogon_ctl create model,
    wires the OBJECT library + orm_compat shim into CMake...

> Write a test for the user registration endpoint
AI: [uses drogon-gen-test] generates a DROGON_TEST(UserRegister) case...

> Is this handler correct?
AI: [consulting CLAUDE.md async discipline] This handler's early-return path never invokes the callback...
```

## Requirements

- Claude Code or ZCode
- A project that **depends on the drogon framework** (drogon installed as a library)
- Rules injection (SessionStart): works out of the box — needs a bash (Git Bash on Windows is what both hosts already require)
- Violation scanning (PostToolUse): optional, needs a Python 3 interpreter somewhere on the machine

## Repository structure

```
├── .claude-plugin/         # Claude Code manifest + marketplace entry
├── .zcode-plugin/          # ZCode manifest (mirrors .claude-plugin)
├── .github/workflows/
│   ├── ci.yml              # 3-OS matrix: structure + hooks + CLI smoke tests
│   └── publish.yml         # tag-triggered → PyPI + npm + GitHub Release
├── scripts/                # host-artifact generator, asset sync, consistency gate, smoke tests
├── hooks/
│   ├── hooks.json          # SessionStart + PostToolUse registration
│   ├── run-hook.cmd        # cross-platform polyglot launcher
│   ├── session-start       # pure-shell rules injection
│   ├── post-tool-use       # finds a Python 3, degrades gracefully
│   └── posttooluse.py      # violation scanner
├── skills/                 # 22 code-generation skills
├── docs/
│   ├── SKILL-AUTHORING.md  # skill authoring manual (fields, structure, sync checklist)
│   └── PROFESSIONALIZATION-REVIEW.md  # professionalization audit + improvement backlog
├── tests/                  # pytest: scanners, structure, rule fixtures, hook e2e
├── src/drogon_plugin/      # PyPI package (CLI installer)
├── npm/                    # npm package (CLI installer)
├── requirements-dev.txt    # pinned dev/CI dependencies (runtime deps: none)
├── CLAUDE.md               # rules layer
└── CHANGELOG.md
```

## License

MIT — see [LICENSE](LICENSE).
