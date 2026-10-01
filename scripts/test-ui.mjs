import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
await import('../src/presentation.js');
await import('../src/ui/i18n.js');
const calls = [];
const data = {
  fingerprint: 'first', preferences: { theme: 'dark', lang: 'FR', notif: 'on' },
  messages: [{ id: 'm1', emitted_at: '2026-09-26T12:00:00+02:00', from: 'a@p', to: ['b@p'], copies: [], subject: 'Test réel', body: [], reply_to: null,
    attachment: { name: 'preuve.txt', fingerprint: 'x'.repeat(64), size: 10 }, complete: false, journey: 'published', reachability: { 'b@p': 'no_session' }, statuses: { 'b@p': 'lu' } }],
  directory: [
    { account: { address: 'a@p', display: 'Alpha', host: 'codex', machine: 'Mac', role: 'Dev', active: true }, contacts: [], waiting: 0, last_collection: null },
    { account: { address: 'b@p', display: 'Beta', host: 'kimi', machine: 'Windows', role: 'QA', active: true }, contacts: [], waiting: 1, last_collection: null },
  ],
  requests: [{ id: 'r1', opened_by: 'a@p', gesture: 'Relire ensemble', scope: 'p', why_now: 'Prêt', reversible: 'Oui', if_refused: 'Attendre',
    nature: 'intervention', effective_nature: 'intervention', taken: false, verdict: null, closure: null, reorientation: null }],
  projects: [], providers: [], incidents: [], exchange: { path: '/shared', configured: true, reachable: true, listening: true, interval_seconds: 60 },
};
globalThis.__TAURI__ = { core: { invoke: async (name, args) => {
  calls.push([name, args]);
  if (name === 'snapshot') return structuredClone(data);
  if (name === 'create_project') {
    data.projects = [...data.projects, { name: args.name }];
    data.fingerprint = 'project-' + args.name;
    return args.name;
  }
  if (name === 'answer_approval') return { publication: 'published', notice: null };
  return null;
} } };
await import('../src/runtime.js');
const runtime = globalThis.MESSENGER_RUNTIME;
const snapshot = await runtime.snapshot();
assert.equal(snapshot.mail[0].pjMissing, true);
assert.equal(snapshot.mail[0].statuts['b@p'], 'lu');
assert.equal(snapshot.mail[0].journey, 'published');
assert.equal(runtime.mark, undefined, 'The human interface must never expose recipient marking');
assert.equal(runtime.chooseProjectFolder, undefined, 'A project is a shared name, never a folder of this computer');
assert.equal(runtime.connectProject, undefined);
const controller = ['controller-core.js', 'controller-view.js'].map((name) => readFileSync(new URL('../src/ui/' + name, import.meta.url), 'utf8')).join('');
class Logic { setState(patch, callback) { this.state = { ...this.state, ...(typeof patch === 'function' ? patch(this.state) : patch) }; callback?.(); } }
const Component = new Function('DCLogic', controller + '\nreturn Component;')(Logic);
const component = new Component();
await component._refresh();
component.state.clock = -1;
await component._refresh();
assert.equal(component.state.clock, Math.floor(Date.now() / 60000));
let view = component.renderVals();
assert.equal(view.groups.find((group) => group.name === 'p').agents.length, 2);
assert.equal(view.approvalItems[0].actions[0].label, 'Prendre en charge');
assert.equal(view.sel.journey, 'Publié après relecture de preuve');
assert.equal(view.sel.advance, undefined);
assert.equal(view.trafficTitle, 'Trafic du ' + new Intl.DateTimeFormat('fr-FR', { day:'numeric', month:'long', timeZone:'Europe/Paris' }).format(new Date()), 'The traffic view follows today in Paris even when the latest mail is older');
component.state.modal = 'setup';
assert.equal(component.renderVals().modal.steps[1].cta, 'Équiper les outils', 'Setup equips the AI tools since projects no longer do it');
assert.equal(component.renderVals().modal.steps[2].state, 'FAIT', 'Step 3 counts the listed projects, account projects included');
assert.equal(component.renderVals().modal.steps[2].cta, 'Créer un autre projet');
assert.equal(component.renderVals().modal.steps[3].state, 'À FAIRE');
await view.sel.openPj();
assert(calls.some(([name, args]) => name === 'request_attachment' && args.messageId === 'm1'));
component.state.modal = 'invite';
component.state.inviteChoice = 'p';
await component.renderVals().modal.primary();
assert(calls.some(([name, args]) => name === 'copy_invitation' && args.project === 'p'));
component.state.projName = 'reste';
component._openModal('project');
assert.equal(component.state.projName, '', 'Opening the project modal forgets a stale name');
for (const invalid of ['', '   ', 'commun', 'Commun', 'Été', '..', 'a/b']) {
  component.state.projName = invalid;
  component.state.projectNotice = null;
  await component.renderVals().modal.primary();
  assert(component.renderVals().modal.providerNotice, 'The modal explains why the name is refused: ' + JSON.stringify(invalid));
  assert(!component.renderVals().incidents.some((incident) => incident.text === component.state.projectNotice), 'A refused name stays in the modal, not in the incidents');
  assert.equal(component.state.modal, 'project');
}
assert(!calls.some(([name]) => name === 'create_project'), 'Nothing is published for an invalid name');
component.state.projName = '  Nouveau   Projet ';
assert.equal(component.renderVals().modal.normalizedText, 'Le projet s’appellera nouveau-projet (minuscules, sans espace).');
await component.renderVals().modal.primary();
assert.deepEqual(calls.filter(([name]) => name === 'create_project'), [['create_project', { name: 'nouveau-projet' }]], 'A project is created from its name alone, without any folder');
assert(!calls.some(([name]) => name === 'choose_project_folder' || name === 'connect_project'));
assert.equal(component.state.modal, 'invite', 'The invitation follows the creation');
assert.equal(component.state.inviteChoice, 'nouveau-projet');
assert.equal(component.state.projName, '');
data.projects.push({ name: 'talos' });
data.fingerprint = 'declared-elsewhere';
await component._refresh();
view = component.renderVals();
assert.deepEqual(view.groups.map((group) => group.name), ['nouveau-projet', 'p', 'talos', 'commun'], 'Projects are sorted so every computer shows the same order and tints');
const talos = view.groups.find((group) => group.name === 'talos');
assert(talos.open && talos.empty && talos.agents.length === 0, 'A project declared on another computer is listed, open, before any agent joins it');
assert(view.modal.choices.some((choice) => choice.name === 'talos'));
component.state.modal = 'setup';
assert.equal(component.renderVals().modal.steps[2].state, 'FAIT');
assert.equal(component.renderVals().modal.steps[2].text, 'Projets : nouveau-projet, p, talos');
assert.equal(component.renderVals().modal.steps[2].cta, 'Créer un autre projet');
await component._preference('theme', 'light');
assert(calls.some(([name, args]) => name === 'save_preferences' && args.preferences.theme === 'light'));
component._openModal('poste');
component.state.remoteUrl = 'https://messenger.arka-squad.app';
component.state.remoteToken = 'private-test-key';
await component.renderVals().modal.connectRemote();
assert(calls.some(([name, args]) => name === 'choose_exchange_url' && args.url === 'https://messenger.arka-squad.app' && args.token === 'private-test-key'));
assert.equal(component.state.remoteToken, '', 'The secret is cleared from UI state after connection');
const html = readFileSync(new URL('../src/index.html', import.meta.url), 'utf8');
assert(!html.includes('simulation.js'));
const template = ['template-main.html', 'template-panels.html'].map((name) => readFileSync(new URL('../src/ui/' + name, import.meta.url), 'utf8')).join('');
assert(!template.includes('sel.advance'));
assert(template.includes('modal.applyMaintenance'));
assert(template.includes('type="url"') && template.includes('type="password"'));
assert(template.includes('sel.openPj'));
assert(!calls.some(([name]) => name === 'mark_mail'));
component.state.lang = 'EN';
assert.equal(component.renderVals().boxes[0].label, 'All messages');
assert.equal(component.renderVals().sel.objet, 'Test réel', 'Message content must never be translated');
assert.equal(component.renderVals().modal.steps[2].text, 'Projects: nouveau-projet, p, talos');
component._openModal('project');
component.state.projName = 'Fils Message';
assert.equal(component.renderVals().modal.title, 'Create a project');
assert.equal(component.renderVals().modal.normalizedText, 'The project will be named fils-message (lowercase, no spaces).', 'Project names are never translated');
component._openModal('invite');
assert(component.renderVals().modal.choices.some((choice) => choice.name === 'talos' && choice.label === ''));
const bootstrap = readFileSync(new URL('../src/ui/bootstrap.js', import.meta.url), 'utf8');
let keydown;
let activeModal = null;
const keyboardDocument = { activeElement:null, querySelector:() => activeModal, addEventListener: (_, callback) => { keydown = callback; } };
new Function('document', bootstrap.slice(bootstrap.indexOf("document.addEventListener"), bootstrap.indexOf('document.body.prepend')))(keyboardDocument);
let clicks = 0, prevented = 0;
const action = { click: () => clicks++ };
for (const native of ['input', 'textarea', 'select', 'button', 'a', '[contenteditable="true"]']) {
  keydown({ key: ' ', target: { closest: (selector) => selector.includes(native) ? action : null }, preventDefault: () => prevented++ });
}
assert.equal(prevented, 0, 'Native controls and editable text retain their keyboard behavior');
assert.equal(clicks, 0);
keydown({ key: ' ', target: { closest: (selector) => selector === '[role="button"]' ? action : null }, preventDefault: () => prevented++ });
assert.equal(prevented, 1);
assert.equal(clicks, 1, 'Custom actions stay keyboard accessible');
let focused = null, closed = 0;
const first = { disabled:false, getClientRects:() => [1], focus:() => { focused = 'first'; } };
const last = { disabled:false, getClientRects:() => [1], focus:() => { focused = 'last'; } };
activeModal = { querySelectorAll:() => [first,last], querySelector:(selector) => selector === '[data-modal-close]' ? ({ click:() => closed++ }) : null, contains:() => true };
keyboardDocument.activeElement = last;
keydown({ key:'Tab', shiftKey:false, target:null, preventDefault() {} });
assert.equal(focused,'first');
keyboardDocument.activeElement = first;
keydown({ key:'Tab', shiftKey:true, target:null, preventDefault() {} });
assert.equal(focused,'last');
keydown({ key:'Escape', target:null, preventDefault() {} });
assert.equal(closed,1);
assert(template.includes('data-modal-close=""'), 'Escape closes dialogs independently of their translated label');
assert(template.includes('role="dialog" aria-modal="true"'));
console.log('UI : données réelles, commandes persistantes, pièces jointes incomplètes, interventions et droits humains vérifiés');
