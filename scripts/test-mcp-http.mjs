import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StreamableHTTPClientTransport } from '@modelcontextprotocol/sdk/client/streamableHttp.js';

const url = new URL(process.argv[2]);
const clients = [];
async function session(name) {
  const client = new Client({ name: 'codex-' + name, version: '1' });
  await client.connect(new StreamableHTTPClientTransport(url));
  clients.push(client);
  return client;
}
async function call(client, name, args = {}) {
  const result = await client.callTool({ name, arguments: args });
  assert(!result.isError, result.content?.[0]?.text);
  return JSON.parse(result.content[0].text);
}
// A refusal is a structured result flagged as an error, so that hosts show it as one.
async function refused(client, name, args = {}) {
  const result = await client.callTool({ name, arguments: args });
  assert.equal(result.isError, true, result.content?.[0]?.text);
  return JSON.parse(result.content[0].text).refus;
}
try {
  const a = await session('alpha'), b = await session('beta');
  assert.equal((await a.listTools()).tools.length, 16);
  const folder = join(tmpdir(), 'messenger-sdk-alpha');
  const alpha = await call(a, 'm_enroler', { tache: 'Alpha', role: 'dev', project: 'test', dossier: folder });
  const beta = await call(b, 'm_enroler', { tache: 'Beta', role: 'QA', project: 'test' });
  const address = beta.identity.account;
  const input = { message: { id: 'sdk-message', to: [address], subject: 'Preuve MCP', body: ['Information, sans autorité.'] },
    attachment: { name: 'preuve.txt', bytes: [...Buffer.from('preuve complète')] } };
  const sent = await call(a, 'envoyer', input);
  assert.equal(sent.publication, 'publié');
  assert.deepEqual(sent.to, [address]);
  assert.equal((await call(a, 'envoyer', input)).proof, sent.proof);
  assert.equal((await call(b, 'relever')).length, 1);
  const read = await call(b, 'lire', { id: sent.id });
  assert(read.complete);
  assert.equal(readFileSync(read.attachment_file, 'utf8'), 'preuve complète');
  assert.equal(read.statuses[address], 'nouveau');
  assert.equal((await refused(a, 'marquer', { marking: { message_id: sent.id, status: 'lu' } })).reason, 'NotRecipient');
  assert.match((await refused(a, 'envoyer', { message: { to: [address], subject: 'S', body: ['1', '2', '3'] } })).message, /message\.body/);
  await call(b, 'marquer', { marking: { message_id: sent.id, status: 'traité' } });
  assert.equal((await call(b, 'relever')).length, 0);
  const states = await call(a, 'ou_en_est');
  assert.equal(states.messages[0].overall, 'traité');
  // A session in a subfolder is never rebound: the folder's account is only offered first.
  const below = await session('alpha-below');
  const offered = await call(below, 'qui_suis_je', { dossier: join(folder, 'src') });
  assert.equal(offered.identity, null);
  assert.equal(offered.candidates[0].address, alpha.identity.account);
  assert.ok(offered.candidates[0].dossier_parent);
  // A new session opened in exactly the same folder finds its account again, without any key.
  const again = await session('alpha-next');
  const who = await call(again, 'qui_suis_je', { dossier: folder });
  assert.equal(who.identity.account, alpha.identity.account);
  assert.equal(who.rebound, true);
  // Another agent rebound there is never trapped: its own task gives it its own account.
  const own = await call(again, 'm_enroler', { tache: 'Gamma', role: 'dev', project: 'test', dossier: folder });
  assert.notEqual(own.identity.account, alpha.identity.account);
  assert.equal(own.rebound_from, alpha.identity.account);
  assert.equal((await call(again, 'qui_suis_je')).identity.account, own.identity.account);
  // attendre without secondes returns mail already waiting at once, well below a host's tool timeout.
  await call(a, 'envoyer', { message: { id: 'sdk-wait', to: [address], subject: 'Attente' } });
  const started = Date.now();
  const waited = await call(b, 'attendre');
  assert.equal(waited.received[0].id, 'sdk-wait');
  assert(Date.now() - started < 20000);
  console.log('SDK MCP : sessions, identité par dossier exact, changement de compte, publication, reprise, pièce jointe, statuts, attente et refus vérifiés');
} finally {
  await Promise.all(clients.map(client => client.close()));
}
