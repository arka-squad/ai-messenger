import { afterEach, expect, test } from 'bun:test'
import { mkdirSync, readdirSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { createServer } from 'node:net'

let cleanup: (() => void)[] = []
type Frame = Record<string, unknown>
type SocketFrame = {
  type?: string
  token?: string
  id?: string
  request?: { method?: string; id?: unknown }
}
afterEach(() => {
  for (const dispose of cleanup.reverse()) dispose()
  cleanup = []
})

test('the authenticated live channel exposes tools and filters event senders', async () => {
  const root = join(tmpdir(), `messenger-channel-test-${process.pid}`)
  mkdirSync(root, { recursive: true })
  cleanup.push(() => rmSync(root, { recursive: true, force: true }))

  const server = Bun.serve({
    port: await freePort(),
    fetch(request, server) {
      return server.upgrade(request) ? undefined : new Response('upgrade required', { status: 426 })
    },
    websocket: {
      message(socket, raw) {
        const frame = JSON.parse(String(raw)) as SocketFrame
        if (frame.type === 'register') {
          expect(frame.token).toBe('test-token')
          socket.send(JSON.stringify({ type: 'accepted' }))
          socket.send(JSON.stringify({ type: 'event', sender: 'intruder', content: 'ignore me' }))
          socket.send(JSON.stringify({ type: 'event', sender: 'messenger-app', content: 'demande validée' }))
          return
        }
        if (frame.type === 'rpc' && frame.request?.method === 'tools/list') {
          socket.send(JSON.stringify({
            type: 'rpc_result',
            id: frame.id,
            response: {
              jsonrpc: '2.0', id: frame.request.id,
              result: { tools: [{ name: 'relever', inputSchema: { type: 'object' } }] },
            },
          }))
        }
      },
    },
  })
  cleanup.push(() => server.stop(true))

  const descriptor = join(root, 'connection.json')
  writeFileSync(descriptor, JSON.stringify({ port: server.port, token: 'test-token' }))
  const binary = readdirSync('src-tauri/binaries')
    .find(name => name.startsWith('messenger-claude-channel-'))
  if (!binary) throw new Error('compiled Claude channel not found')
  const child = Bun.spawn([join('src-tauri/binaries', binary)], {
    stdin: 'pipe', stdout: 'pipe', stderr: 'pipe',
    env: { ...Bun.env, MESSENGER_CHANNEL_DESCRIPTOR: descriptor },
  })
  cleanup.push(() => child.kill())

  const lines = jsonLines(child.stdout)
  child.stdin.write(JSON.stringify({
    jsonrpc: '2.0', id: 1, method: 'initialize',
    params: { protocolVersion: '2025-06-18', capabilities: {}, clientInfo: { name: 'test', version: '1' } },
  }) + '\n')
  child.stdin.write(JSON.stringify({ jsonrpc: '2.0', method: 'notifications/initialized' }) + '\n')
  child.stdin.write(JSON.stringify({ jsonrpc: '2.0', id: 2, method: 'tools/list', params: {} }) + '\n')
  child.stdin.flush()

  let initialized: Frame | undefined
  let tools: Frame | undefined
  let event: Frame | undefined
  for await (const value of lines) {
    const frame = value as Frame
    if (frame.id === 1) initialized = frame
    if (frame.id === 2) tools = frame
    if (frame.method === 'notifications/claude/channel') {
      if ((frame.params as Frame).content === 'ignore me') throw new Error('untrusted sender reached Claude')
      event = frame
    }
    if (initialized && tools && event) break
  }
  if (!initialized || !tools || !event) throw new Error('incomplete channel exchange')
  const capabilities = (initialized.result as Frame).capabilities as Frame
  expect((capabilities.experimental as Frame)['claude/channel']).toEqual({})
  const listed = (tools.result as Frame).tools as Frame[]
  expect(listed[0].name).toBe('relever')
  expect((event.params as Frame).content).toBe('demande validée')
}, 60_000) // Includes cold startup of the compiled macOS binary on a busy workstation.

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
