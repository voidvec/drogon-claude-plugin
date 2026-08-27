#!/usr/bin/env node
/**
 * 同步插件资产到 npm 包的 assets/ 目录.
 * 在 `npm pack` 前由 prepack 钩子触发（package.json 已配置）。
 * 用法: node scripts/sync-assets.mjs [--check]
 */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const REPO_ROOT = path.resolve(__dirname, '..')
const ASSETS = ['skills', 'hooks', '.claude-plugin']
const FILES = ['CLAUDE.md']
const DEST = path.join(REPO_ROOT, 'npm', 'assets')

function collect(root) {
  const out = []
  for (const entry of fs.readdirSync(root, { withFileTypes: true })) {
    const full = path.join(root, entry.name)
    if (entry.isDirectory()) out.push(...collect(full))
    else out.push(full)
  }
  return out
}

function sync() {
  fs.rmSync(DEST, { recursive: true, force: true })
  fs.mkdirSync(DEST, { recursive: true })
  let count = 0
  for (const name of ASSETS) {
    const src = path.join(REPO_ROOT, name)
    if (fs.existsSync(src)) {
      fs.cpSync(src, path.join(DEST, name), { recursive: true })
      count += collect(path.join(DEST, name)).length
    }
  }
  for (const name of FILES) {
    const src = path.join(REPO_ROOT, name)
    if (fs.existsSync(src)) {
      fs.copyFileSync(src, path.join(DEST, name))
      count++
    }
  }
  console.log(`✅ 已同步 ${count} 个资产文件到 npm/assets`)
}

function check() {
  for (const name of ASSETS) {
    const src = path.join(REPO_ROOT, name)
    const dst = path.join(DEST, name)
    if (!fs.existsSync(dst)) return false
    const srcFiles = collect(src).map((f) => path.relative(src, f)).sort()
    const dstFiles = collect(dst).map((f) => path.relative(dst, f)).sort()
    if (srcFiles.length !== dstFiles.length) return false
    for (let i = 0; i < srcFiles.length; i++) {
      if (srcFiles[i] !== dstFiles[i]) return false
      const a = fs.readFileSync(path.join(src, srcFiles[i]))
      const b = fs.readFileSync(path.join(dst, dstFiles[i]))
      if (!a.equals(b)) return false
    }
  }
  // CLAUDE.md
  const src = path.join(REPO_ROOT, 'CLAUDE.md')
  const dst = path.join(DEST, 'CLAUDE.md')
  if (!fs.existsSync(dst)) return false
  if (!fs.readFileSync(src).equals(fs.readFileSync(dst))) return false
  return true
}

const isCheck = process.argv.includes('--check')
if (isCheck) {
  const ok = check()
  if (ok === true) {
    console.log('✅ npm 资产与源码同步')
    process.exit(0)
  }
  console.log(`❌ npm 资产与源码不一致: ${typeof ok === 'string' ? ok : ''}`)
  process.exit(1)
} else {
  sync()
}