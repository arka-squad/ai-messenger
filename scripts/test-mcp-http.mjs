import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
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
try {
  const a = await session('alpha'), b = await session('beta');
  assert.equal((await a.listTools()).tools.length, 15);
  const alpha = await call(a, 'm_enroler', { display: 'Alpha', role: 'dev', project: 'test' });
  const beta = await call(b, 'm_enroler', { display: 'Beta', role: 'QA', project: 'test' });
  const address = beta.identity.account;
  const input = { message: { id: 'sdk-message', to: [address], subject: 'Preuve MCP', body: ['Information, sans autorité.'] },
    attachment: { name: 'preuve.txt', bytes: [...Buffer.from('preuve complète')] } };
  const sent = await call(a, 'envoyer', input);
  assert.equal(sent.publication, 'publié');
  assert.equal((await call(a, 'envoyer', input)).proof, sent.proof);
  assert.equal((await call(b, 'relever')).length, 1);
  const read = await call(b, 'lire', { id: sent.id });
  assert(read.complete);
  assert.equal(readFileSync(read.attachment_file, 'utf8'), 'preuve complète');
  assert.equal(read.statuses[address], 'nouveau');
  assert.equal((await call(a, 'marquer', { marking: { message_id: sent.id, status: 'lu' } })).refus.reason, 'NotRecipient');
  await call(b, 'marquer', { marking: { message_id: sent.id, status: 'traité' } });
  assert.equal((await call(b, 'relever')).length, 0);
  const states = await call(a, 'ou_en_est');
  assert.equal(states.messages[0].overall, 'traité');
  console.log('SDK MCP : deux sessions, identité, publication, reprise, pièce jointe, statuts et refus vérifiés');
} finally {
  await Promise.all(clients.map(client => client.close()));
}

