globalThis.MESSENGER_PRESENTATION = {
  ME: null,
  TINTS: ['#a78bfa', '#34d399', '#60a5fa', '#f472b6'],
  ST: {
    nouveau: { icon: 'circle-dot', color: 'var(--warn-tx)', word: 'NOUVEAU' },
    lu: { icon: 'circle', color: 'var(--tx4)', word: 'LU' },
    traité: { icon: 'circle-check', color: 'var(--pass-tx)', word: 'TRAITÉ' },
  },
  ORDER: ['nouveau', 'lu', 'traité'],
  initialState: () => ({
    theme: 'dark', loading: true, notif: 'on', lang: 'FR', mail: [], directory: [], projects: [], incidents: [],
    box: 'toutes', filter: null, project: null, agent: null, query: '', view: 'fils', openThreads: {}, sel: null,
    statuses: {}, approvals: [], deciding: null, providers: [], equipping: null, providerNotice: null,
    exchange: null, exchangeNotice: null, remoteUrl: '', remoteToken: '', remoteBusy: false, openGroups: {}, agentPanel: null, agentClosing: false, modal: null, modalAgent: null,
    hidden: {}, incidentsOpen: false, copied: false, projName: '', projectNotice: null, inviteChoice: '',
    mergeTarget: null, fileTarget: null, contactAlias: '', contactNote: '', contactTargets: {}, mergeQuery: '', targetQuery: '',
    busy: false, migration: null, retention: null, maintenanceNotice: null,
  }),
};
