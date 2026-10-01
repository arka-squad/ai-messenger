import assert from 'node:assert/strict';
import { readdirSync, readFileSync } from 'node:fs';
await import('../src/presentation.js');
await import('../src/ui/i18n.js');
const calls = [];
const data = {
  fingerprint: 'first', preferences: { theme: 'dark', lang: 'FR', notif: 'on' },
  messages: [{ id: 'm1', emitted_at: '2026-09-26T12:00:00+02:00', from: 'a@p', to: ['b@p'], copies: [], subject: 'Test réel', body: [], reply_to: null,
    attachment: { name: 'preuve.txt', fingerprint: 'x'.repeat(64), size: 10 }, complete: false, journey: 'published', reachability: { 'b@p': 'no_session' }, statuses: { 'b@p': 'lu' } }],
  directory: [
    { account: { address: 'a@p', display: 'Alpha', host: 'claude-code', machine: 'GRIMWORKSHOP', role: 'Dev', active: true }, contacts: [], waiting: 0, last_collection: null },
    { account: { address: 'b@p', display: 'Beta', host: 'kimi', machine: 'Windows', role: 'QA', active: true }, contacts: [], waiting: 1, last_collection: null },
  ],
  inactive: [{ address: 'c@p', display: 'Gamma', role: 'Ancien relecteur', host: 'codex', machine: 'arka', project: 'p' }],
  requests: [{ id: 'r1', opened_by: 'a@p', gesture: 'Relire ensemble', scope: 'p', why_now: 'Prêt', reversible: 'Oui', if_refused: 'Attendre',
    nature: 'intervention', effective_nature: 'intervention', taken: false, verdict: null, closure: null, reorientation: null }],
  projects: [], providers: [], incidents: [], exchange: { path: '/shared', configured: true, reachable: true, listening: true, interval_seconds: 60 },
};
const listeners = {};
const tick = () => new Promise((resolve) => setTimeout(resolve, 5));
globalThis.__TAURI__ = { event: { listen: async (name, callback) => { listeners[name] = callback; return () => { delete listeners[name]; }; } }, core: { invoke: async (name, args) => {
  calls.push([name, args]);
  if (name === 'snapshot') return structuredClone(data);
  if (name === 'create_project') {
    data.projects = [...data.projects, { name: args.name }];
    data.fingerprint = 'project-' + args.name;
    return args.name;
  }
  if (name === 'answer_approval') return { publication: 'published', notice: null };
  if (name === 'update_account') {
    if (args.role === 'Refusé par la boîte') throw 'Compte inconnu.';
    data.directory.find(({ account }) => account.address === args.address).account.role = args.role;
    data.fingerprint = 'role-' + args.role;
  }
  if (name === 'set_account_active') {
    const off = (account) => ({ address: account.address, display: account.display, role: account.role, host: account.host, machine: account.machine, project: account.project });
    if (args.active) {
      const account = data.inactive.find((item) => item.address === args.address);
      data.inactive = data.inactive.filter((item) => item !== account);
      data.directory.push({ account: { ...account, active: true }, contacts: [], waiting: 0, last_collection: null });
    } else {
      const entry = data.directory.find(({ account }) => account.address === args.address);
      data.directory = data.directory.filter((item) => item !== entry);
      data.inactive.push(off(entry.account));
    }
    data.fingerprint = 'active-' + args.address + args.active;
  }
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
// Clic sur la notification d'une demande : « Ce qu’on me demande » s'ouvre sur cette demande.
const mounted = new Component();
mounted.componentDidMount();
await tick();
assert(listeners['open-message'] && listeners['open-request'], 'The window listens to both notification events');
listeners['open-request']({ payload: 'r1' });
await tick();
assert.equal(mounted.state.box, 'moi', 'A request notification opens the requests box');
let opened = mounted.renderVals();
assert.equal(opened.boxes.find((box) => box.label === 'Ce qu’on me demande').color, 'var(--tx1)');
assert(opened.approvalItems[0].focused && opened.approvalItems[0].reveal === mounted._reveal, 'The request named by the notification is outlined and brought into view');
opened.boxes[0].pick();
assert(!mounted.renderVals().approvalItems[0].focused, 'Leaving the requests box drops the outline');
mounted.componentWillUnmount();
assert(!listeners['open-request'] && !listeners['open-message'], 'Unmounting stops both listeners');
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
// Comptes : le poste se lit, le rôle se corrige, la désactivation garde l'historique et se réactive.
component.state.modal = null;
view = component.renderVals();
const alpha = view.groups.find((group) => group.name === 'p').agents.find((agent) => agent.name === 'Alpha');
assert.equal(alpha.tip, 'a@p\nClaude Code · GRIMWORKSHOP\nDev', 'The tooltip names the AI tool and the computer of the agent');
component.state.agentPanel = 'a@p';
view = component.renderVals();
assert.equal(view.ag.post, 'Claude Code · GRIMWORKSHOP');
assert(view.ag.acct.viewing && !view.ag.acct.editing);
view.ag.acct.editRole();
view = component.renderVals();
assert(view.ag.acct.editing);
assert.equal(view.ag.acct.roleDraft, 'Dev', 'The editor starts from the current role');
const roleCalls = () => calls.filter(([name]) => name === 'update_account');
for (const invalid of ['', '   ', 'humain', ' Human ', 'deux\nlignes']) {
  component.renderVals().ag.acct.onRoleDraft({ target: { value: invalid } });
  await component.renderVals().ag.acct.saveRole();
  assert(component.renderVals().ag.acct.noticeAtRole, 'A refused role is explained beside the field: ' + JSON.stringify(invalid));
  assert.equal(component.state.providerNotice, null, 'A refused role never becomes an incident');
}
component.renderVals().ag.acct.onRoleDraft({ target: { value: ' Dev ' } });
await component.renderVals().ag.acct.saveRole();
assert.equal(roleCalls().length, 0, 'Nothing is published for an invalid or unchanged role');
component.renderVals().ag.acct.editRole();
component.renderVals().ag.acct.onRoleDraft({ target: { value: 'Refusé par la boîte' } });
await component.renderVals().ag.acct.saveRole();
assert.equal(component.renderVals().ag.acct.notice, 'Compte inconnu.', 'A refusal from the app stays beside the account');
assert(component.renderVals().ag.acct.editing, 'The draft survives a refusal');
assert(!component.renderVals().incidents.some((incident) => incident.text === 'Compte inconnu.'));
component.renderVals().ag.acct.onRoleDraft({ target: { value: '  Relecture du code  ' } });
await component.renderVals().ag.acct.saveRole();
assert.deepEqual(roleCalls().at(-1), ['update_account', { address: 'a@p', role: 'Relecture du code' }], 'The trimmed role is published');
view = component.renderVals();
assert(!view.ag.acct.editing && view.ag.role === 'Relecture du code', 'The new role shows once republished');
component._openModal('adv', 'b@p');
view = component.renderVals();
assert.equal(view.modal.post, 'Kimi Code · Windows', 'The “…” menu shows the agent’s post too');
view.modal.acct.editRole();
component.renderVals().modal.acct.onRoleDraft({ target: { value: 'QA mobile' } });
await component.renderVals().modal.primary();
assert.deepEqual(roleCalls().at(-1), ['update_account', { address: 'b@p', role: 'QA mobile' }], 'Saving the menu keeps a role being typed');
assert(component.state.modal === null && component.state.roleEdit === null && component.state.roleDraft === '', 'A successful save closes the menu and its draft');
// Le rôle du menu passe par le chemin du compte : refus sous le champ, menu ouvert, rien d'autre d'enregistré.
const sideCalls = () => calls.filter(([name]) => name === 'save_contacts' || name === 'file_account' || name === 'merge_accounts').length;
const sideBefore = sideCalls();
component._openModal('adv', 'b@p');
component.renderVals().modal.acct.editRole();
component.renderVals().modal.acct.onRoleDraft({ target: { value: 'Refusé par la boîte' } });
component.state.contactAlias = 'equipe';
await component.renderVals().modal.primary();
view = component.renderVals();
assert(view.modal.acct.noticeAtRole && view.modal.acct.notice === 'Compte inconnu.', 'A refused role from the menu is explained beside its field');
assert.equal(component.state.providerNotice, null, 'A refused role from the menu never becomes an incident');
assert(!view.incidents.some((incident) => incident.text === 'Compte inconnu.'));
assert(component.state.modal === 'adv' && view.modal.acct.editing && view.modal.acct.roleDraft === 'Refusé par la boîte', 'The menu and the draft stay open after a refusal');
assert.equal(sideCalls(), sideBefore, 'Nothing else is saved when the role is refused');
const rolesBefore = roleCalls().length;
component.renderVals().modal.acct.onRoleDraft({ target: { value: 'humain' } });
await component.renderVals().modal.primary();
assert(component.renderVals().modal.acct.noticeAtRole && component.state.providerNotice === null, 'An invalid role from the menu stays beside its field');
assert.equal(roleCalls().length, rolesBefore);
// Fermer le menu abandonne le brouillon et la confirmation : la fiche de l'agent s'ouvre au repos.
component.renderVals().closeModal();
component.state.agentPanel = 'b@p';
view = component.renderVals();
assert(!view.ag.acct.editing && view.ag.acct.roleDraft === '' && !view.ag.acct.notice, 'A role draft abandoned in the menu does not reappear in the panel');
component.state.agentPanel = null;
component._openModal('adv', 'b@p');
component.renderVals().modal.acct.askDeactivate();
component.renderVals().closeModal();
component.state.agentPanel = 'b@p';
view = component.renderVals();
assert(!view.ag.acct.confirming && !view.ag.acct.editing && view.ag.acct.roleDraft === '', 'A deactivation cancelled with the menu does not come back armed in the panel');
component.state.agentPanel = null;
component._openModal('adv', 'b@p');
component.renderVals().modal.acct.askDeactivate();
component.state.contactAlias = 'qa';
await component.renderVals().modal.primary();
assert.equal(sideCalls(), sideBefore + 1);
assert(component.state.modal === null && component.state.confirmDeactivate === null && component.state.accountNotice === null, 'Saving the menu disarms its deactivation');
// Changer de fiche depuis la liste abandonne les gestes de l'agent précédent ; recliquer le même agent les garde.
const railAgent = (name) => component.renderVals().groups.find((group) => group.name === 'p').agents.find((agent) => agent.name === name);
railAgent('Alpha').open();
component.renderVals().ag.acct.askDeactivate();
railAgent('Beta').open();
assert.equal(component.state.agentPanel, 'b@p');
assert(!component.renderVals().ag.acct.confirming && component.state.confirmDeactivate === null, 'Opening another agent drops the pending deactivation');
component.renderVals().ag.acct.editRole();
component.renderVals().ag.acct.onRoleDraft({ target: { value: 'brouillon' } });
railAgent('Beta').open();
assert.equal(component.renderVals().ag.acct.roleDraft, 'brouillon', 'Clicking the open agent again keeps its draft');
railAgent('Alpha').open();
assert(!component.renderVals().ag.acct.editing && component.state.roleDraft === '', 'Opening another agent drops the role draft');
// La confirmation dit ce que la désactivation coûte, et propose la fusion quand du courrier attend.
component.renderVals().ag.acct.askDeactivate();
view = component.renderVals();
assert.match(view.ag.acct.consequence, /ne pourra plus relever ni écrire/);
assert.match(view.ag.acct.consequence, /prochaine session créera un nouveau compte/);
assert(!view.ag.acct.hasWaiting && view.ag.acct.waitingText === '', 'No merge advice when no mail is waiting');
railAgent('Beta').open();
component.renderVals().ag.acct.askDeactivate();
view = component.renderVals();
assert(view.ag.acct.hasWaiting, 'Mail waiting for the account is announced before deactivating it');
assert.equal(view.ag.acct.waitingText, '1 message(s) l’attendent encore : pour un doublon, fusionne-le plutôt dans le compte qui reste (son courrier en attente le suit).');
view.ag.acct.mergeInstead();
assert(component.state.modal === 'adv' && component.state.modalAgent === 'b@p' && component.state.confirmDeactivate === null, 'Merge instead opens the account menu where merging lives');
assert(component.renderVals().modal.acct.idle);
component.renderVals().modal.acct.askDeactivate();
assert(component.renderVals().modal.acct.hasWaiting, 'The menu confirmation warns about waiting mail too');
component.renderVals().closeModal();
component.state.agentPanel = null;
component._openModal('adv', 'b@p');
component.renderVals().modal.acct.askDeactivate();
view = component.renderVals();
assert(view.modal.acct.confirming && !view.modal.acct.idle);
assert(!calls.some(([name]) => name === 'set_account_active'), 'Deactivation waits for confirmation');
view.modal.acct.cancelDeactivate();
assert(component.renderVals().modal.acct.idle);
component.state.modal = null;
component.state.agentPanel = 'b@p';
component.state.agent = 'b@p';
component.renderVals().ag.acct.askDeactivate();
await component.renderVals().ag.acct.deactivate();
assert.deepEqual(calls.filter(([name]) => name === 'set_account_active').at(-1), ['set_account_active', { address: 'b@p', active: false }]);
assert.equal(component.state.agentPanel, null, 'The panel of a deactivated account closes');
assert.equal(component.state.agent, null);
view = component.renderVals();
assert(!view.groups.some((group) => group.agents.some((agent) => agent.name === 'Beta')));
assert(view.hasInactive && !view.inactiveOpen);
assert.equal(view.inactiveTitle, 'Comptes désactivés (2)');
view.toggleInactive();
view = component.renderVals();
assert(view.inactiveOpen);
const gamma = view.inactive.find((account) => account.address === 'c@p');
assert.equal(gamma.name, 'Gamma');
assert.equal(gamma.post, 'Codex · arka · p', 'A deactivated account keeps its post and project');
await gamma.reactivate();
assert.deepEqual(calls.filter(([name]) => name === 'set_account_active').at(-1), ['set_account_active', { address: 'c@p', active: true }]);
view = component.renderVals();
assert.deepEqual(view.inactive.map((account) => account.address), ['b@p']);
assert(view.groups.find((group) => group.name === 'p').agents.some((agent) => agent.name === 'Gamma'), 'A reactivated account is back among the agents');
const html = readFileSync(new URL('../src/index.html', import.meta.url), 'utf8');
assert(!html.includes('simulation.js'));
// The template is one tree cut in two files. Tauri rewrites every packaged .html file as a whole
// document, closing the first half and dropping the second half's leading end tags, so the halves
// must not be .html files.
assert(!readdirSync(new URL('../src/ui/', import.meta.url)).some((name) => name.startsWith('template-') && name.endsWith('.html')), 'Template halves are .tpl, never rewritten by Tauri packaging');
const template = ['template-main.tpl', 'template-panels.tpl'].map((name) => readFileSync(new URL('../src/ui/' + name, import.meta.url), 'utf8')).join('');
assert(!template.includes('sel.advance'));
assert(template.includes('modal.applyMaintenance'));
assert(template.includes('type="url"') && template.includes('type="password"'));
assert(template.includes('sel.openPj'));
for (const binding of ['a.tip', 'ag.post', 'ag.acct.saveRole', 'ag.acct.deactivate', 'modal.acct.saveRole', 'modal.acct.deactivate', 'off.reactivate', 'inactiveTitle',
  'ag.acct.consequence', 'ag.acct.waitingText', 'ag.acct.mergeInstead', 'modal.acct.consequence', 'modal.acct.waitingText', 'request.reveal', 'request.border']) {
  assert(template.includes('{{ ' + binding + ' }}'), 'The template binds ' + binding);
}
for (const tag of ['sc-if', 'sc-for', 'div']) {
  assert.equal(template.split('<' + tag).length, template.split('</' + tag + '>').length, 'Both template halves keep ' + tag + ' balanced');
}
assert(template.includes('<span ref="{{ modal.acct.reveal }}" role="alert"'), 'A role refusal in the long menu scrolls into view');
assert(!template.includes('Il quitte la liste de tes agents'), 'The old confirmation that hid the consequences is gone');
assert(!calls.some(([name]) => name === 'mark_mail'));
component.state.lang = 'EN';
assert.equal(component.renderVals().boxes[0].label, 'All messages');
assert.equal(component.renderVals().sel.objet, 'Test réel', 'Message content must never be translated');
assert.equal(component.renderVals().modal.steps[2].text, 'Projects: nouveau-projet, p, talos');
view = component.renderVals();
assert.equal(view.inactiveTitle, 'Deactivated accounts (1)');
assert.equal(view.inactive[0].name, 'Beta', 'Account names are never translated');
assert.equal(view.inactive[0].post, 'Kimi Code · Windows · p');
component.state.agentPanel = 'a@p';
component.renderVals().ag.acct.editRole();
component.renderVals().ag.acct.onRoleDraft({ target: { value: 'humain' } });
await component.renderVals().ag.acct.saveRole();
assert.equal(component.renderVals().ag.acct.notice, 'An agent is never “human”. Describe its working role.');
assert.equal(component.renderVals().ag.role, 'Relecture du code', 'Roles are never translated');
component.renderVals().ag.acct.cancelRole();
component.state.directory.find(({ account }) => account.address === 'a@p').waiting = 2;
component.renderVals().ag.acct.askDeactivate();
view = component.renderVals();
assert.equal(view.ag.acct.consequence, 'Its agent will no longer be able to collect or send mail, and no one will be able to write to it. If it is still working, its next session will create a new account. Its history stays in the mailbox; you can reactivate it from “Deactivated accounts”.');
assert.equal(view.ag.acct.waitingText, '2 message(s) still waiting for it. For a duplicate, merge it into the account you keep instead: its pending mail follows.');
assert.match(view.ag.alertTitle, /^2 message\(s\) waiting for/);
component.renderVals().ag.acct.cancelDeactivate();
component.state.directory.find(({ account }) => account.address === 'a@p').waiting = 0;
component.state.agentPanel = null;
// Un compte repris d'une ancienne boîte n'a pas d'outil connu : seul ce repli se traduit.
data.directory.push({ account: { address: 'old@p', display: 'Ancien', host: 'inconnu', machine: '', role: '', active: true }, contacts: [], waiting: 0, last_collection: null },
  { account: { address: 'bare@p', display: 'Nu', machine: 'POSTE-7', role: 'Dev', active: true }, contacts: [], waiting: 0, last_collection: null });
data.fingerprint = 'migrated';
await component._refresh();
component.state.lang = 'EN';
component.state.agentPanel = 'old@p';
view = component.renderVals();
assert.equal(view.ag.post, 'Unknown tool');
assert.equal(view.ag.alertTitle, 'This account was never resumed');
assert.equal(view.ag.alertText, 'This account was imported from an old mailbox. Its agent never resumed it, so it does not collect its mail. Send it its invitation so it resumes its account from its working folder.');
assert(view.incidents.some((incident) => incident.text === 'old@p was imported from an old mailbox. Its agent never resumed it, so it does not collect its mail.'), 'Addresses stay untouched in translated incidents');
component.state.agentPanel = 'bare@p';
assert.equal(component.renderVals().ag.post, 'Unknown tool · POSTE-7', 'Machine names are never translated');
component.state.lang = 'FR';
assert.equal(component.renderVals().ag.post, 'Outil inconnu · POSTE-7');
component.state.agentPanel = 'old@p';
assert.equal(component.renderVals().ag.post, 'Outil inconnu');
component.state.lang = 'EN';
assert.match(component.renderVals().trafficTitle, /^Traffic on /);
component.state.agentPanel = null;
for (const key of ['Rôle', 'Modifier le rôle', 'Désactiver le compte', 'Désactiver ce compte ?', 'Désactiver', 'Réactiver', 'Leur historique reste dans la boîte.', 'Le rôle de cet agent', 'Outil d’IA et ordinateur de cet agent', 'Son rôle, sur une ligne (ex. relecture du code)', 'Donne un rôle à ce compte.', 'Le rôle tient sur une seule ligne.', 'Fusionner plutôt', 'Outil inconnu', 'Ce compte n’a jamais été repris']) {
  assert(globalThis.MESSENGER_I18N.text(key, 'EN') !== key, 'Every new owner string has an English translation: ' + key);
}
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
