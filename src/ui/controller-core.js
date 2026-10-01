const L = (n) => `./assets/icons/${n}.svg`;
const { ME, TINTS, ST, ORDER, initialState } = globalThis.MESSENGER_PRESENTATION;

class Component extends DCLogic {
  state = initialState();

  componentDidMount() {
    this._refresh();
    this._poll = setInterval(() => this._refresh(), 2500);
    globalThis.MESSENGER_RUNTIME.listenMessage((id) => this.setState({ sel: id, box: 'toutes' }))?.then((stop) => { this._unlisten = stop; });
  }
  componentWillUnmount() { clearTimeout(this._p); clearInterval(this._poll); this._unlisten?.(); }
  async _refresh() {
    if (this._refreshing) return;
    this._refreshing = true;
    try {
      const snapshot = await globalThis.MESSENGER_RUNTIME.snapshot();
      const clock = Math.floor(Date.now() / 60000);
      if (snapshot.fingerprint !== this._fingerprint) {
        this._fingerprint = snapshot.fingerprint;
        const openGroups = { ...this.state.openGroups };
        snapshot.directory.forEach(({ account }) => { const project = account.address.split('@')[1] || account.project || 'commun'; if (!(project in openGroups)) openGroups[project] = true; });
        this.setState({ ...snapshot, ...snapshot.preferences, openGroups, clock, loading: false }, () => this._applyTheme());
      } else if (this.state.loading) this.setState({ loading: false });
      else if (this.state.clock !== clock) this.setState({ clock });
    } catch (error) { this.setState({ loading: false, providerNotice: String(error) }); }
    finally { this._refreshing = false; }
  }
  async _run(work, patch = {}) {
    if (this.state.busy) return;
    this.setState({ busy: true, providerNotice: null });
    try { const result = await work(); this.setState({ ...patch, busy: false }); await this._refresh(); return result; }
    catch (error) { this.setState({ busy: false, providerNotice: String(error) }); }
  }
  _preference(key, value) {
    const preferences = { theme: this.state.theme, lang: this.state.lang, notif: this.state.notif, [key]: value };
    return this._run(() => globalThis.MESSENGER_RUNTIME.preferences(preferences), preferences);
  }
  _reload() { this._refresh(); }
  _projects() {
    return [...new Set(this.state.projects.map((p) => p.name).concat(this.state.directory.map(({ account }) => account.address.split('@')[1] || account.project).filter(Boolean)))];
  }
  _applyTheme() {
    const el = this._root;
    if (!el) return;
    const light = this.state.theme === 'light';
    el.classList.toggle('theme-light', light);
    const doc = el.ownerDocument;
    doc.documentElement.classList.toggle('theme-light', light);
    doc.body.classList.toggle('theme-light', light);
    doc.body.style.background = light ? '#ECE8E1' : '#171718';
  }

  _tint(p) {
    if (!p) return TINTS[3];
    const i = this._projects().indexOf(p);
    return TINTS[i < 0 ? 2 : i % TINTS.length];
  }

  _msgs() {
    const directory = Object.fromEntries(this.state.directory.map(({ account }) => [account.address, account]));
    return this.state.mail.map((r) => {
      const date = new Date(r.emitted_at);
      const valid = Number.isFinite(date.getTime());
      const stamp = valid ? new Intl.DateTimeFormat('sv-SE', { timeZone: 'Europe/Paris', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false }).format(date).replace(' ', 'T') : '';
      const hh = stamp.slice(11, 13), mm = stamp.slice(14, 16);
      const ranks = Object.values(r.statuts).map((st) => ORDER.indexOf(st)).filter((rank) => rank >= 0);
      const overall = r.overall || ORDER[ranks.length ? Math.min(...ranks) : 0];
      const projects = [...new Set([r.from, ...r.to, ...(r.copies || [])].map((address) => address.split('@')[1] || directory[address]?.project || 'commun'))];
      return { ...r, day: stamp.slice(0, 10).replaceAll('-', ''), hhmm: valid ? hh + ':' + mm : '—',
        minutes: valid ? Number(hh) * 60 + Number(mm) : 0, date: valid ? date.getTime() : 0,
        mine: null, overall, status: overall, forMe: false, actor: false, projects };
    }).sort((a, b) => b.date - a.date || b.id.localeCompare(a.id));
  }
  _visible(all) {
    const f = this.state.filter, b = this.state.box, ag = this.state.agent, p = this.state.project;
    const q = this.state.query.trim().toLowerCase();
    return all.filter((m) => {
      if (f && m.status !== f) return false;
      if (b === 'fils' && !m.re) return false;
      if (b === 'pj' && !m.pj) return false;
      if (b === 'moi') return false;
      if (ag && m.from !== ag && m.to.indexOf(ag) < 0) return false;
      if (p && m.projects.indexOf(p) < 0) return false;
      if (q) {
        const hay = [m.id, m.re, m.objet, m.pj, m.from, m.to.join(' '), m.body.join(' ')].join(' ').toLowerCase();
        if (hay.indexOf(q) < 0) return false;
      }
      return true;
    });
  }

  _openModal(kind, agentName) {
    this.setState({ modal: kind, modalAgent: agentName || null, copied: false, browsing: false, mergeTarget: null, fileTarget: null, contactAlias: '', contactNote: '', contactTargets: {}, providerNotice: null,
      remoteUrl: kind === 'poste' && this.state.exchange?.kind === 'url' ? this.state.exchange.path : '', remoteToken: '', remoteBusy: false });
  }

  renderVals() {
    const AGENTS = this.state.directory.map((entry) => {
      const a = entry.account;
      const last = entry.last_collection ? new Intl.DateTimeFormat('fr-FR', { timeZone: 'Europe/Paris', hour: '2-digit', minute: '2-digit' }).format(new Date(entry.last_collection)) : '';
      const age = entry.oldest_waiting ? Math.max(0, Math.floor((Date.now() - new Date(entry.oldest_waiting).getTime()) / 3600000)) + ' h' : '';
      return [a.address, a.address, a.address.split('@')[1] || a.project || '', a.host || 'inconnu', a.machine || '—', a.role, last, entry.waiting, age,
        entry.contacts.map((c) => [c.alias, c.addresses.join(', '), c.note, c.addresses]), a.display || a.address];
    });
    const byName = Object.fromEntries(AGENTS.map((a) => [a[0], a]));
    const SCENARIO = { projectNames: this._projects(), trafficDay: new Intl.DateTimeFormat('sv-SE', { timeZone: 'Europe/Paris' }).format(new Date()).replaceAll('-', ''),
      connectedProjectsText: this._projects().length ? 'Projets connectés : ' + this._projects().join(', ') : 'Aucun projet connecté.', projectPlaceholder: 'ex. talos' };
    const light = this.state.theme === 'light';
    const parisClock = new Intl.DateTimeFormat('en-GB', { timeZone: 'Europe/Paris', hour: '2-digit', minute: '2-digit', hour12: false }).format(new Date()).split(':');
    const parisMinutes = Number(parisClock[0]) * 60 + Number(parisClock[1]);
    const all = this._msgs();
    const visible = this._visible(all);
    const tally = { nouveau: 0, lu: 0, 'traité': 0 };
    all.forEach((m) => { tally[m.status] = (tally[m.status] || 0) + 1; });

    let sel = all.find((m) => m.id === this.state.sel);
    if (!sel || visible.indexOf(sel) < 0) sel = visible[0] || all[0];

    // ——— frise
    const day = SCENARIO.trafficDay;
    const dayMsgs = all.filter((m) => m.day === day && (!this.state.project || m.projects.indexOf(this.state.project) >= 0));
    const laneIds = [];
    dayMsgs.forEach((m) => {
      [m.from].concat(m.to).forEach((n) => { if (laneIds.indexOf(n) < 0) laneIds.push(n); });
    });
    const lanes = laneIds.map((n) => {
      const mine = dayMsgs.filter((m) => m.from === n || m.to.indexOf(n) >= 0);
      return {
        id: n,
        short: n.length > 24 ? n.slice(0, 23) + '…' : n,
        nameColor: this.state.agent === n ? 'var(--tx1)' : 'var(--tx4)',
        pick: () => { this.setState((s) => ({ agent: s.agent === n ? null : n })); },
        dots: mine.map((m, i) => {
          const sent = m.from === n;
          const on = sel && m.id === sel.id;
          return {
            left: (m.minutes / 1440 * 100).toFixed(2) + '%',
            size: on ? '11px' : (sent ? '9px' : '7px'),
            bg: sent ? (on ? 'var(--tx1)' : 'rgba(var(--w), 0.44)') : 'transparent',
            ring: on ? 'var(--tx1)' : 'rgba(var(--w), 0.34)',
            delay: (i * 40) + 'ms',
            title: m.hhmm + ' · ' + (sent ? 'envoyé' : 'reçu') + ' · ' + m.from + ' → ' + m.to.join(', ') + ' · ' + m.objet,
            pick: () => this.setState({ sel: m.id }),
          };
        }),
      };
    });

    const ticks = [0, 6, 12, 18, 24].map((h, i, a) => ({
      left: (h / 24 * 100).toFixed(2) + '%',
      shift: i === 0 ? 'none' : (i === a.length - 1 ? 'translateX(-100%)' : 'translateX(-50%)'),
      label: (h < 10 ? '0' + h : h) + ':00',
    }));

    // ——— groupes d'agents
    const projNames = SCENARIO.projectNames;
    const groups = projNames.concat(['commun']).map((p) => {
      const key = p;
      const list = AGENTS.filter((a) => (a[2] || 'commun') === p);
      const open = !!this.state.openGroups[key];
      const waiting = list.reduce((n, a) => n + a[7], 0);
      const count = all.filter((m) => m.projects.indexOf(p) >= 0).length;
      const tint = p === 'commun' ? TINTS[3] : this._tint(p);
      return {
        name: p === 'commun' ? 'commun' : p,
        tint, open, count: String(count),
        caret: open ? 'rotate(90deg)' : 'none',
        bg: this.state.project === p ? 'rgba(var(--w), 0.07)' : 'transparent',
        hasNew: waiting > 0, newTitle: waiting + ' message(s) en attente dans ce projet',
        empty: list.length === 0,
        toggle: () => this.setState((s) => ({ openGroups: Object.assign({}, s.openGroups, { [key]: !s.openGroups[key] }) })),
        pick: () => { this.setState((s) => ({ project: s.project === p ? null : p })); this._reload(); },
        agents: list.map((a) => {
          const on = this.state.agent === a[0];
          const panel = this.state.agentPanel === a[0];
          return {
            name: a[10],
            title: a[1] + '\n' + a[3] + ' · ' + a[4] + '\n' + (a[5] || 'Aucune information sur ce compte.'),
            dot: a[7] > 0 ? 'var(--warn-tx)' : (a[6] ? 'var(--pass-tx)' : 'var(--tx5)'),
            pulse: a[7] > 0 ? 'pulse' : '',
            color: on || panel ? 'var(--tx1)' : 'var(--tx3)',
            bg: panel ? 'rgba(var(--w), 0.08)' : (on ? 'rgba(var(--w), 0.05)' : 'transparent'),
            border: panel ? 'rgba(var(--w), 0.16)' : 'transparent',
            last: a[6] ? 'dernier ' + a[6] : 'silencieux',
            waiting: a[7] > 0,
            waitLabel: a[7] + ' en attente depuis ' + a[8],
            open: () => this.setState({ agentPanel: a[0] }),
            more: (e) => { if (e && e.stopPropagation) e.stopPropagation(); this._openModal('adv', a[0]); },
          };
        }),
      };
    });

    // ——— incidents
    const incidents = this.state.incidents.filter((incident) => !this.state.hidden[incident.id]).map((incident) => ({
      icon: L('triangle-alert'), canHide: true, text: incident.message, cta: incident.message_id ? 'Voir le message' : 'Voir les réglages',
      act: () => incident.message_id ? this.setState({ sel: incident.message_id, box: 'toutes' }) : this._openModal('poste'),
      hide: () => this.setState((state) => ({ hidden: { ...state.hidden, [incident.id]: true } })),
    }));
    const pjMiss = all.find((m) => m.pj && m.pjMissing);
    if (pjMiss && !this.state.hidden.pj) {
      incidents.push({
        icon: L('file-x'), canHide: true,
        text: 'Une pièce jointe annoncée n\u2019est pas dans le dossier de la boîte : ' + pjMiss.pj,
        cta: 'Voir le message',
        act: () => this.setState({ sel: pjMiss.id }),
        hide: () => this.setState((s) => ({ hidden: Object.assign({}, s.hidden, { pj: true }) })),
      });
    }
    const orphan = AGENTS.find((a) => a[3] === 'inconnu');
    if (orphan && !this.state.hidden.orphan) {
      incidents.push({
        icon: L('user-round-x'), canHide: true,
        text: orphan[0] + ' a été repris d\u2019une ancienne boîte : son agent ne l\u2019a jamais repris, il ne relève donc pas son courrier.',
        cta: 'Envoyer son invite',
        act: () => this.setState({ agentPanel: orphan[0] }),
        hide: () => this.setState((s) => ({ hidden: Object.assign({}, s.hidden, { orphan: true }) })),
      });
    }
    if (this.state.providerNotice) {
      incidents.push({
        icon: L('wrench'), canHide: true,
        text: this.state.providerNotice,
        cta: 'Voir les outils',
        act: () => this._openModal('poste'),
        hide: () => this.setState({ providerNotice: null }),
      });
    }

    // ——— message sélectionné
    const s = sel || {};
    const si = ORDER.indexOf(s.mine || s.overall || 'nouveau');
    const hist = { 'nouveau': 'envoyé par ' + s.from, 'lu': 'lu', 'traité': 'traité' };
    const steps = ORDER.map((st, i) => ({
      label: ST[st].word,
      dot: i <= si ? (i === si ? 'var(--tx1)' : 'rgba(var(--w), 0.34)') : 'rgba(var(--w), 0.14)',
      color: i === si ? 'var(--tx1)' : 'var(--tx5)',
      line: i < 2 ? 'rgba(var(--w), 0.14)' : 'transparent',
      pulse: i === si && st !== 'traité' ? 'pulse' : '',
      title: i <= si ? hist[st] + (i === 0 ? ' le ' + (s.day || '') : '') : 'Étape pas encore atteinte',
    }));

    const canAct = !!s.forMe && s.mine !== 'traité';
    const nextStatus = s.mine === 'nouveau' ? 'lu' : 'traité';
    const thread = all.filter((m) => s.id && m.id !== s.id && (m.re === s.id || (s.re && m.id === s.re)))
      .map((m) => ({
        id: m.id, objet: m.objet, dot: ST[m.status].color, bg: 'transparent',
        pick: () => this.setState({ sel: m.id }),
      }));

    // ——— fils de discussion
    const byId = {};
    all.forEach((m) => { byId[m.id] = m; });
    const rootOf = (m) => {
      let cur = m, guard = 0;
      while (cur.re && guard < 20) {
        if (byId[cur.re]) { cur = byId[cur.re]; guard += 1; } else return cur.re;
      }
      return cur.id;
    };
    const strip = (o) => o.replace(/^Re\s*:\s*\S+\s*—\s*/, '');
    const tOrder = [];
    const tMap = {};
    visible.forEach((m) => {
      const r = rootOf(m);
      if (!tMap[r]) { tMap[r] = []; tOrder.push(r); }
      tMap[r].push(m);
    });
    const threads = tOrder.map((r, gi) => {
      const asc = tMap[r].slice().sort((a, b) => (a.date - b.date || a.id.localeCompare(b.id)));
      const items = tMap[r].slice().sort((a, b) => (b.date - a.date || b.id.localeCompare(a.id)));
      const newest = items[0], oldest = items[items.length - 1];
      const present = {};
      asc.forEach((m) => { present[m.id] = m; });
      const depthOf = (m) => {
        let d = 0, cur = m, guard = 0;
        while (cur.re && present[cur.re] && guard < 20) { cur = present[cur.re]; d += 1; guard += 1; }
        return d;
      };
      const tree = asc.map((m) => ({ m, d: depthOf(m) }));
      const people = [];
      items.forEach((m) => { [m.from].concat(m.to).forEach((n) => { if (people.indexOf(n) < 0) people.push(n); }); });
      const tags = [];
      items.forEach((m) => { m.projects.forEach((p) => { if (tags.indexOf(p) < 0) tags.push(p); }); });
      const worst = ORDER[Math.min.apply(null, items.map((m) => ORDER.indexOf(m.status)))];
      const forMe = items.some((m) => m.forMe);
      const actor = items.some((m) => m.actor);
      const holdsSel = sel && items.some((m) => m.id === sel.id);
      const open = this.state.openThreads[r] === undefined ? !!holdsSel : !!this.state.openThreads[r];
      const pjm = items.find((m) => m.pj);
      return {
        title: strip(byId[r] ? byId[r].objet : oldest.objet),
        titleColor: worst === 'nouveau' ? 'var(--tx1)' : 'var(--tx2)',
        weight: worst === 'nouveau' ? 600 : 400,
        people: people.join(', '),
        span: items.length > 1 ? oldest.hhmm + ' → ' + newest.hhmm : newest.hhmm,
        last: newest.day === SCENARIO.trafficDay ? newest.hhmm : newest.day.slice(6, 8) + '/' + newest.day.slice(4, 6),
        count: String(items.length),
        tags: tags.map((p) => ({ name: p, tint: this._tint(p === 'commun' ? '' : p), title: p === 'commun' ? 'Compte commun à tous les projets' : p })),
        stalled: items.length === 1 && !byId[r],
        forMe, roleLabel: actor ? 'on attend ta décision' : 'pour information',
        roleIcon: L(actor ? 'hand' : 'eye'),
        roleColor: actor ? 'var(--warn-tx)' : 'var(--tx4)',
        roleBorder: actor ? 'rgba(217, 119, 6, 0.34)' : 'rgba(var(--w), 0.1)',
        roleBg: actor ? 'rgba(217, 119, 6, 0.10)' : 'transparent',
        hasPj: !!pjm,
        pjIcon: L(pjm && pjm.pjMissing ? 'file-x' : 'paperclip'),
        pjColor: pjm && pjm.pjMissing ? 'var(--warn-tx)' : 'var(--tx5)',
        pjTitle: pjm ? (pjm.pjMissing ? 'Une pièce jointe est absente du dossier' : pjm.pj) : '',
        status: ST[worst].word, statusIcon: L(ST[worst].icon), statusColor: ST[worst].color,
        mark: holdsSel ? 'var(--tx1)' : (worst === 'nouveau' ? 'var(--warn-tx)' : 'transparent'),
        bg: holdsSel ? 'rgba(var(--w), 0.045)' : 'transparent',
        caret: open ? 'rotate(90deg)' : 'none',
        open,
        anim: gi < 10 ? 'drop' : '',
        delay: Math.min(gi, 10) * 26 + 'ms',
        toggle: () => this.setState((st) => ({ openThreads: Object.assign({}, st.openThreads, { [r]: !open }) })),
        items: tree.map((node, ni) => {
        const m = node.m, d = node.d;
        const rails = [];
        for (let k = 0; k < d; k += 1) {
          const last = k === d - 1;
          const deeperLater = tree.slice(ni + 1).some((n) => n.d > k);
          rails.push({
            ml: k === 0 ? '3px' : '0px',
            h: last ? '13px' : (deeperLater ? '100%' : '0px'),
            line: last || deeperLater ? 'rgba(var(--w), 0.16)' : 'transparent',
            bottom: last ? 'rgba(var(--w), 0.16)' : 'transparent',
            radius: last ? '7px' : '0',
          });
        }
        return {
          rails, dotGap: d > 0 ? '1px' : '0px',
          rowDelay: Math.min(ni, 8) * 34 + 'ms',
          when: m.day === SCENARIO.trafficDay ? m.hhmm : m.day.slice(6, 8) + '/' + m.day.slice(4, 6) + ' ' + m.hhmm,
          from: m.from, to: m.to.join(', '),
          short: strip(m.objet),
          objetColor: m.status === 'nouveau' ? 'var(--tx1)' : 'var(--tx3)',
          weight: m.status === 'nouveau' ? 600 : 400,
          status: ST[m.status].word, statusColor: ST[m.status].color,
          hasPj: !!m.pj,
          pjIcon: L(m.pjMissing ? 'file-x' : 'paperclip'),
          pjColor: m.pjMissing ? 'var(--warn-tx)' : 'var(--tx5)',
          pjTitle: m.pjMissing ? 'Ce fichier n\u2019est pas dans le dossier de la boîte.' : m.pj,
          mark: sel && m.id === sel.id ? 'var(--tx1)' : 'transparent',
          bg: sel && m.id === sel.id ? 'rgba(var(--w), 0.06)' : 'transparent',
          pick: () => this.setState({ sel: m.id }),
        };
        }),
      };
    });

    const ap = this.state.agentPanel ? byName[this.state.agentPanel] : null;
    const apSent = ap ? all.filter((m) => m.from === ap[0]).length : 0;
    const apIn = ap ? all.filter((m) => m.to.indexOf(ap[0]) >= 0).length : 0;

    const ma = this.state.modalAgent ? byName[this.state.modalAgent] : null;
    const kind = this.state.modal;
    const modalTitles = {
      setup: ['Mise en place', 'Trois étapes, une seule fois. Tu peux y revenir quand tu veux.'],
      project: ['Connecter un projet', 'Rattache un dossier de projet à la boîte.'],
      invite: ['Inviter un agent', 'Tu obtiens un texte à coller dans le chat de ton agent.'],
      adv: [ma ? ma[0] : '', 'Options avancées de ce compte.'],
      poste: ['Réglages de cet ordinateur', 'La boîte, les outils d\u2019IA, et l\u2019extinction.'],
    };
    const mt = modalTitles[kind] || ['', ''];

    const pool = AGENTS.filter((a) => !ma || a[0] !== ma[0]);
    const match = (a, q) => {
      const s = q.trim().toLowerCase();
      if (!s) return true;
      return (a[0] + ' ' + a[1] + ' ' + (a[2] || '') + ' ' + (a[5] || '')).toLowerCase().indexOf(s) >= 0;
    };
    const mergePool = pool.filter((a) => match(a, this.state.mergeQuery));
    const targetPool = pool.filter((a) => match(a, this.state.targetQuery));
