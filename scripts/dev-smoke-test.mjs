#!/usr/bin/env node
/**
 * npm 包端到端冒烟测试：验证 CLI 的 install / verify / uninstall 到临时目录。
 * 用法: node scripts/dev-smoke-test.mjs  （或 npm test）
 */
import { execFileSync } from 'node:child_process'
import { createRequire } from 'node:module'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'

const require = createRequire(import.meta.url)
const PKG = require('../npm/package.json')

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

  let r = run(['version'])
  if (r.status !== 0) throw new Error(`version 失败: ${r.stderr}`)
  console.log('✓ version')

  r = run(['install', '--target', target])
  if (r.status !== 0) throw new Error(`install 失败: ${r.stderr}`)
  for (const rel of ['.claude-plugin/plugin.json', 'CLAUDE.md', 'hooks/posttooluse.py']) {
    if (!fs.existsSync(path.join(target, rel)))
      throw new Error(`install 后缺少 ${rel}`)
  }
  const skills = fs
    .readdirSync(path.join(target, 'skills'), { withFileTypes: true })
    .filter((d) => d.isDirectory())
  if (skills.length !== 17) throw new Error(`skills 数 ${skills.length} != 17`)
  console.log('install OK')

  r = run(['verify', '--target', target])
  if (r.status !== 0 || !String(r.stdout).includes('✅ 通过'))
    throw new Error(`verify 未通过: ${r.stdout} ${r.stderr}`)
  console.log('verify OK')

  r = run(['uninstall', '--target', target])
  if (r.status !== 0 || fs.existsSync(path.join(target, 'skills')))
    throw new Error(`uninstall 未清空: ${r.stderr}`)
  console.log('uninstall OK')

  fs.rmSync(tmp, { recursive: true, force: true })
  console.log('✅ npm CLI 冒烟测试通过')
}

main().catch((e) => {
  console.error(`❌ ${e.message}`)
  process.exit(1)
})