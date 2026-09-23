#!/usr/bin/env node
/**
 * drogon-claude-plugin — CLI 安装器 (npm 发行版).
 * 把随包 assets/ 内的 drogon 插件资产安装到目标项目的 .drogon-plugin/ 子目录
 * （v0.2.0 起不再覆盖项目根文件），或校验 / 升级 / 卸载。
 *
 * 子命令:
 *   install   [--target DIR]
 *   verify    [--target DIR]
 *   upgrade   [--target DIR]
 *   uninstall [--target DIR]
 *   version
 */
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'
import crypto from 'node:crypto'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'

const require = createRequire(import.meta.url)
const PKG = require('../package.json')
const __dirname = path.dirname(fileURLToPath(import.meta.url))

const INSTALL_DIR = '.drogon-plugin'
const LEGACY_STAMP = '.drogon-claude-plugin-installed.json'
const STAMP = '.drogon-claude-plugin-v2.json'
// 落地后必须可执行的钩子文件(copyAssets 统一 chmod;POSIX 专用问题,Windows 为 no-op)
const HOOK_EXEC_FILES = [
  'hooks/run-hook.cmd',
  'hooks/session-start',
  'hooks/post-tool-use',
  'hooks/posttooluse.py',
]
const CLAUDE_MD_MARKER = '# Drogon 后端开发规则'
const EXPECTED_HOOK_FILES = ['hooks.json', 'run-hook.cmd', 'session-start', 'post-tool-use', 'posttooluse.py']
const EXPECTED_HOOK_EVENTS = 2

// 本 CLI 支持的命令(单一来源:dispatch 与 --capabilities 共用,能力契约测试据此比对)。
const COMMANDS = ['install', 'verify', 'upgrade', 'uninstall', 'version']

function cliVersion() {
  return PKG.version
}

// 受管资产条目。回退到源码树时**只**复制这些顶层条目 ——
// 否则会把 .git / node_modules / tests / scripts 整仓拖进用户项目
// （且会被 verify 当成受管文件）。与 scripts/sync-assets.mjs 的 ASSETS+FILES 对应，
// scripts/check-consistency.py 会校验两者等价。
const MANAGED_ENTRIES = new Set([
  'skills',
  'hooks',
  '.claude-plugin',
  '.zcode-plugin',
  '.codex-plugin',
  'CLAUDE.md',
  'AGENTS.md',
  'GEMINI.md',
  'gemini-extension.json',
])

// 是否处于"源码树回退"模式（打包后的正常安装不会有此状态）
let ASSETS_FALLBACK = false

/** 定位打包进 tarball 的 assets 根 */
function findAssets() {
  const packaged = path.join(__dirname, '..', 'assets')
  if (fs.existsSync(path.join(packaged, '.claude-plugin'))) {
    ASSETS_FALLBACK = false
    return packaged
  }
  // 源码树 fallback: 指向仓库根，但只复制受管资产（见 MANAGED_ENTRIES）
  const repoRoot = path.resolve(__dirname, '..', '..')
  if (fs.existsSync(path.join(repoRoot, '.claude-plugin', 'plugin.json'))) {
    ASSETS_FALLBACK = true
    return repoRoot
  }
  throw new Error(
    '未找到插件资产目录。请确认包安装完整（assets/），或从源码仓库运行。'
  )
}

/**
 * 解析并校验项目根目录。--target 由用户显式给出，但仍做边界防护：
 * 必须是已存在的目录，且拒绝文件系统根目录 / 用户主目录这类误操作高危目标。
 */
function resolveProjectDir(args) {
  const p = path.resolve(args.target || process.cwd())
  const st = fs.existsSync(p) ? fs.statSync(p) : null
  if (!st || !st.isDirectory()) {
    throw new Error(`目标目录不存在或不是目录: ${p}`)
  }
  if (p === path.parse(p).root) throw new Error(`拒绝在文件系统根目录操作: ${p}`)
  if (p === os.homedir()) throw new Error(`拒绝在用户主目录操作: ${p}`)
  return p
}

function listFiles(dir, base) {
  const out = []
  const isTop = dir === base
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    // 回退模式下顶层只允许受管条目（见 MANAGED_ENTRIES）
    if (ASSETS_FALLBACK && isTop && !MANAGED_ENTRIES.has(entry.name)) continue
    const full = path.join(dir, entry.name)
    const rel = path.relative(base, full)
    if (entry.isDirectory()) out.push(...listFiles(full, base))
    else out.push(rel)
  }
  return out
}

/** 技能数量单一事实源:实枚举随包 skills/ 目录(禁止硬编码)。 */
function skillCount(dir) {
  try {
    return fs.readdirSync(dir, { withFileTypes: true }).filter((d) => d.isDirectory()).length
  } catch {
    return 0
  }
}

function bundledSkillCount() {
  try {
    return skillCount(path.join(findAssets(), 'skills'))
  } catch {
    return 0
  }
}

function skillsOk(dir) {
  const n = skillCount(dir)
  const expected = bundledSkillCount()
  return expected ? n === expected : n > 0
}

const asPosix = (p) => p.split(path.sep).join('/')

/** 受管文件摘要(relpath -> sha256),用于安装后漂移检测。 */
function fileHashes(root, skip = new Set()) {
  const out = {}
  for (const rel of listFiles(root, root)) {
    const posix = asPosix(rel)
    if (skip.has(posix) || posix.split('/').includes('__pycache__')) continue
    out[posix] = crypto.createHash('sha256').update(fs.readFileSync(path.join(root, rel))).digest('hex')
  }
  return out
}

/** 已安装 bundle 的资产漂移检测(缺失/被改动/多余);无清单时静默跳过。 */
function driftProblems(root) {
  let recorded = null
  try {
    recorded = JSON.parse(fs.readFileSync(path.join(root, STAMP), 'utf-8')).hashes
  } catch {
    /* 旧版安装无 hashes 字段 */
  }
  if (!recorded || typeof recorded !== 'object') return []
  const current = fileHashes(root, new Set([STAMP]))
  const problems = []
  const missing = Object.keys(recorded).filter((k) => !(k in current)).sort()
  const modified = Object.keys(recorded).filter((k) => k in current && recorded[k] !== current[k]).sort()
  const added = Object.keys(current).filter((k) => !(k in recorded)).sort()
  if (missing.length) problems.push(`资产缺失 ${missing.length} 个（如 ${missing[0]}）；可 upgrade 重装`)
  if (modified.length) problems.push(`资产被改动 ${modified.length} 个（如 ${modified[0]}）；可 upgrade 覆盖`)
  if (added.length) problems.push(`资产目录存在未受管文件 ${added.length} 个（如 ${added[0]}）`)
  return problems
}

/** 把资产树复制到 targetRoot（rel 来自对 srcRoot 的枚举，不含用户输入）。 */
function copyAssets(srcRoot, targetRoot) {
  let count = 0
  for (const rel of listFiles(srcRoot, srcRoot)) {
    const dest = path.join(targetRoot, rel)
    fs.mkdirSync(path.dirname(dest), { recursive: true })
    fs.copyFileSync(path.join(srcRoot, rel), dest)
    count++
  }
  // 回归(P2):copyFileSync 不携带源 mode,Linux/macOS 上钩子脚本落地即丢
  // 可执行位 → 宿主执行 hooks command 时 Permission denied、静默失效。
  // Windows 上 chmod 的 x 位是 no-op,统一补 0o755。
  for (const rel of HOOK_EXEC_FILES) {
    const f = path.join(targetRoot, rel.split('/').join(path.sep))
    if (fs.existsSync(f)) fs.chmodSync(f, 0o755)
  }
  return count
}

function loadManifest(targetRoot) {
  const p = path.join(targetRoot, '.claude-plugin', 'plugin.json')
  if (!fs.existsSync(p)) throw new Error(`缺少插件清单: ${p}`)
  return JSON.parse(fs.readFileSync(p, 'utf-8'))
}

function pluginVersion(targetRoot) {
  try {
    const m = loadManifest(targetRoot)
    return String(m.version ?? '?')
  } catch {
    return null
  }
}

function installRootOf(project) {
  return path.join(project, INSTALL_DIR)
}

/** v0.1.x 根目录散装布局的归属签名：只有像"我们装的的东西"才允许清理。 */
function looksLikeOurLegacyLayout(project) {
  if (!fs.existsSync(path.join(project, LEGACY_STAMP))) return false
  const skillSig = fs.existsSync(path.join(project, 'skills', 'drogon-create-controller'))
  const hookSig = fs.existsSync(path.join(project, 'hooks', 'posttooluse.py'))
  return skillSig && hookSig
}

/** 返回 ['v2'|'legacy'|null, pluginRoot|null] */
function detectLayout(project) {
  const v2 = installRootOf(project)
  if (fs.existsSync(path.join(v2, '.claude-plugin', 'plugin.json'))) return ['v2', v2]
  if (looksLikeOurLegacyLayout(project)) return ['legacy', project]
  return [null, null]
}

/**
 * 清理 v0.1.x 散装在项目根的资产。逐项做归属校验（签名不匹配则跳过并告警），
 * 项目自身的 CLAUDE.md 等文件绝不会被误删。
 */
function removeLegacyLayout(project) {
  const removed = []
  const skipped = []
  if (!fs.existsSync(path.join(project, LEGACY_STAMP))) return { removed, skipped }

  // skills/ 与 hooks/：目录内含本插件特征文件才删
  for (const [dir, sig] of [
    ['skills', path.join('skills', 'drogon-create-controller', 'SKILL.md')],
    ['hooks', path.join('hooks', 'posttooluse.py')],
    ['.claude-plugin', path.join('.claude-plugin', 'plugin.json')],
    ['.zcode-plugin', path.join('.zcode-plugin', 'plugin.json')],
  ]) {
    const p = path.join(project, dir)
    if (fs.existsSync(p) && fs.existsSync(path.join(project, sig))) {
      fs.rmSync(p, { recursive: true, force: true })
      removed.push(dir)
    } else if (fs.existsSync(p)) {
      skipped.push(dir)
    }
  }

  // CLAUDE.md：首行是本插件标记才删，否则视为项目自有文件，保留并告警
  const md = path.join(project, 'CLAUDE.md')
  if (fs.existsSync(md)) {
    const firstLine = fs.readFileSync(md, 'utf-8').split('\n', 1)[0].trim()
    if (firstLine === CLAUDE_MD_MARKER) {
      fs.rmSync(md, { force: true })
      removed.push('CLAUDE.md')
    } else {
      skipped.push('CLAUDE.md（项目自有，已保留）')
    }
  }

  fs.rmSync(path.join(project, LEGACY_STAMP), { force: true })
  removed.push(LEGACY_STAMP)
  return { removed, skipped }
}

function printEnableHint(root) {
  const rel = path.basename(root)
  console.log('   启用方式（二选一）:')
  console.log(`     · Claude Code:  claude plugin install ${rel} --scope project`)
  console.log('     · ZCode:        在 ZCode 插件管理中添加 marketplace')
  console.log('       https://github.com/voidvec/drogon-claude-plugin 后安装 drogon 插件')
  console.log('     （已用 marketplace 安装过则跳过本地注册，直接 claude plugin update drogon）')
}

// ---------------------------------------------------------------------------

/** 回退到源码树时显式告警:用户应当知道复制来源不是打包资产。 */
function warnIfFallback() {
  if (ASSETS_FALLBACK) {
    console.warn('⚠️  未找到打包资产（npm/assets/），已回退到源码树 —— 只复制受管插件资产。')
    console.warn('    发布包不应出现此提示；如需正常路径请先运行 node scripts/sync-assets.mjs')
  }
}

function cmdInstall(args) {
  try {
    const project = resolveProjectDir(args)
    const src = findAssets()
    warnIfFallback()
    const root = installRootOf(project)
    if (fs.existsSync(root)) fs.rmSync(root, { recursive: true, force: true })
    const count = copyAssets(src, root)
    const manifestVer = pluginVersion(root) ?? '?'

    fs.writeFileSync(
      path.join(root, STAMP),
      JSON.stringify(
        {
          source: 'npm:drogon-claude-plugin',
          cli_version: cliVersion(),
          plugin_version: manifestVer,
          files: count,
          hashes: fileHashes(root, new Set([STAMP])),
        },
        null,
        2
      )
    )

    console.log(`✅ 已安装 drogon 插件资产到 ${root}`)
    console.log(`   复制 ${count} 个文件 · 插件版本 ${manifestVer} · ${bundledSkillCount()} 个技能`)
    printEnableHint(root)
    return 0
  } catch (e) {
    console.error(`❌ ${e.message}`)
    return 1
  }
}

function cmdVerify(args) {
  try {
    const project = resolveProjectDir(args)
    const [layout, target] = detectLayout(project)
    if (!layout) {
      console.error(`❌ ${project} 下未发现已安装的 drogon 插件（找 .drogon-plugin/ 或 v0.1.x 根目录布局）`)
      return 1
    }
    const manifest = loadManifest(target)
    const manifestVer = String(manifest.version ?? '?')
    const problems = []

    const skillsDir = path.join(target, 'skills')
    let skillNames = []
    if (!fs.existsSync(skillsDir)) {
      problems.push('缺少 skills/ 目录')
    } else {
      skillNames = fs
        .readdirSync(skillsDir, { withFileTypes: true })
        .filter((d) => d.isDirectory())
        .map((d) => d.name)
        .sort()
      if (!skillsOk(skillsDir))
        problems.push(`技能数 ${skillNames.length} != 随包 ${bundledSkillCount()}`)
      for (const n of skillNames) {
        if (!fs.existsSync(path.join(skillsDir, n, 'SKILL.md')))
          problems.push(`技能 ${n} 缺少 SKILL.md`)
      }
    }

    const hooksDir = path.join(target, 'hooks')
    if (!fs.existsSync(hooksDir)) {
      problems.push('缺少 hooks/ 目录')
    } else {
      for (const f of EXPECTED_HOOK_FILES) {
        if (!fs.existsSync(path.join(hooksDir, f))) problems.push(`缺少 hooks/${f}`)
      }
      const hooksJson = path.join(hooksDir, 'hooks.json')
      if (fs.existsSync(hooksJson)) {
        try {
          const data = JSON.parse(fs.readFileSync(hooksJson, 'utf-8'))
          const n = Object.keys(data.hooks ?? {}).length
          if (n !== EXPECTED_HOOK_EVENTS) problems.push(`hooks 事件数 ${n} != 预期 ${EXPECTED_HOOK_EVENTS}`)
        } catch {
          problems.push('hooks/hooks.json 不是合法 JSON')
        }
      }
    }

    if (!fs.existsSync(path.join(target, 'CLAUDE.md'))) problems.push('缺少 CLAUDE.md')
    if (!fs.existsSync(path.join(target, '.zcode-plugin', 'plugin.json')))
      problems.push('缺少 .zcode-plugin/plugin.json（ZCode 宿主清单）')
    problems.push(...driftProblems(target))

    console.log(`📦 drogon-claude-plugin 结构校验 — ${target}（布局: ${layout}）`)
    console.log(`   插件版本 : ${manifestVer}`)
    console.log(`   技能数   : ${skillNames.length}`)
    console.log(`   hooks    : ${EXPECTED_HOOK_FILES.length} 个文件 / ${EXPECTED_HOOK_EVENTS} 个事件`)
    if (problems.length) {
      console.log('   ❌ 发现问题:')
      for (const p of problems) console.log(`      - ${p}`)
      return 1
    }
    console.log('   ✅ 通过')
    return 0
  } catch (e) {
    console.error(`❌ ${e.message}`)
    return 1
  }
}

function cmdUpgrade(args) {
  try {
    const project = resolveProjectDir(args)
    const src = findAssets()
    warnIfFallback()
    const bundled = pluginVersion(src) ?? '?'
    let [layout, target] = detectLayout(project)

    if (layout === 'legacy') {
      const { removed, skipped } = removeLegacyLayout(project)
      console.log(`🔄 已清理 v0.1.x 根目录布局（${removed.length} 项，迁移到 ${INSTALL_DIR}/）`)
      for (const s of skipped) console.log(`   ⚠️  跳过 ${s}`)
      layout = null
    }

    if (layout === 'v2') {
      const current = pluginVersion(target)
      if (current === bundled) {
        console.log(`✅ 已是最新版本 ${current}（无需升级）`)
        return 0
      }
      console.log(`⬆️  ${current} → ${bundled}`)
      fs.rmSync(target, { recursive: true, force: true })
    } else {
      console.log(`⬆️  安装 ${bundled}`)
    }

    const root = installRootOf(project)
    const count = copyAssets(src, root)
    fs.writeFileSync(
      path.join(root, STAMP),
      JSON.stringify(
        {
          source: 'npm:drogon-claude-plugin',
          cli_version: cliVersion(),
          plugin_version: bundled,
          files: count,
          hashes: fileHashes(root, new Set([STAMP])),
        },
        null,
        2
      )
    )
    console.log(`✅ 已升级到 ${root}（${count} 个文件 · ${bundled}）`)
    printEnableHint(root)
    return 0
  } catch (e) {
    console.error(`❌ ${e.message}`)
    return 1
  }
}

function cmdUninstall(args) {
  const project = resolveProjectDir(args)
  const removed = []

  const root = installRootOf(project)
  if (fs.existsSync(root)) {
    fs.rmSync(root, { recursive: true, force: true })
    removed.push(INSTALL_DIR)
  }

  const legacy = removeLegacyLayout(project)
  removed.push(...legacy.removed)

  if (removed.length) {
    console.log(`🗑  已从 ${project} 移除: ${removed.join(', ')}`)
    for (const s of legacy.skipped) console.log(`   ⚠️  跳过 ${s}`)
    console.log('   注意：如曾用 claude plugin install 注册，另需 claude plugin uninstall drogon')
  } else {
    console.log(`ℹ️   未在 ${project} 发现插件资产`)
  }
  return 0
}

function cmdVersion() {
  let pluginVer = '?'
  try {
    const m = JSON.parse(
      fs.readFileSync(path.join(findAssets(), '.claude-plugin', 'plugin.json'), 'utf-8')
    )
    pluginVer = m.version ?? '?'
  } catch {
    /* noop */
  }
  console.log(`drogon-claude-plugin (npm) v${cliVersion()} | 内置插件 v${pluginVer}`)
  return 0
}

// ---------------------------------------------------------------------------

const HELP = `drogon-claude-plugin — drogon 插件安装器 (npm, Claude Code / ZCode 双宿主)

用法:
  drogon-claude-plugin install   [--target DIR]
  drogon-claude-plugin verify    [--target DIR]
  drogon-claude-plugin upgrade   [--target DIR]
  drogon-claude-plugin uninstall [--target DIR]
  drogon-claude-plugin version
`

function main() {
  const argv = process.argv.slice(2)
  const command = argv[0] ?? 'help'

  if (command === 'version' || command === '-v' || command === '--version') {
    return cmdVersion()
  }
  if (command === '--capabilities') {
    // 机器可读的能力声明:供 scripts/plugin-capabilities.json 的契约测试比对
    console.log(JSON.stringify({ cli: 'npm', version: cliVersion(), commands: COMMANDS }))
    return 0
  }
  if (command === 'help' || command === '-h' || command === '--help') {
    console.log(HELP)
    return 0
  }
  if (!COMMANDS.includes(command)) {
    console.error(`未知命令: ${command}`)
    console.error(HELP)
    return 2
  }

  const args = { command }
  for (let i = 1; i < argv.length; i++) {
    const a = argv[i]
    if (a === '--target') args.target = argv[++i]
    else {
      console.error(`未知参数: ${a}`)
      return 2
    }
  }

  try {
    if (command === 'install') return cmdInstall(args)
    if (command === 'verify') return cmdVerify(args)
    if (command === 'upgrade') return cmdUpgrade(args)
    return cmdUninstall(args)
  } catch (e) {
    console.error(`❌ ${e.message}`)
    return 1
  }
}

process.exit(main())
