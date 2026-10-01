import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { mkdtemp, writeFile, rm } from 'node:fs/promises';
import { spawn, spawnSync } from 'node:child_process';
import { createServer } from 'node:net';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';

const root = resolve(import.meta.dirname, '..');
const target = join(root, 'src-tauri', 'target');
const built = spawnSync('cargo', ['build', '--manifest-path', join(root, 'server/Cargo.toml'), '--locked'], {
  cwd: root, env: { ...process.env, CARGO_TARGET_DIR: target }, stdio: 'inherit',
});
assert.equal(built.status, 0, 'The remote mailbox server must build');
const temporary = await mkdtemp(join(tmpdir(), 'messenger-remote-test-'));
const token = 'test' + createHash('sha256').update(temporary).digest('hex');
const tokenFile = join(temporary, 'token');
await writeFile(tokenFile, token, { mode: 0o600 });
const portServer = createServer();
await new Promise((resolveListen) => portServer.listen(0, '127.0.0.1', resolveListen));
const port = portServer.address().port;
await new Promise((resolveClose) => portServer.close(resolveClose));
const url = `http://127.0.0.1:${port}`;
let server;
const start = () => {
  server = spawn(join(target, 'debug', `messenger-server${process.platform === 'win32' ? '.exe' : ''}`), [], {
    env: { ...process.env, MESSENGER_ROOT: temporary, MESSENGER_TOKEN_FILE: tokenFile, MESSENGER_LISTEN_ADDR: `127.0.0.1:${port}` },
    stdio: ['ignore', 'ignore', 'pipe'],
  });
};
const stop = async () => {
  if (server && server.exitCode === null) {
    server.kill('SIGTERM');
    await new Promise((resolveExit) => server.once('exit', resolveExit));
  }
};
const request = async (path, method = 'GET', body, secret = token) => fetch(url + path, {
  method, headers: { Authorization: `Bearer ${secret}`, ...(body && !(body instanceof Uint8Array) ? { 'Content-Type': 'application/json' } : {}) },
  body: body && !(body instanceof Uint8Array) ? JSON.stringify(body) : body,
});

try {
  start();
  let ready = false;
  for (let i = 0; i < 50; i++) {
    try { ready = (await request('/v1/health')).status === 200; } catch {}
    if (ready) break;
    await new Promise((resolveWait) => setTimeout(resolveWait, 100));
  }
  assert(ready, 'The local HTTP service must start');
  assert.equal((await request('/v1/health', 'GET', null, 'wrong')).status, 401);
  assert.equal((await request('/v1/probe', 'POST')).status, 204);
  assert.deepEqual((await (await request('/v1/list')).json()).mutations, []);

  const message = { kind: 'message', payload: { id: 'http-proof', emitted_at: new Date().toISOString(), from: 'a@test', to: ['b@test'], copies: [], subject: 'Remote proof', body: ['One line.'], attachment: null, reply_to: null, projects: [], origin: { host: 'test', session: 'test' } } };
  const deposited = await request('/v1/mutations', 'POST', message);
  assert.equal(deposited.status, 200);
  const proof = (await deposited.json()).fingerprint;
  assert.equal(proof.length, 64);
  assert.equal((await (await request('/v1/mutations', 'POST', message)).json()).fingerprint, proof);
  assert.equal((await request('/v1/mutations', 'POST', { ...message, payload: { ...message.payload, subject: 'Conflict' } })).status, 409);
  assert.equal((await request('/v1/mutations', 'POST', { ...message, payload: { ...message.payload, id: '../escape' } })).status, 422);

  const bytes = new TextEncoder().encode('verified attachment');
  const fingerprint = createHash('sha256').update(bytes).digest('hex');
  const query = new URLSearchParams({ name: 'preuve.txt', fingerprint, size: String(bytes.length) });
  assert.equal((await request('/v1/attachments?' + query, 'POST', bytes)).status, 200);
  assert.deepEqual(new Uint8Array(await (await request('/v1/attachments/' + fingerprint + '?' + query)).arrayBuffer()), bytes);
  const checkpoint = { id: 'test-installation', machine: 'test', seen_at: new Date().toISOString(), integrated: {}, missed_before: null };
  assert.equal((await request('/v1/checkpoints', 'PUT', checkpoint)).status, 200);
  assert.equal((await (await request('/v1/list')).json()).mutations.length, 1);
  const retention = await (await request('/v1/retention')).json();
  assert.equal(retention.mutations, 0);
  assert.equal((await request('/v1/retention', 'POST', { fingerprint: 'stale', installation: checkpoint.id })).status, 409);
  const applied = await request('/v1/retention', 'POST', { fingerprint: retention.fingerprint, installation: checkpoint.id });
  assert.equal(applied.status, 200);
  assert.equal((await applied.json()).fingerprint, retention.fingerprint);

  await stop();
  start();
  ready = false;
  for (let i = 0; i < 50; i++) {
    try { ready = (await request('/v1/health')).status === 200; } catch {}
    if (ready) break;
    await new Promise((resolveWait) => setTimeout(resolveWait, 100));
  }
  assert(ready, 'The service must reopen the same mailbox');
  const reopened = await (await request('/v1/list')).json();
  assert.equal(reopened.mutations[0].payload.id, 'http-proof');
  assert.equal(reopened.checkpoints[0].id, checkpoint.id);

  const rust = spawnSync('cargo', ['test', '--manifest-path', join(root, 'src-tauri/Cargo.toml'), 'remote_exchange::tests::http_end_to_end', '--', '--ignored', '--nocapture'], {
    cwd: root, env: { ...process.env, CARGO_TARGET_DIR: target, MESSENGER_REMOTE_TEST_URL: url, MESSENGER_REMOTE_TEST_TOKEN: token }, encoding: 'utf8', maxBuffer: 8 * 1024 * 1024,
  });
  if (rust.status !== 0) throw new Error((rust.stdout + rust.stderr).slice(-5000));
  console.log('Remote protocol: authentication, immutable deposits, attachments, checkpoints, reopening, retention apply, and Rust client passed');
} finally {
  await stop();
  await rm(temporary, { recursive: true, force: true });
}
