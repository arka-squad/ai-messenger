    const pickedNames = Object.keys(this.state.contactTargets).filter((k) => this.state.contactTargets[k]);
    const groupPool = (list, fn) => projNames.concat(['commun'])
      .map((p) => {
        const rows = list.filter((a) => (a[2] || 'commun') === p);
        return { name: p, tint: p === 'commun' ? TINTS[3] : this._tint(p), count: String(rows.length), rows: rows.map(fn) };
      })
      .filter((g) => g.rows.length > 0);

    // name porte le nom du projet (jamais traduit), label le libellé du compte commun.
    const projOpts = projNames.map((p) => ({ p, name: p, label: '', hint: all.filter((m) => m.projects.indexOf(p) >= 0).length + ' messages' }))
      .concat([{ p: '', name: '', label: 'Sans projet (compte commun)', hint: 'Il écrit à tout le monde, sans projet' }]);
    const newProject = projectName(this.state.projName);

    const providerHosts = (this.state.providers || []).map((provider) => {
      const equipping = this.state.equipping === provider.id;
      const equip = () => {
        if (!provider.can_equip || this.state.equipping) return;
        this.setState({ equipping: provider.id, providerNotice: null });
        globalThis.MESSENGER_RUNTIME.equipProvider(provider.id)
          .then((updated) => this.setState((state) => ({
            providers: state.providers.map((item) => item.id === updated.id ? updated : item),
            equipping: null,
          })))
          .catch((error) => this.setState({ equipping: null, providerNotice: String(error) }));
      };
      return {
        name: provider.name,
        state: equipping ? 'équipement…' : provider.state,
        title: provider.detail,
        color: provider.equipped ? 'var(--pass-tx)' : 'var(--warn-tx)',
        icon: L(provider.equipped ? 'check' : 'wrench'),
        cursor: provider.can_equip ? 'pointer' : 'default',
        act: equip,
      };
    });
    const hosts = providerHosts;
    const readyHosts = hosts.filter((host) => host.state === 'prêt').map((host) => host.name);
    const exchange = this.state.exchange;
    const exchangeReady = !!(exchange && exchange.configured);

    const approvalItems = this.state.approvals.map((request) => {
      const intervention = request.effective_nature === 'intervention';
      const pending = !request.closure && (intervention ? !request.taken : !request.verdict);
      const decide = (response) => {
        if (!pending || this.state.busy) return;
        this.setState({ deciding: request.id });
        this._run(() => globalThis.MESSENGER_RUNTIME.answer(request.id, response))
          .then((outcome) => this.setState({ deciding: null, providerNotice: outcome?.notice || this.state.providerNotice }));
      };
      const actions = intervention ? [['prendre_en_charge', 'Prendre en charge', 'var(--tx2)']] : [
        ['valider', 'Valider', 'var(--pass-tx)'], ['refuser', 'Refuser', 'var(--fail-tx)'], ['discuter', 'Discuter', 'var(--tx2)'],
      ];
      // Désignée par sa notification : bordée et amenée en vue dans « Ce qu’on me demande ».
      const focused = this.state.box === 'moi' && this.state.openRequest === request.id;
      return { id: request.id, from: request.opened_by, gesture: request.gesture, scope: request.scope,
        focused, border: focused ? 'rgba(217, 119, 6, 0.55)' : 'rgba(var(--w), 0.1)', reveal: focused ? this._reveal : this._still,
        reversible: request.reversible, ifRefused: request.if_refused, whyNow: request.why_now,
        result: request.closure?.result || globalThis.MESSENGER_I18N.text(request.decision_journey === 'pending' ? 'Le dépôt n’est pas confirmé. L’agent ne peut pas encore utiliser cette décision.' : (request.verdict?.response === 'valider' ? 'L’agent doit encore rapporter le résultat.' : intervention && request.taken ? 'La suite se passe dans la session de l’agent.' : ''), this.state.lang),
        state: request.closure_journey === 'pending' ? 'CLÔTURE EN ATTENTE DE PUBLICATION' : request.decision_journey === 'pending' ? 'DÉCISION EN ATTENTE DE PUBLICATION' : request.closure ? 'TERMINÉE' : intervention ? (request.taken ? 'PRISE EN CHARGE' : 'INTERVENTION') : request.verdict ? (request.verdict.response === 'valider' ? 'VALIDÉE · RÉSULTAT ATTENDU' : 'REFUSÉE') : 'EN ATTENTE',
        stateColor: pending || (request.verdict?.response === 'valider' && !request.closure) ? 'var(--warn-tx)' : 'var(--tx4)',
        pending, busy: this.state.deciding === request.id,
        actions: actions.map(([response, label, color]) => ({ label, color, act: () => decide(response) })),
      };
    });
    const copyInvite = (project, account = null) => this._run(() => globalThis.MESSENGER_RUNTIME.copyInvitation(project || null, account), { copied: true });
    const updateContacts = (account, contacts) => this._run(() => globalThis.MESSENGER_RUNTIME.contacts(account, contacts));
    const maintenance = this.state.migration || this.state.retention;

    const values = {
      rootRef: (el) => { this._root = el; if (el) this._applyTheme(); },
      themeIcon: L(light ? 'moon' : 'sun'),
      themeTitle: light ? 'Passer en sombre' : 'Passer en clair',
      toggleTheme: () => this._preference('theme', light ? 'dark' : 'light'),
      langLabel: this.state.lang === 'FR' ? 'EN' : 'FR',
      langTitle: this.state.lang === 'FR' ? 'Switch to English' : 'Passer en français',
      toggleLang: () => this._preference('lang', this.state.lang === 'FR' ? 'EN' : 'FR'),
      notifIcon: L(this.state.notif === 'on' ? 'bell-ring' : 'bell-off'),
      notifColor: this.state.notif === 'on' ? 'var(--tx2)' : 'var(--tx5)',
      notifTitle: this.state.notif === 'on'
        ? 'Notifications système actives : chaque message qui passe est signalé — cliquer pour couper'
        : 'Notifications système coupées — cliquer pour les rétablir',
      toggleNotif: () => this._preference('notif', this.state.notif === 'on' ? 'off' : 'on'),
      meTitle: 'Administration humaine de la boîte',
      boxPath: exchange ? exchange.path : 'Boîte locale de cet ordinateur',
      boxTitle: exchange?.kind === 'url' ? 'Boîte en ligne' : exchangeReady ? 'Boîte partagée' : 'Boîte locale',
      boxDescription: exchange?.kind === 'url' ? 'La boîte est reliée à son adresse HTTPS.' : exchangeReady
        ? 'La boîte est ouverte sur un dossier partagé.'
        : 'Choisis un dossier partagé pour relier cet ordinateur aux autres.',

      loading: this.state.loading, ready: !this.state.loading,
      hasApprovals: approvalItems.length > 0,
      approvalCount: approvalItems.filter((request) => request.pending).length,
      approvalItems,
      five: [1, 2, 3, 4, 5], eight: [1, 2, 3, 4, 5, 6, 7, 8],

      newBadge: tally.nouveau + ' NOUVEAU' + (tally.nouveau > 1 ? 'X' : ''),
      newKey: 'n' + tally.nouveau,
      liveLabel: exchange && exchange.listening ? 'Veille active' : 'Relève toutes les ' + (exchange?.interval_seconds || 10) + ' s',
      liveTitle: exchange && exchange.listening
        ? 'Le dossier signale ses changements.'
        : 'La relève périodique vérifie les nouvelles écritures.',
      liveDot: exchange && exchange.reachable ? 'var(--pass-tx)' : 'var(--warn-tx)',
      livePulse: exchange && exchange.listening ? 'pulse' : '',
      liveBg: exchange && exchange.reachable ? 'rgba(var(--w), 0.05)' : 'transparent',
      liveCursor: 'default',
      toggleLive: () => {},

      hasIncidents: incidents.length > 0,
      incidents,
      incidentsOpen: this.state.incidentsOpen,
      incidentCount: incidents.length + (incidents.length > 1 ? ' signalements' : ' signalement'),
      incidentPeek: this.state.incidentsOpen ? '' : (incidents[0] ? incidents[0].text : ''),
      incidentToggle: this.state.incidentsOpen ? 'Replier' : 'Voir',
      incidentCaret: this.state.incidentsOpen ? 'rotate(180deg)' : 'none',
      toggleIncidents: () => this.setState((st) => ({ incidentsOpen: !st.incidentsOpen })),

      boxes: [
        ['toutes', 'Tous les messages', 'inbox', all.length],
        ['moi', 'Ce qu’on me demande', 'hand', approvalItems.filter((r) => r.pending).length],
        ['fils', 'Réponses', 'reply', all.filter((m) => m.re).length],
        ['pj', 'Avec pièce jointe', 'paperclip', all.filter((m) => m.pj).length],
      ].map((b) => {
        const on = this.state.box === b[0];
        return {
          label: b[1], icon: L(b[2]), count: String(b[3]),
          color: on ? 'var(--tx1)' : 'var(--tx-inactive)',
          bg: on ? 'rgba(var(--w), 0.07)' : 'transparent',
          pick: () => { this.setState({ box: b[0] }); this._reload(); },
        };
      }),

      groups,
      hasInactive: inactive.length > 0, inactive, inactiveOpen: this.state.inactiveOpen,
      inactiveTitle: 'Comptes désactivés (' + inactive.length + ')',
      inactiveCaret: this.state.inactiveOpen ? 'rotate(90deg)' : 'none',
      toggleInactive: () => this.setState((st) => ({ inactiveOpen: !st.inactiveOpen })),
      allProjColor: this.state.project ? 'var(--tx5)' : 'var(--tx2)',
      pickAllProjects: () => { this.setState({ project: null, agent: null }); this._reload(); },

      ctas: [
        { label: 'Mise en place guidée', icon: L('list-checks'), kind: 'setup', todo: false },
        { label: 'Créer un projet', icon: L('plus'), kind: 'project', todo: false },
        { label: 'Inviter un agent', icon: L('user-round-plus'), kind: 'invite', todo: true },
      ].map((c) => ({
        label: c.label, icon: c.icon, todo: c.todo,
        color: 'var(--tx2)',
        border: c.todo ? 'rgba(217, 119, 6, 0.3)' : 'rgba(var(--w), 0.1)',
        bg: 'transparent',
        act: () => this._openModal(c.kind),
      })),

      toolsLabel: readyHosts.length ? 'Prêts : ' + readyHosts.join(', ') : 'Aucun fournisseur équipé',
      openPoste: () => this._openModal('poste'),
      lastSweep: exchange && exchange.reachable
        ? 'Relève automatique toutes les ' + exchange.interval_seconds + ' s'
        : 'Dossier non joignable · reprise automatique',

      chips: [
        [null, 'Tous', all.length],
        ['nouveau', 'Nouveaux', tally.nouveau],
        ['lu', 'Lus', tally.lu],
        ['traité', 'Traités', tally['traité']],
      ].map((c) => {
        const on = this.state.filter === c[0];
        return {
          label: c[1], count: String(c[2]),
          border: on ? 'rgba(var(--w), 0.24)' : 'rgba(var(--w), 0.1)',
          bg: on ? 'rgba(var(--w), 0.07)' : 'transparent',
          color: on ? 'var(--tx1)' : 'var(--tx4)',
          pick: () => this.setState({ filter: c[0] }),
        };
      }),

      query: this.state.query,
      onQuery: (e) => this.setState({ query: e.target.value }),

      trafficTitle: 'Trafic du ' + new Intl.DateTimeFormat(this.state.lang === 'EN' ? 'en-GB' : 'fr-FR', { day: 'numeric', month: 'long', timeZone: 'Europe/Paris' }).format(new Date(day.slice(0, 4) + '-' + day.slice(4, 6) + '-' + day.slice(6, 8))),
      dayCaption: dayMsgs.length + ' messages · ' + lanes.length + ' agents',
      lanes, ticks, noTraffic: lanes.length === 0,
      nowLeft: (parisMinutes / 1440 * 100) + '%', nowTop: (-14 - lanes.length * 22) + 'px', nowHeight: (lanes.length * 22 + 18) + 'px',

      listTitle: this.state.view === 'fils' ? 'Fils de discussion' : 'Messages',
      threadView: !this.state.loading && this.state.view === 'fils',
      flatView: !this.state.loading && this.state.view !== 'fils',
      threads,
      modes: [['fils', 'Fils'], ['plat', 'Tous']].map((v) => {
        const on = (this.state.view === 'fils') === (v[0] === 'fils');
        return {
          label: v[1],
          border: on ? 'rgba(var(--w), 0.22)' : 'rgba(var(--w), 0.08)',
          bg: on ? 'rgba(var(--w), 0.07)' : 'transparent',
          color: on ? 'var(--tx1)' : 'var(--tx5)',
          pick: () => this.setState({ view: v[0] }),
        };
      }),
      listCaption: this.state.view === 'fils'
        ? threads.length + ' fils · ' + visible.length + ' msg'
        : visible.length + ' / ' + all.length,
      emptyList: visible.length === 0,
      emptyLabel: all.length === 0 ? 'La boîte est vide.' : 'Aucun message ne correspond.',
      footStat: all.length + ' messages · ' + tally.nouveau + ' nouveaux · ' + all.filter((m) => m.pj).length + ' pièces jointes',
      footSource: 'Source : base locale',

      messages: visible.map((m, i) => {
        const on = sel && m.id === sel.id;
        return {
          hhmm: m.hhmm, from: m.from, to: m.to.join(', '), objet: m.objet,
          hasPj: !!m.pj,
          pjIcon: L(m.pjMissing ? 'file-x' : 'paperclip'),
          pjColor: m.pjMissing ? 'var(--warn-tx)' : 'var(--tx5)',
          pjTitle: m.pjMissing ? 'Ce fichier n\u2019est pas dans le dossier de la boîte.' : m.pj,
          status: ST[m.status].word,
          statusIcon: L(ST[m.status].icon),
          statusColor: ST[m.status].color,
          mark: on ? 'var(--tx1)' : (m.status === 'nouveau' ? 'var(--warn-tx)' : 'transparent'),
          bg: on ? 'rgba(var(--w), 0.06)' : 'transparent',
          objetColor: m.status === 'nouveau' ? 'var(--tx1)' : 'var(--tx2)',
          weight: m.status === 'nouveau' ? 600 : 400,
          anim: i < 14 ? 'drop' : '',
          delay: Math.min(i, 14) * 22 + 'ms',
          tags: m.projects.map((p) => ({ name: p, tint: this._tint(p === 'commun' ? '' : p), title: p === 'commun' ? 'Compte commun à tous les projets' : p })),
          forMe: m.forMe,
          roleLabel: m.actor ? 'on attend ta décision' : 'pour information',
          roleIcon: L(m.actor ? 'hand' : 'eye'),
          roleColor: m.actor ? 'var(--warn-tx)' : 'var(--tx4)',
          roleBorder: m.actor ? 'rgba(217, 119, 6, 0.34)' : 'rgba(var(--w), 0.1)',
          roleBg: m.actor ? 'rgba(217, 119, 6, 0.10)' : 'transparent',
          pick: () => this.setState({ sel: m.id }),
        };
      }),

      sel: {
        id: s.id || '', objet: s.objet || 'Aucun message à afficher.',
        from: s.from || '', stamp: s.day ? s.day.slice(6, 8) + '/' + s.day.slice(4, 6) + ' ' + s.hhmm + ' Paris' : '',
        tags: (s.projects || []).map((p) => ({ name: p, tint: this._tint(p === 'commun' ? '' : p), title: p === 'commun' ? 'Compte commun à tous les projets' : p })),
        recips: (s.to || []).map((n) => {
          const st = s.statuts[n] || 'nouveau';
          return {
            name: n, status: ST[st].word, dot: ST[st].color,
            color: n === ME ? 'var(--tx1)' : 'var(--tx3)',
            title: st === 'nouveau' ? 'ne l\u2019a pas encore lu' : 'l\u2019a marqué ' + st,
          };
        }),
        askTitle: 'Suivi du courrier', askIcon: L('eye'), askColor: 'var(--tx3)',
        askBorder: 'rgba(var(--w), 0.09)', askBg: 'transparent',
        askText: 'Seuls les agents destinataires marquent leur propre statut. L’humain lit la boîte et répond aux demandes distinctes.',
        steps,
        journey: ({ pending: 'En attente de publication', published: 'Publié après relecture de preuve', integrated: 'Intégration confirmée', conflict: 'Écriture locale en conflit' })[s.journey] || '',
        history: (s.history || []).map((item) => ({ line: [item.date, item.par, item.statut].filter(Boolean).join(' · ') })),
        reach: Object.entries(s.reachability || {}).map(([account, reach]) => account + ' : ' + ({ live_session: 'remis à une session vivante', next_start: 'déposé pour son prochain démarrage', no_session: 'aucune session à atteindre' })[reach]).join(' · ') || 'L’atteinte d’une session n’a pas été confirmée.',
        body: (s.body || []).map((line) => ({ line })),
        noBody: !s.body || s.body.length === 0,
        hasPj: !!s.pj, noPj: !s.pj, pj: s.pj || '',
        pjIcon: L(s.pjMissing ? 'file-x' : 'file-text'),
        pjColor: s.pjMissing ? 'var(--warn-tx)' : 'var(--tx4)',
        pjBorder: s.pjMissing ? 'rgba(217, 119, 6, 0.3)' : 'rgba(var(--w), 0.1)',
        pjState: s.pjMissing ? 'demander la remise' : 'ouvrir',
        openPj: () => this._run(() => s.pjMissing ? globalThis.MESSENGER_RUNTIME.requestAttachment(s.id) : globalThis.MESSENGER_RUNTIME.openAttachment(s.id)),
        savePj: () => this._run(() => globalThis.MESSENGER_RUNTIME.saveAttachment(s.id)),
        canSavePj: !!s.pj && !s.pjMissing,
        pjTitle: s.pjMissing ? 'Ce fichier n\u2019est pas disponible dans la boîte.' : 'Ouvrir la pièce jointe',
        thread, noThread: thread.length === 0,
      },

      agentOpen: !!ap,
      panelAnim: this.state.agentClosing ? 'panel-out' : 'panel-in',
      closeAgent: () => {
        this.setState({ agentClosing: true });
        clearTimeout(this._p);
        this._p = setTimeout(() => this.setState({ agentPanel: null, agentClosing: false, ...ACCOUNT_IDLE }), 195);
      },
      ag: ap ? {
        name: ap[10], address: ap[1],
        role: ap[5] || noRole, post: ap[11] || '—',
        acct: this._accountControls(ap[1], ap[5], ap[7]),
        dot: ap[7] > 0 ? 'var(--warn-tx)' : (ap[6] ? 'var(--pass-tx)' : 'var(--tx5)'),
        pulse: ap[7] > 0 ? 'pulse' : '',
        alert: ap[7] > 0 || ap[3] === 'inconnu',
        alertTitle: ap[3] === 'inconnu' ? 'Ce compte n\u2019a jamais été repris' : ap[7] + ' message(s) l\u2019attend(ent) depuis ' + ap[8],
        alertText: ap[3] === 'inconnu'
          ? 'Ce compte a été repris d\u2019une ancienne boîte : son agent ne l\u2019a jamais repris, il ne relève donc pas son courrier. Envoie-lui son invite : il reprendra son compte depuis son dossier de travail.'
          : 'S\u2019il ne répond pas, envoie-lui son invite : il reprendra son compte depuis son dossier de travail.',
        stats: [
          { value: String(apSent), label: 'messages envoyés', color: 'var(--tx1)' },
          { value: String(apIn), label: 'reçus', color: 'var(--tx1)' },
          { value: String(ap[7]), label: 'en attente', color: ap[7] > 0 ? 'var(--warn-tx)' : 'var(--tx1)' },
        ],
        filterLabel: this.state.agent === ap[0] ? 'Retirer le filtre' : 'Ne voir que son courrier',
        filter: () => { this.setState((st) => ({ agent: st.agent === ap[0] ? null : ap[0] })); this._reload(); },
        copyLabel: this.state.copied ? 'Invite copiée' : 'Copier son invite',
        copyIcon: L(this.state.copied ? 'check' : 'copy'),
        copy: () => copyInvite(ap[2], ap[1]),
        contactCount: ap[9].length + (ap[9].length > 1 ? ' contacts' : ' contact'),
        contacts: ap[9].map((c) => ({
          alias: c[0], targets: c[1], note: c[2],
          remove: () => updateContacts(ap[1], this.state.directory.find((entry) => entry.account.address === ap[1]).contacts.filter((contact) => contact.alias !== c[0])),
        })),
        noContacts: ap[9].length === 0,
        openAdv: () => this._openModal('adv', ap[0]),
      } : {},

      modalOpen: !!kind,
      // Fermer le menu abandonne ses gestes de compte : rien ne revient armé dans la fiche de l'agent.
      closeModal: () => this.setState({ modal: null, modalAgent: null, observerKey: null, ...ACCOUNT_IDLE }),
      stop: (e) => e.stopPropagation(),
      modal: {
        width: kind === 'setup' ? '640px' : (kind === 'adv' ? '680px' : '560px'),
        title: mt[0], intro: mt[1],
        isSetup: kind === 'setup', isProject: kind === 'project', isInvite: kind === 'invite',
        isAdv: kind === 'adv', isPoste: kind === 'poste',

        steps: [
          { n: '1', title: 'Choisir la boîte', state: exchangeReady ? 'FAIT' : 'À FAIRE', done: exchangeReady,
            text: 'Choisis un dossier local, un partage réseau ou une adresse HTTPS commune.',
            cta: exchangeReady ? '' : 'Choisir le dossier', kind: 'poste' },
          { n: '2', title: 'Équiper les outils d’IA', state: readyHosts.length ? 'FAIT' : 'À FAIRE', done: readyHosts.length > 0,
            text: readyHosts.length ? 'Prêts : ' + readyHosts.join(', ') : 'Branche la boîte dans les outils d’IA de cet ordinateur, puis ouvre une nouvelle session.',
            cta: readyHosts.length ? '' : 'Équiper les outils', kind: 'poste', icon: 'wrench' },
          { n: '3', title: 'Créer un projet', state: this._projects().length ? 'FAIT' : 'À FAIRE', done: this._projects().length > 0,
            text: SCENARIO.connectedProjectsText, cta: this._projects().length ? 'Créer un autre projet' : 'Créer un projet', kind: 'project' },
          { n: '4', title: 'Inviter tes agents', state: this.state.directory.some(({ account }) => account.installation === this.state.installation && !!account.installation) ? 'FAIT' : 'À FAIRE', done: this.state.directory.some(({ account }) => account.installation === this.state.installation && !!account.installation),
            text: 'Colle l\u2019invite dans le chat de chaque agent : il crée son compte tout seul, dans ce projet.', cta: 'Copier l\u2019invite', kind: 'invite' },
        ].map((st) => ({
          n: st.n, title: st.title, state: st.state, text: st.text,
          stateColor: st.done ? 'var(--pass-tx)' : 'var(--warn-tx)',
          border: st.done ? 'rgba(var(--w), 0.08)' : 'rgba(217, 119, 6, 0.3)',
          bg: st.done ? 'transparent' : 'rgba(217, 119, 6, 0.10)',
          numBorder: st.done ? 'rgba(16, 185, 129, 0.4)' : 'rgba(217, 119, 6, 0.4)',
          numBg: 'transparent',
          numColor: st.done ? 'var(--pass-tx)' : 'var(--warn-tx)',
          hasCta: !!st.cta, cta: st.cta,
          ctaIcon: L(st.icon || ({ invite: 'copy', project: 'plus' })[st.kind] || 'folder-plus'),
          ctaBorder: 'rgba(var(--w), 0.14)', ctaBg: 'rgba(var(--w), 0.04)', ctaColor: 'var(--tx1)',
          act: () => this._openModal(st.kind),
        })),

        browse: async () => {
          this.setState({ exchangeNotice: null });
          try { const selected = await globalThis.MESSENGER_RUNTIME.chooseExchangeLocation(); if (selected) this.setState({ exchange: selected }); }
          catch (error) { this.setState({ exchangeNotice: String(error) }); }
          finally { await this._refresh(); }
        },
        remoteUrl: this.state.remoteUrl,
        remoteToken: this.state.remoteToken,
        remoteBusy: this.state.remoteBusy,
        onRemoteUrl: (e) => this.setState({ remoteUrl: e.target.value }),
        onRemoteToken: (e) => this.setState({ remoteToken: e.target.value }),
        connectRemote: async () => {
          if (this.state.remoteBusy) return;
          this.setState({ remoteBusy: true, exchangeNotice: null });
          try { await globalThis.MESSENGER_RUNTIME.chooseExchangeUrl(this.state.remoteUrl, this.state.remoteToken); }
          catch (error) { this.setState({ exchangeNotice: String(error) }); }
          finally { this.setState({ remoteBusy: false, remoteToken: '' }); }
        },
        projName: this.state.projName,
        projectPlaceholder: SCENARIO.projectPlaceholder,
        onProjName: (e) => this.setState({ projName: e.target.value, projectNotice: null }),
        normalized: !!newProject && newProject !== this.state.projName,
        normalizedText: 'Le projet s\u2019appellera ' + newProject + ' (minuscules, sans espace).',

        choices: projOpts.map((o) => {
          const on = this.state.inviteChoice === o.p;
          return {
            name: o.name, label: o.label, hint: o.hint,
            border: on ? 'rgba(var(--w), 0.22)' : 'rgba(var(--w), 0.1)',
            bg: on ? 'rgba(var(--w), 0.06)' : 'transparent',
            ring: on ? 'var(--arka-red)' : 'rgba(var(--w), 0.22)',
            inner: on ? 'var(--arka-red)' : 'transparent',
            color: on ? 'var(--tx1)' : 'var(--tx3)',
            pick: () => this.setState({ inviteChoice: o.p, copied: false }),
          };
        }),
        copied: this.state.copied,

        projectText: ma && ma[1].indexOf('@') > 0
          ? 'Son adresse porte son projet (' + ma[2] + ') : il ne se range pas ailleurs.'
          : 'Ce compte n\u2019a pas de projet dans son adresse : tu peux le ranger où tu veux.',
        canFile: !!(ma && ma[1].indexOf('@') < 0),
        role: ma ? ma[5] || noRole : '', post: ma ? ma[11] || '—' : '',
        acct: ma ? this._accountControls(ma[1], ma[5], ma[7]) : {},
        fileChoices: projOpts.map((o) => {
          const on = this.state.fileTarget === o.p;
          return {
            name: o.name, label: o.label,
            border: on ? 'rgba(var(--w), 0.24)' : 'rgba(var(--w), 0.1)',
            bg: on ? 'rgba(var(--w), 0.07)' : 'transparent',
            color: on ? 'var(--tx1)' : 'var(--tx3)',
            pick: () => this.setState({ fileTarget: o.p }),
          };
        }),
        mergeQuery: this.state.mergeQuery,
        onMergeQuery: (e) => this.setState({ mergeQuery: e.target.value }),
        mergeCount: mergePool.length + ' / ' + pool.length,
        mergeEmpty: mergePool.length === 0,
        mergeGroups: groupPool(mergePool, (a) => {
          const on = this.state.mergeTarget === a[0];
          return {
            label: a[0], meta: a[6] ? 'dernier ' + a[6] : 'silencieux',
            ring: on ? 'var(--arka-red)' : 'rgba(var(--w), 0.22)',
            inner: on ? 'var(--arka-red)' : 'transparent',
            color: on ? 'var(--tx1)' : 'var(--tx3)',
            bg: on ? 'rgba(var(--w), 0.06)' : 'transparent',
            pick: () => this.setState({ mergeTarget: on ? null : a[0] }),
          };
        }),
        mergeText: this.state.mergeTarget && ma
          ? '« ' + ma[0] + ' » sera fermé : son courrier en attente passe à ' + this.state.mergeTarget + ', et ce qui s\u2019écrit encore à son adresse y arrive. Les messages déjà envoyés ne changent pas.'
          : 'Choisis le compte qui garde la main. Les messages déjà envoyés ne changent pas.',
        alias: this.state.contactAlias,
        onAlias: (e) => this.setState({ contactAlias: e.target.value }),
        note: this.state.contactNote,
        onNote: (e) => this.setState({ contactNote: e.target.value }),
        targetQuery: this.state.targetQuery,
        onTargetQuery: (e) => this.setState({ targetQuery: e.target.value }),
        targetCount: targetPool.length + ' / ' + pool.length,
        targetEmpty: targetPool.length === 0,
        picked: pickedNames.map((n) => ({
          label: n,
          remove: () => this.setState((st) => ({ contactTargets: Object.assign({}, st.contactTargets, { [n]: false }) })),
        })),
        hasPicked: pickedNames.length > 0,
        targetGroups: groupPool(targetPool, (a) => {
          const on = !!this.state.contactTargets[a[0]];
          return {
            label: a[0], meta: a[6] ? 'dernier ' + a[6] : 'silencieux',
            ring: on ? 'var(--arka-red)' : 'rgba(var(--w), 0.22)',
            tickColor: on ? 'var(--arka-red)' : 'transparent',
            color: on ? 'var(--tx1)' : 'var(--tx3)',
            bg: on ? 'rgba(var(--w), 0.06)' : 'transparent',
            pick: () => this.setState((st) => ({ contactTargets: Object.assign({}, st.contactTargets, { [a[0]]: !st.contactTargets[a[0]] }) })),
          };
        }),

        hosts,
        watch: this._watch(),
        // Un nom refusé reste dans la fenêtre : il ne devient pas un signalement.
        providerNotice: this.state.projectNotice || this.state.providerNotice,
        exchangeNotice: this.state.exchangeNotice,
        shutdown: () => globalThis.MESSENGER_RUNTIME.shutdown().catch((error) => this.setState({ providerNotice: String(error) })),
        maintenanceNotice: this.state.maintenanceNotice,
        hasMigration: !!this.state.migration, hasRetention: !!this.state.retention,
        maintenanceSummary: this.state.migration ? this.state.migration.messages + ' messages · ' + this.state.migration.accounts + ' comptes · ' + this.state.migration.attachments + ' pièces jointes · ' + this.state.migration.missing_attachments.length + ' absentes'
          : this.state.retention ? this.state.retention.mutations + ' écritures et ' + this.state.retention.attachments + ' pièces jointes supprimables · ' + this.state.retention.protected + ' écritures protégées · ' + this.state.retention.dormant.length + ' installations dormantes' : '',
        migrationRows: this.state.migration ? Object.entries(this.state.migration.counts).map(([account, counts]) => ({ account, counts: Object.entries(counts).map(([status, n]) => n + ' ' + status).join(' · ') })) : [],
        previewMigration: async () => { const migration = await this._run(() => globalThis.MESSENGER_RUNTIME.chooseMigration()); if (migration) this.setState({ migration, retention: null, maintenanceNotice: null }); },
        previewRetention: async () => { const retention = await this._run(() => globalThis.MESSENGER_RUNTIME.retention()); if (retention) this.setState({ retention, migration: null, maintenanceNotice: null }); },
        cancelMaintenance: () => this.setState({ migration: null, retention: null, maintenanceNotice: null }),
        applyMaintenance: () => this._run(() => this.state.migration ? globalThis.MESSENGER_RUNTIME.migrate(maintenance.source, maintenance.fingerprint) : globalThis.MESSENGER_RUNTIME.purge(maintenance.fingerprint),
          { migration: null, retention: null, maintenanceNotice: this.state.migration ? 'Reprise terminée. Aucun agent n’a été réveillé.' : 'Suppression effectuée selon l’aperçu.' }),

        foot: kind === 'invite' ? 'Colle-la dans le chat de ton agent : il crée son compte tout seul, dans ce projet.'
          : (kind === 'project' ? 'Aucun agent n\u2019est prévenu : copie ensuite l\u2019invite du projet.'
          : (kind === 'adv' ? 'Son adresse ne change pas.' : '')),
        cancel: kind === 'setup' || kind === 'poste' ? 'Fermer' : 'Annuler',
        hasPrimary: kind === 'invite' || kind === 'project' || kind === 'adv',
        primaryLabel: kind === 'invite' ? (this.state.copied ? 'Invite copiée' : 'Copier l\u2019invite') : (kind === 'project' ? 'Créer le projet' : 'Enregistrer'),
        primaryIcon: L(kind === 'invite' ? (this.state.copied ? 'check' : 'copy') : (kind === 'project' ? 'plus' : 'check')),
        primaryBorder: 'rgba(var(--w), 0.2)',
        primaryBg: 'rgba(var(--w), 0.08)',
        primaryColor: 'var(--tx1)',
        primary: () => {
          if (kind === 'invite') return copyInvite(this.state.inviteChoice);
          if (kind === 'project') {
            const problem = projectProblem(newProject);
            if (problem) return this.setState({ projectNotice: problem });
            // Créé : on passe à l'invite, projet présélectionné sans attendre la relève suivante.
            // Un refus reste dans la fenêtre du projet, effacé dès que le nom change.
            if (this.state.busy) return;
            this.setState({ busy: true, projectNotice: null });
            return globalThis.MESSENGER_RUNTIME.createProject(newProject).then((created) => {
              if (this.state.modal === 'project') this._openModal('invite');
              const projects = this.state.projects;
              this.setState({ busy: false, inviteChoice: created, projName: '', copied: false,
                projects: projects.some((p) => p.name === created) ? projects : [...projects, { name: created }] });
              return this._refresh();
            }, (error) => this.setState({ busy: false, projectNotice: String(error) }));
          }
          // Un rôle en cours de saisie part avec le reste plutôt que d'être perdu.
          const role = kind === 'adv' && ma && this.state.roleEdit === ma[1] ? this.state.roleDraft.trim() : null;
          if (role !== null && roleProblem(role)) return this.setState({ accountNotice: { address: ma[1], text: roleProblem(role) } });
          if (kind === 'adv' && ma) return (async () => {
            const runtime = globalThis.MESSENGER_RUNTIME;
            // Le rôle passe d'abord par le chemin du compte : un refus reste sous le champ, jamais en signalement.
            if (role !== null && role !== ma[5] && !(await this._account(ma[1], () => runtime.updateAccount(ma[1], role), { roleEdit: null, roleDraft: '' }))) return;
            return this._run(async () => {
              if (this.state.contactAlias.trim()) {
                const current = this.state.directory.find((entry) => entry.account.address === ma[1]).contacts;
                const contact = { alias: this.state.contactAlias.trim(), addresses: pickedNames, note: this.state.contactNote };
                await runtime.contacts(ma[1], current.filter((c) => c.alias !== contact.alias).concat([contact]));
              }
              if (this.state.fileTarget !== null) await runtime.file(ma[1], this.state.fileTarget);
              if (this.state.mergeTarget) await runtime.merge(ma[1], this.state.mergeTarget);
            }, { modal: null, modalAgent: null, ...ACCOUNT_IDLE });
          })();
        },
      },
    };
    return globalThis.MESSENGER_I18N.render(values, this.state.lang);
  }
}
