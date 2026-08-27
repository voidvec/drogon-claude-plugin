#!/usr/bin/env node
/**
 * drogon-claude-plugin — CLI 安装器 (npm 发行版).
 * 把随包 assets/ 内的 drogon 插件资产安装到目标项目，或校验 / 卸载。
 *
 * 子命令:
 *   install   [--target DIR] [--scope project|user|local]
 *   verify    [--target DIR]
 *   uninstall [--target DIR]
 *   version
 */
import { execFileSync } from 'node:child_process'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'

const require = createRequire(import.meta.url)
const PKG = require('../package.json')
const __dirname = path.dirname(fileURLToPath(import.meta.url))

const ASSET_DIRS = ['skills', 'hooks', '.claude-plugin']
const ASSET_FILES = ['CLAUDE.md']
const EXPECTED_SKILLS = 17
const EXPECTED_HOOKS = 2

const SCOPE_DIRS = {
  user: path.join(os.homedir(), '.claude', 'plugins'),
  local: path.join(os.homedir(), '.claude', 'plugins'),
  project: null,
}

function cliVersion() {
  return PKG.version
}

/** 定位打包进 tarball 的 assets 根 */
function findAssets() {
  const packaged = path.join(__dirname, '..', 'assets')
  if (fs.existsSync(path.join(packaged, '.claude-plugin'))) return packaged
  // 源码树 fallback: 直接指向仓库根
  const repoRoot = path.resolve(__dirname, '..', '..')
  if (fs.existsSync(path.join(repoRoot, '.claude-plugin', 'plugin.json'))) return repoRoot
  throw new Error(
    '未找到插件资产目录。请确认包安装完整（assets/），或从源码仓库运行。'
  )
}

function listFiles(dir, base) {
  const out = []
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name)
    const rel = path.relative(base, full)
    if (entry.isDirectory()) out.push(...listFiles(full, base))
    else out.push(rel)
  }
  return out
}

function copyAssets(srcRoot, targetRoot) {
  let count = 0
  for (const rel of listFiles(srcRoot, srcRoot)) {
    const src = path.join(srcRoot, rel)
    const dest = path.join(targetRoot, rel)
    fs.mkdirSync(path.dirname(dest), { recursive: true })
    fs.copyFileSync(src, dest)
    count++
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
    return '?'
  }
}

function resolveTarget(args) {
  if (args.target) return path.resolve(args.target)
  if (args.scope) {
    if (args.scope === 'project') return process.cwd()
    if (SCOPE_DIRS[args.scope]) return path.resolve(SCOPE_DIRS[args.scope])
  }
  return process.cwd()
}

// ---------------------------------------------------------------------------

function cmdInstall(args) {
  let target
  try {
    target = resolveTarget(args)
    const src = findAssets()
    const count = copyAssets(src, target)
    const manifest = loadManifest(target)

    const stamp = path.join(target, '.drogon-claude-plugin-installed.json')
    fs.writeFileSync(
      stamp,
      JSON.stringify(
        {
          source: 'npm:drogon-claude-plugin',
          cli_version: cliVersion(),
          plugin_version: manifest.version ?? '?',
          files: count,
        },
        null,
        2
      )
    )

    console.log(`✅ 已安装 drogon 插件资产到 ${target}`)
    console.log(`   复制 ${count} 个文件 · 插件版本 ${manifest.version ?? '?'}`)
    console.log('   下一步:')
    console.log('     1) cd <你的 drogon 项目>')
    console.log('     2) claude plugin install ../drogon-claude-plugin --scope project')
    console.log('       （或如果已通过 marketplace 添加: claude plugin install drogon）')
    return 0
  } catch (e) {
    console.error(`❌ ${e.message}`)
    return 1
  }
}

function cmdVerify(args) {
  let target
  try {
    target = resolveTarget(args)
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
      if (skillNames.length !== EXPECTED_SKILLS)
        problems.push(`技能数 ${skillNames.length} != 预期 ${EXPECTED_SKILLS}`)
      for (const n of skillNames) {
        if (!fs.existsSync(path.join(skillsDir, n, 'SKILL.md')))
          problems.push(`技能 ${n} 缺少 SKILL.md`)
      }
    }

    const hooksDir = path.join(target, 'hooks')
    if (!fs.existsSync(hooksDir)) {
      problems.push('缺少 hooks/ 目录')
    } else {
      const hooksJson = path.join(hooksDir, 'hooks.json')
      if (!fs.existsSync(hooksJson)) problems.push('缺少 hooks/hooks.json')
      else {
        try {
          const data = JSON.parse(fs.readFileSync(hooksJson, 'utf-8'))
          const n = Object.keys(data.hooks ?? {}).length
          if (n !== EXPECTED_HOOKS) problems.push(`hooks 数 ${n} != 预期 ${EXPECTED_HOOKS}`)
        } catch {
          problems.push('hooks/hooks.json 不是合法 JSON')
        }
      }
      if (!fs.existsSync(path.join(hooksDir, 'posttooluse.py')))
        problems.push('缺少 hooks/posttooluse.py')
    }

    if (!fs.existsSync(path.join(target, 'CLAUDE.md')))
      problems.push('缺少 CLAUDE.md')

    console.log(`📦 drogon-claude-plugin 结构校验 — ${target}`)
    console.log(`   插件版本 : ${manifestVer}`)
    console.log(`   技能数   : ${skillNames.length}`)
    console.log(`   hooks    : ${EXPECTED_HOOKS} (SessionStart + PostToolUse)`)
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

function cmdUninstall(args) {
  const target = resolveTarget(args)
  const removed = []
  for (const name of [...ASSET_DIRS, ...ASSET_FILES]) {
    const p = path.join(target, name)
    if (fs.existsSync(p)) {
      fs.rmSync(p, { recursive: true, force: true })
      removed.push(name)
    }
  }
  const stamp = path.join(target, '.drogon-claude-plugin-installed.json')
  if (fs.existsSync(stamp)) {
    fs.rmSync(stamp, { force: true })
    removed.push('.drogon-claude-plugin-installed.json')
  }
  if (removed.length) console.log(`🗑  已从 ${target} 移除: ${removed.join(', ')}`)
  else console.log(`ℹ️   未在 ${target} 发现插件资产`)
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

const HELP = `drogon-claude-plugin — drogon Claude Code 插件安装器 (npm)

用法:
  drogon-claude-plugin install   [--target DIR] [--scope project|user|local]
  drogon-claude-plugin verify    [--target DIR]
  drogon-claude-plugin uninstall [--target DIR]
  drogon-claude-plugin version
`

function main() {
  const argv = process.argv.slice(2)
  const command = argv[0] ?? 'help'

  if (command === 'version' || command === '-v' || command === '--version') {
    return cmdVersion()
  }
  if (command === 'help' || command === '-h' || command === '--help') {
    console.log(HELP)
    return 0
  }
  if (!['install', 'verify', 'uninstall'].includes(command)) {
    console.error(`未知命令: ${command}`)
    console.error(HELP)
    return 2
  }

  const args = { command }
  for (let i = 1; i < argv.length; i++) {
    const a = argv[i]
    if (a === '--target') args.target = argv[++i]
    else if (a === '--scope') args.scope = argv[++i]
    else {
      console.error(`未知参数: ${a}`)
      return 2
    }
  }

  try {
    if (command === 'install') return cmdInstall(args)
    if (command === 'verify') return cmdVerify(args)
    return cmdUninstall(args)
  } catch (e) {
    console.error(`❌ ${e.message}`)
    return 1
  }
}

process.exit(main())