import { execFileSync } from 'node:child_process'
import { mkdirSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = fileURLToPath(new URL('..', import.meta.url))
const rust = execFileSync('rustc', ['-vV'], { encoding: 'utf8' })
const target = rust.match(/^host: (.+)$/m)?.[1]
if (!target) throw new Error('Rust host target not found')

const directory = join(root, 'src-tauri', 'binaries')
const extension = target.includes('windows') ? '.exe' : ''
const output = join(directory, `messenger-claude-channel-${target}${extension}`)
mkdirSync(directory, { recursive: true })
execFileSync('bun', ['build', '--compile', join(root, 'channel', 'claude-channel.ts'), '--outfile', output], {
  cwd: root,
  stdio: 'inherit',
})

console.log(`Claude channel: ${output}`)
