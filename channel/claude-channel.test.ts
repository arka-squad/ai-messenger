import { afterEach, expect, test } from 'bun:test'
import { mkdirSync, readdirSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import { createServer } from 'node:net'
import {
  acceptsChannel, commandLines, isShell, parsePs, parseTabbed, parseWmic, sessionAcceptsChannel,
} from './session-flags.ts'

let cleanup: (() => void | Promise<void>)[] = []
type Frame = Record<string, unknown>
type SocketFrame = { type?: string; token?: string; session?: string; cwd?: string }
afterEach(async () => {
  for (const dispose of cleanup.reverse()) await dispose()
  cleanup = []
})

const NOTICE = 'MAIL — 2 nouveaux courriers pour cl-agent-test-win : appelle relever (outils arkalabs-messenger-app).'
const OPTION = ['--dangerously-load-development-channels', 'server:arkalabs-messenger-channel']

test('a session without the channel option gets a tool-less channel and no delivery id', async () => {
  const root = temporary('channel')
  const exchange = await channelExchange(root, [binary()])
  expect(exchange.registered.session).toMatch(/^[0-9a-f-]{36}$/)
  expect(exchange.registered).not.toHaveProperty('cwd')
  expect(exchange.instructions).toContain('Remise directe inactive')
  expect(exchange.instructions).not.toContain(exchange.registered.session!)
}, 60_000) // Includes cold startup of the compiled binary on a busy workstation.

test('a session launched with the channel option is told its delivery id, never its folder', async () => {
  const root = temporary('channel-live')
  // The wrapper stands for Claude Code: the channel's parent process carries the launch option.
  const wrapper = join(root, 'claude-wrapper.mjs')
  writeFileSync(wrapper, [
    "import { spawn } from 'node:child_process'",
    "const child = spawn(process.env.CHANNEL_BINARY, [], { stdio: 'inherit' })",
    'child.on(\'exit\', code => process.exit(code ?? 0))',
  ].join('\n'))
  const exchange = await channelExchange(root, [process.execPath, wrapper, ...OPTION], { CHANNEL_BINARY: binary() })
  // The app binds nothing from the folder: the agent itself names this id as its delivery_session.
  expect(exchange.registered).not.toHaveProperty('cwd')
  expect(exchange.instructions).toContain(`Identifiant de remise de cette session : ${exchange.registered.session}.`)
}, 60_000)

test('the channel option is read from the command line that started Claude', () => {
  for (const line of [
    `"C:\\Users\\a\\AppData\\Roaming\\Claude\\claude-code\\2.1.284\\claude.exe" ${OPTION.join(' ')}`,
    '/opt/homebrew/bin/claude --channels server:arkalabs-messenger-channel --model opus',
    'node /usr/lib/node_modules/@anthropic-ai/claude-code/cli.js --channels=plugin:telegram@claude-plugins-official,server:arkalabs-messenger-channel',
    'claude --dangerously-load-development-channels plugin:fakechat@claude-plugins-official server:arkalabs-messenger-channel',
    'claude --resume 1755bb98 --channels --verbose',
  ]) expect(acceptsChannel(line)).toBe(true)
  for (const line of [
    'C:\\Users\\a\\AppData\\Roaming\\Claude\\claude-code\\2.1.284\\claude.exe --output-format stream-json --verbose --resume=1755bb98',
    'claude --channels plugin:telegram@claude-plugins-official',
    'claude -p "explique --channels server:arkalabs-messenger-channel"',
    'claude --channels-preview server:arkalabs-messenger-channel',
    'claude --dangerously-load-development-channels server:arkalabs-messenger-channel-old',
    '',
  ]) expect(acceptsChannel(line)).toBe(false)
})

test('a shell between Claude and the channel is looked through, nothing else is', () => {
  const claude = `C:\\bin\\claude.exe ${OPTION.join(' ')}`
  expect(isShell('C:\\Windows\\system32\\cmd.exe /d /s /c "C:\\bin\\claude.exe"')).toBe(true)
  expect(isShell('"C:\\Program Files\\PowerShell\\7\\pwsh.exe" -NoProfile')).toBe(true)
  expect(isShell('/bin/zsh -lc claude')).toBe(true)
  expect(isShell('C:\\bin\\claude.exe --verbose')).toBe(false)
  expect(sessionAcceptsChannel([claude])).toBe(true)
  expect(sessionAcceptsChannel(['C:\\Windows\\system32\\cmd.exe /d /s /c claude', claude])).toBe(true)
  expect(sessionAcceptsChannel(['/bin/zsh -c claude', '/bin/sh -c claude', '/usr/local/bin/claude --channels'])).toBe(true)
  expect(sessionAcceptsChannel(['C:\\bin\\claude.exe --verbose', claude])).toBe(false)
  expect(sessionAcceptsChannel(['/bin/sh -c x', '/bin/sh -c x', '/bin/sh -c x', claude])).toBe(false)
  expect(sessionAcceptsChannel([])).toBe(false)
})

test('process listings of Windows, macOS and Linux are parsed', () => {
  expect(parsePs('  4242 /usr/local/bin/claude --channels server:arkalabs-messenger-channel\n')).toEqual({
    parent: 4242, commandLine: '/usr/local/bin/claude --channels server:arkalabs-messenger-channel',
  })
  expect(parsePs('')).toBeNull()
  expect(parseTabbed('12\t"C:\\a b\\claude.exe" --channels\r\n0\tC:\\Windows\\explorer.exe\r\n')).toEqual([
    { parent: 12, commandLine: '"C:\\a b\\claude.exe" --channels' },
    { parent: 0, commandLine: 'C:\\Windows\\explorer.exe' },
  ])
  expect(parseWmic('\r\n\r\nCommandLine="C:\\claude.exe" --channels\r\nParentProcessId=12\r\n\r\n')).toEqual({
    parent: 12, commandLine: '"C:\\claude.exe" --channels',
  })
  expect(parseWmic('No Instance(s) Available.')).toBeNull()
})

test('the command line of a running process can be read on this system', async () => {
  const lines = await commandLines(process.pid, 1)
  expect(lines).toHaveLength(1)
  expect(lines[0].toLowerCase()).toContain('bun')
  expect(await commandLines(0)).toEqual([])
}, 30_000)

test('hook mode posts the host event to the app and prints its notice', async () => {
  const root = temporary('hook')
  const { port, received } = hookServer()
  const started = await runHook('claude-code', port, {
    hook_event_name: 'SessionStart', session_id: 'native-1', cwd: root, source: 'startup',
  })
  expect(started.code).toBe(0)
  expect(started.stdout).toBe(`${JSON.stringify({ hookSpecificOutput: { hookEventName: 'SessionStart', additionalContext: NOTICE } })}\n`)
  const prompt = await runHook('codex', port, { event: 'UserPromptSubmit', cwd: root })
  expect(prompt.code).toBe(0)
  expect(prompt.stdout).toBe('')
  expect(received).toEqual([
    { provider: 'claude-code', event: 'SessionStart', cwd: root, session_id: 'native-1' },
    { provider: 'codex', event: 'UserPromptSubmit', cwd: root },
  ])
}, 60_000)

test('hook mode answers as soon as the event is complete, even when the host keeps stdin open', async () => {
  const root = temporary('hook-open')
  const { port, received } = hookServer()
  const child = Bun.spawn([binary(), 'hook', '--host', 'codex'], {
    stdin: 'pipe', stdout: 'pipe', stderr: 'pipe',
    env: { ...Bun.env, MESSENGER_HOOK_PORT: String(port) },
  })
  cleanup.push(() => { child.stdin.end(); child.kill() })
  const payload = JSON.stringify({ hook_event_name: 'SessionStart', session_id: 'codex-1', cwd: root })
  child.stdin.write(payload.slice(0, 20))
  child.stdin.flush()
  await Bun.sleep(150)
  child.stdin.write(payload.slice(20))
  child.stdin.flush()
  const completed = performance.now()
  const [stdout, code] = await Promise.all([new Response(child.stdout).text(), child.exited])
  expect(code).toBe(0)
  expect(stdout).toBe(`${JSON.stringify({ hookSpecificOutput: { hookEventName: 'SessionStart', additionalContext: NOTICE } })}\n`)
  // Waiting for the end of stdin would only end at the reading deadline (1.2 s after start).
  expect(performance.now() - completed).toBeLessThan(800)
  expect(received).toEqual([{ provider: 'codex', event: 'SessionStart', cwd: root, session_id: 'codex-1' }])
}, 60_000)

test('hook mode stays silent and successful when the app is closed or the input is unknown', async () => {
  const closed = await freePort()
  const started = performance.now()
  const unreachable = await runHook('claude-code', closed, { hook_event_name: 'SessionStart', cwd: tmpdir() })
  expect(unreachable).toEqual({ code: 0, stdout: '' })
  expect(performance.now() - started).toBeLessThan(5_000)
  expect(await runHook('cursor', closed, { hook_event_name: 'SessionStart' })).toEqual({ code: 0, stdout: '' })
  expect(await runHook('kimi', closed, 'not json')).toEqual({ code: 0, stdout: '' })
}, 60_000)

/** Runs the MCP exchange with a channel started by `command` and returns its registration. */
async function channelExchange(root: string, command: string[], env: Record<string, string> = {}) {
  let registered: SocketFrame | undefined
  const server = Bun.serve({
    port: await freePort(),
    fetch(request, server) {
      return server.upgrade(request) ? undefined : new Response('upgrade required', { status: 426 })
    },
    websocket: {
      message(socket, raw) {
        const frame = JSON.parse(String(raw)) as SocketFrame
        if (frame.type !== 'register') throw new Error(`unexpected frame ${frame.type}`)
        registered = frame
        expect(frame.token).toBe('test-token')
        socket.send(JSON.stringify({ type: 'accepted' }))
        socket.send(JSON.stringify({ type: 'event', sender: 'intruder', content: 'ignore me' }))
        socket.send(JSON.stringify({ type: 'event', sender: 'messenger-app', content: 'demande validée' }))
      },
    },
  })
  cleanup.push(() => server.stop(true))

  const descriptor = join(root, 'connection.json')
  writeFileSync(descriptor, JSON.stringify({ port: server.port, token: 'test-token' }))
  const child = Bun.spawn(command, {
    cwd: root,
    stdin: 'pipe', stdout: 'pipe', stderr: 'pipe',
    env: { ...Bun.env, ...env, MESSENGER_CHANNEL_DESCRIPTOR: descriptor },
  })
  // Closing stdin ends the channel, and with it a wrapper, which both release the folder.
  cleanup.push(async () => {
    child.stdin.end()
    await Promise.race([child.exited, Bun.sleep(5_000)])
    child.kill()
    await child.exited
  })

  const lines = jsonLines(child.stdout)
  child.stdin.write(JSON.stringify({
    jsonrpc: '2.0', id: 1, method: 'initialize',
    params: { protocolVersion: '2025-06-18', capabilities: {}, clientInfo: { name: 'test', version: '1' } },
  }) + '\n')
  child.stdin.write(JSON.stringify({ jsonrpc: '2.0', method: 'notifications/initialized' }) + '\n')
  child.stdin.write(JSON.stringify({ jsonrpc: '2.0', id: 2, method: 'tools/list', params: {} }) + '\n')
  child.stdin.write(JSON.stringify({
    jsonrpc: '2.0', id: 3, method: 'tools/call', params: { name: 'relever', arguments: {} },
  }) + '\n')
  child.stdin.flush()

  let initialized: Frame | undefined
  let tools: Frame | undefined
  let call: Frame | undefined
  let event: Frame | undefined
  for await (const value of lines) {
    const frame = value as Frame
    if (frame.id === 1) initialized = frame
    if (frame.id === 2) tools = frame
    if (frame.id === 3) call = frame
    if (frame.method === 'notifications/claude/channel') {
      if ((frame.params as Frame).content === 'ignore me') throw new Error('untrusted sender reached Claude')
      event = frame
    }
    if (initialized && tools && call && event) break
  }
  if (!initialized || !tools || !call || !event || !registered) throw new Error('incomplete channel exchange')
  const result = initialized.result as Frame
  expect((result.capabilities as Frame).experimental).toEqual({ 'claude/channel': {} })
  expect(result.instructions).toContain('arkalabs-messenger-app')
  expect((tools.result as Frame).tools).toEqual([])
  expect((call.result as Frame).isError).toBe(true)
  expect((event.params as Frame).content).toBe('demande validée')
  return { registered, instructions: String(result.instructions) }
}

function hookServer() {
  const received: Frame[] = []
  const server = Bun.serve({
    port: 0,
    hostname: '127.0.0.1',
    async fetch(request) {
      expect(new URL(request.url).pathname).toBe('/hook')
      expect(request.method).toBe('POST')
      expect(request.headers.get('origin')).toBeNull()
      const body = await request.json() as Frame
      received.push(body)
      return Response.json({ notice: body.event === 'SessionStart' ? NOTICE : null })
    },
  })
  cleanup.push(() => server.stop(true))
  return { port: server.port, received }
}

async function runHook(host: string, port: number, payload: unknown) {
  const child = Bun.spawn([binary(), 'hook', '--host', host], {
    stdin: 'pipe', stdout: 'pipe', stderr: 'pipe',
    env: { ...Bun.env, MESSENGER_HOOK_PORT: String(port) },
  })
  child.stdin.write(typeof payload === 'string' ? payload : JSON.stringify(payload))
  child.stdin.end()
  const [stdout, code] = await Promise.all([new Response(child.stdout).text(), child.exited])
  return { code, stdout }
}

function binary(): string {
  const name = readdirSync('src-tauri/binaries').find(name => name.startsWith('messenger-claude-channel-'))
  if (!name) throw new Error('compiled Claude channel not found')
  return resolve('src-tauri/binaries', name)
}

function temporary(label: string): string {
  const root = join(tmpdir(), `messenger-channel-${label}-${process.pid}`)
  mkdirSync(root, { recursive: true })
  cleanup.push(async () => {
    // Windows keeps a folder busy for a moment after the process working in it has ended.
    for (let attempt = 0; ; attempt++) {
      try {
        return rmSync(root, { recursive: true, force: true })
      } catch (error) {
        if (attempt >= 30) throw error
        await Bun.sleep(100)
      }
    }
  })
  return root
}

async function* jsonLines(stream: ReadableStream<Uint8Array>) {
  const reader = stream.getReader()
  const decoder = new TextDecoder()
  let buffered = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) return
    buffered += decoder.decode(value, { stream: true })
    for (;;) {
      const end = buffered.indexOf('\n')
      if (end < 0) break
      const line = buffered.slice(0, end)
      buffered = buffered.slice(end + 1)
      if (line.trim()) yield JSON.parse(line)
    }
  }
}

function freePort(): Promise<number> {
  return new Promise((resolve, reject) => {
    const probe = createServer()
    probe.once('error', reject)
    probe.listen(0, '127.0.0.1', () => {
      const address = probe.address()
      if (!address || typeof address === 'string') return reject(new Error('free port unavailable'))
      probe.close(error => error ? reject(error) : resolve(address.port))
    })
  })
}
