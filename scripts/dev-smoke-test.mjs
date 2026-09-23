#!/usr/bin/env node
/**
 * npm 包端到端冒烟测试：验证 CLI 的 install / verify / upgrade / uninstall
 * 到临时目录（v0.2.0 布局：资产在 .drogon-plugin/，项目根文件不受影响）。
 * 用法: node scripts/dev-smoke-test.mjs  （或 npm test）
 */
import { execFileSync } from 'node:child_process'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'

const require = createRequire(import.meta.url)
const PKG = require('../npm/package.json')

// 技能数单一事实源:源仓库 skills/ 目录(不依赖 cwd,禁止硬编码)。
const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const EXPECTED_SKILLS = fs
  .readdirSync(path.join(REPO, 'skills'), { withFileTypes: true })
  .filter((d) => d.isDirectory()).length

const EXE = path.resolve(
  process.cwd(),
  'node_modules',
  '.bin',
  process.platform === 'win32' ? 'drogon-claude-plugin.cmd' : 'drogon-claude-plugin'
)

function run(args, opts = {}) {
  const bin = fs.existsSync(EXE) ? EXE : 'drogon-claude-plugin'
  const r = (() => {
    try {
      return execFileSync(bin, args, {
        encoding: 'utf-8',
        stdio: ['ignore', 'pipe', 'pipe'],
        ...opts,
      })
    } catch (e) {
      return { status: e.status, stdout: e.stdout, stderr: e.stderr }
    }
  })()
  if (typeof r === 'string') return { status: 0, stdout: r, stderr: '' }
  return r
}

async function main() {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'drogon-npm-smoke-'))
  const target = path.join(tmp, 'proj')
  fs.mkdirSync(target, { recursive: true })
  const plugin = path.join(target, '.drogon-plugin')

  // 项目自有文件：安装/升级/卸载全程不得触碰
  fs.writeFileSync(path.join(target, 'CLAUDE.md'), '# 我的项目\n', 'utf-8')

  let r = run(['version'])
  if (r.status !== 0) throw new Error(`version 失败: ${r.stderr}`)
  console.log('✓ version')

  r = run(['install', '--target', target])
  if (r.status !== 0) throw new Error(`install 失败: ${r.stderr}`)
  for (const rel of [
    '.claude-plugin/plugin.json',
    '.zcode-plugin/plugin.json',
    'CLAUDE.md',
    'hooks/hooks.json',
    'hooks/run-hook.cmd',
    'hooks/session-start',
    'hooks/post-tool-use',
    'hooks/posttooluse.py',
  ]) {
    if (!fs.existsSync(path.join(plugin, rel)))
      throw new Error(`install 后缺少 ${rel}`)
  }
  const skills = fs
    .readdirSync(path.join(plugin, 'skills'), { withFileTypes: true })
    .filter((d) => d.isDirectory())
  if (skills.length !== EXPECTED_SKILLS)
    throw new Error(`skills 数 ${skills.length} != 源仓库 ${EXPECTED_SKILLS}`)
  if (fs.readFileSync(path.join(target, 'CLAUDE.md'), 'utf-8') !== '# 我的项目\n')
    throw new Error('install 覆盖了项目自有 CLAUDE.md')
  console.log('install OK')

  r = run(['verify', '--target', target])
  if (r.status !== 0 || !String(r.stdout).includes('✅ 通过'))
    throw new Error(`verify 未通过: ${r.stdout} ${r.stderr}`)
  console.log('verify OK')

  r = run(['upgrade', '--target', target])
  if (r.status !== 0 || !String(r.stdout).includes('已是最新'))
    throw new Error(`upgrade(同版本) 未通过: ${r.stdout} ${r.stderr}`)
  console.log('upgrade OK')

  r = run(['uninstall', '--target', target])
  if (r.status !== 0 || fs.existsSync(plugin))
    throw new Error(`uninstall 未清空: ${r.stderr}`)
  if (fs.readFileSync(path.join(target, 'CLAUDE.md'), 'utf-8') !== '# 我的项目\n')
    throw new Error('uninstall 误删了项目自有 CLAUDE.md')
  console.log('uninstall OK')

  fs.rmSync(tmp, { recursive: true, force: true })
  console.log('✅ npm CLI 冒烟测试通过')
}

main().catch((e) => {
  console.error(`❌ ${e.message}`)
  process.exit(1)
})
