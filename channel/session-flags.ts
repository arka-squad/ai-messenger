import { execFile } from 'node:child_process'

/** The MCP server name under which Claude Code knows this channel. */
export const SERVER = 'arkalabs-messenger-channel'
const FLAGS = ['--channels', '--dangerously-load-development-channels']
const SHELLS = new Set(['cmd', 'powershell', 'pwsh', 'sh', 'bash', 'zsh', 'dash', 'fish'])
/** The Claude process, plus at most two shells that may wrap it. */
const DEPTH = 3

/** The words of a command line; double quotes group a path that contains spaces. */
export function words(commandLine: string): string[] {
  const result: string[] = []
  let current = ''
  let started = false
  let quoted = false
  for (const char of commandLine) {
    if (char === '"') {
      quoted = !quoted
      started = true
    } else if (!quoted && /\s/.test(char)) {
      if (started) result.push(current)
      current = ''
      started = false
    } else {
      current += char
      started = true
    }
  }
  if (started) result.push(current)
  return result
}

/**
 * True when this command line starts a Claude session that delivers this server's channel
 * notifications: `--channels` or `--dangerously-load-development-channels`, either without a
 * list or with a list that names this server (`server:arkalabs-messenger-channel`).
 */
export function acceptsChannel(commandLine: string, server = SERVER): boolean {
  const list = words(commandLine)
  for (let index = 0; index < list.length; index++) {
    const word = list[index]
    const flag = FLAGS.find(candidate => word === candidate || word.startsWith(`${candidate}=`))
    if (!flag) continue
    const values = word.length > flag.length ? [word.slice(flag.length + 1)] : []
    while (index + 1 < list.length && !list[index + 1].startsWith('-')) values.push(list[++index])
    const names = values.flatMap(value => value.split(',')).map(name => name.trim()).filter(Boolean)
    if (!names.length || names.some(name => name === server || name.endsWith(`:${server}`))) return true
  }
  return false
}

/** True when the command line runs a shell, which may stand between Claude and this process. */
export function isShell(commandLine: string): boolean {
  const program = words(commandLine)[0] ?? ''
  const name = program.split(/[\\/]/).pop()?.toLowerCase().replace(/\.exe$/, '') ?? ''
  return SHELLS.has(name)
}

/** Decides from the command lines of the parent, grandparent… (nearest first). */
export function sessionAcceptsChannel(commandLines: string[]): boolean {
  for (const commandLine of commandLines.slice(0, DEPTH)) {
    if (acceptsChannel(commandLine)) return true
    if (!isShell(commandLine)) return false
  }
  return false
}

type Ancestor = { parent: number; commandLine: string }

/** `<parent pid>\t<command line>` lines, as the Windows query below prints them. */
export function parseTabbed(output: string): Ancestor[] {
  return output.split(/\r?\n/).flatMap(line => {
    const tab = line.indexOf('\t')
    if (tab < 0) return []
    return [{ parent: Number(line.slice(0, tab).trim()) || 0, commandLine: line.slice(tab + 1).trim() }]
  })
}

/** `ps -o ppid=,args=` output: the parent pid, then the command line. */
export function parsePs(output: string): Ancestor | null {
  const match = /^\s*(\d+)\s+(.*\S)\s*$/s.exec(output)
  return match ? { parent: Number(match[1]), commandLine: match[2] } : null
}

/** `wmic … get CommandLine,ParentProcessId /format:list` output. */
export function parseWmic(output: string): Ancestor | null {
  const commandLine = /^CommandLine=(.*)$/m.exec(output)?.[1]?.trim()
  const parent = Number(/^ParentProcessId=(\d+)/m.exec(output)?.[1])
  return commandLine ? { parent: parent || 0, commandLine } : null
}

function run(program: string, args: string[], timeout: number): Promise<string> {
  return new Promise((resolve, reject) => {
    execFile(program, args, { timeout, windowsHide: true, encoding: 'utf8', maxBuffer: 1 << 20 }, (error, stdout) => {
      if (error) reject(error)
      else resolve(stdout)
    })
  })
}

/** The command lines of `pid` and of its parents, nearest first; empty when unreadable. */
export async function commandLines(pid: number, depth = DEPTH): Promise<string[]> {
  if (!Number.isInteger(pid) || pid <= 0) return []
  if (process.platform === 'win32') return windowsCommandLines(pid, depth)
  const result: string[] = []
  for (let current = pid; current > 0 && result.length < depth;) {
    const ancestor = parsePs(await run('ps', ['-ww', '-o', 'ppid=,args=', '-p', String(current)], 3_000).catch(() => ''))
    if (!ancestor) break
    result.push(ancestor.commandLine)
    current = ancestor.parent
  }
  return result
}

async function windowsCommandLines(pid: number, depth: number): Promise<string[]> {
  const script = [
    '[Console]::OutputEncoding = [Text.Encoding]::UTF8',
    `$id = ${pid}`,
    `for ($i = 0; $i -lt ${depth} -and $id; $i++) {`,
    '  $p = Get-CimInstance Win32_Process -Filter "ProcessId=$id"',
    '  if (-not $p) { break }',
    '  "$($p.ParentProcessId)`t$($p.CommandLine)"',
    '  $id = $p.ParentProcessId',
    '}',
  ].join('\n')
  // An encoded script reaches PowerShell intact, whatever quoting the command line applies.
  const encoded = Buffer.from(script, 'utf16le').toString('base64')
  const output = await run('powershell.exe', ['-NoProfile', '-NonInteractive', '-EncodedCommand', encoded], 10_000)
    .catch(() => '')
  const found = parseTabbed(output)
  if (found.length) return found.map(ancestor => ancestor.commandLine)
  // Older systems without CIM cmdlets still answer through wmic.
  const result: string[] = []
  for (let current = pid; current > 0 && result.length < depth;) {
    const ancestor = parseWmic(await run('wmic', [
      'process', 'where', `ProcessId=${current}`, 'get', 'CommandLine,ParentProcessId', '/format:list',
    ], 5_000).catch(() => ''))
    if (!ancestor) break
    result.push(ancestor.commandLine)
    current = ancestor.parent
  }
  return result
}

/**
 * Whether the Claude session that started this process receives channel notifications.
 * Any failure reads as no: an unbound session is honestly reported as not reached.
 */
export async function parentAcceptsChannel(): Promise<boolean> {
  try {
    return sessionAcceptsChannel(await commandLines(process.ppid))
  } catch {
    return false
  }
}
