const invoke = globalThis.__TAURI__?.core?.invoke;
const call = (name, args = {}) => invoke ? invoke(name, args) : Promise.reject(new Error('Ouvre Messenger pour accéder à la boîte locale.'));
const message = (value) => ({
  ...value, objet: value.subject, pj: value.attachment?.name || value.announced_attachment || '',
  statuts: value.statuses || {}, re: value.reply_to || '', pjMissing: !value.complete,
});
globalThis.MESSENGER_RUNTIME = {
  available: !!invoke,
  listenMessage: (callback) => globalThis.__TAURI__?.event?.listen('open-message', ({ payload }) => callback(payload)),
  async snapshot() {
    const value = await call('snapshot');
    return { ...value, mail: value.messages.map(message), approvals: value.requests };
  },
  preferences: (preferences) => call('save_preferences', { preferences }),
  providers: () => call('provider_statuses'),
  equipProvider: (id) => call('equip_provider', { id }),
  chooseExchangeLocation: () => call('choose_exchange_location'),
  chooseExchangeUrl: (url, token) => call('choose_exchange_url', { url, token }),
  createProject: (name) => call('create_project', { name }),
  copyInvitation: (project = null, account = null) => call('copy_invitation', { project, account }),
  merge: (source, target) => call('merge_accounts', { source, target }),
  file: (account, project) => call('file_account', { account, project: project || null }),
  contacts: (account, contacts) => call('save_contacts', { account, contacts }),
  requestAttachment: (messageId) => call('request_attachment', { messageId }),
  saveAttachment: (messageId) => call('save_attachment', { messageId }),
  openAttachment: (messageId) => call('open_attachment', { messageId }),
  chooseMigration: () => call('choose_migration_source'),
  migrate: (source, fingerprint) => call('apply_migration', { source, fingerprint }),
  retention: () => call('preview_retention'),
  purge: (fingerprint) => call('apply_retention', { fingerprint }),
  shutdown: () => call('shutdown'),
  answer: (requestId, response, note = null) => call('answer_approval', { verdict: {
    request_id: requestId, response, rendered_at: new Date().toISOString(), note,
  } }),
};
