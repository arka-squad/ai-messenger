import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import {
  FILTRE_INITIAL,
  adresseCourte,
  affichagesDe,
  agents,
  anciennete,
  attend,
  cleJour,
  compter,
  couloirs,
  fil,
  filtrer,
  groupesAgents,
  initiales,
  libelleJour,
  nomAffiche,
  projetPropose,
  projets,
  projetsDe,
  projetsDesComptes,
  recents,
  statutPour,
  teinteProjet,
  TEINTES,
  titre,
} from './boite.ts';
import type { Message } from './types.ts';

function message(id: string, date: string, de: string, a: string[], extra: Partial<Message> = {}): Message {
  const m = {
    id, date, de, a, objet: `objet ${id}`, corps: [], pj: null, re: null, statut: 'nouveau' as const,
    statuts: {}, mien: 'nouveau' as const, historique: [], suite: null, pj_presente: false, ...extra,
  };
  // comme l'API : chaque destinataire porte le statut du message, et `mien` est celui du compte qui regarde
  return {
    ...m,
    statuts: extra.statuts ?? Object.fromEntries(a.map((x) => [x, m.statut])),
    mien: extra.mien ?? m.statut,
  };
}

const M = [
  message('a', '2026-09-18T09:00:00', 'windows', ['kimi'], { pj: 'rapport.md' }),
  message('b', '2026-09-18T10:30:00', 'kimi', ['windows', 'owner'], { re: 'a', statut: 'lu' }),
  message('c', '2026-09-17T22:50:00', 'mac', ['windows'], { statut: 'traité', corps: ['relevé urgent'] }),
];

describe('titre et dates', () => {
  it('préfixe une réponse', () => {
    assert.equal(titre(M[1]!), 'Re : a — objet b');
    assert.equal(titre(M[0]!), 'objet a');
  });
  it('clé et libellé du jour', () => {
    assert.equal(cleJour(new Date('2026-09-18T23:59:00')), '20260918');
    assert.equal(libelleJour('20260918', new Date('2026-01-01T00:00:00')), '18 septembre');
    assert.equal(libelleJour('20250918', new Date('2026-01-01T00:00:00')), '18 septembre 2025');
  });
});

describe('liste', () => {
  it('ordonne du plus récent au plus ancien', () => {
    assert.deepEqual(recents(M).map((m) => m.id), ['b', 'a', 'c']);
  });
  it('filtre par classement, statut, agent et recherche', () => {
    const f = FILTRE_INITIAL;
    assert.deepEqual(filtrer(M, { ...f, classement: 'fils' }, 'owner').map((m) => m.id), ['b']);
    assert.deepEqual(filtrer(M, { ...f, classement: 'pj' }, 'owner').map((m) => m.id), ['a']);
    assert.deepEqual(filtrer(M, { ...f, classement: 'moi' }, 'owner').map((m) => m.id), ['b']);
    assert.deepEqual(filtrer(M, { ...f, statut: 'traité' }, 'owner').map((m) => m.id), ['c']);
    assert.deepEqual(filtrer(M, { ...f, agent: 'mac' }, 'owner').map((m) => m.id), ['c']);
    assert.deepEqual(filtrer(M, { ...f, recherche: 'URGENT' }, 'owner').map((m) => m.id), ['c']);
    assert.deepEqual(filtrer(M, { ...f, recherche: 'rapport' }, 'owner').map((m) => m.id), ['a']);
  });
  it('compte', () => {
    assert.deepEqual(compter(M, 'owner'), { total: 3, nouveau: 1, lu: 1, traité: 1, fils: 1, pj: 1, moi: 1 });
  });
});

describe('agents et trafic', () => {
  it('classe les agents du plus récemment actif au silencieux', () => {
    const comptes = ['owner', 'mac', 'windows', 'kimi', 'ancien'].map((nom) => ({ nom, actif: nom !== 'ancien' }));
    const liste = agents(comptes, M);
    assert.deepEqual(liste.map((a) => a.nom), ['kimi', 'windows', 'mac', 'owner']);
    assert.equal(liste.find((a) => a.nom === 'kimi')?.enAttente, 1);
    assert.equal(liste.find((a) => a.nom === 'owner')?.dernierEnvoi, null);
  });
  it('trace un couloir par agent actif ce jour-là', () => {
    const c = couloirs(M, '20260918', ['windows', 'mac', 'kimi', 'owner']);
    assert.deepEqual(c.map((x) => x.agent), ['windows', 'kimi', 'owner']);
    const windows = c[0]!;
    assert.deepEqual(windows.points.map((p) => [p.message.id, p.minutes, p.envoye]), [['a', 540, true], ['b', 630, false]]);
  });
});

describe('fil', () => {
  it('rend le message parent puis les réponses', () => {
    assert.deepEqual(fil(M, M[1]!).map((m) => m.id), ['a']);
    assert.deepEqual(fil(M, M[0]!).map((m) => m.id), ['b']);
    assert.deepEqual(fil(M, M[2]!), []);
  });
});

describe('projets', () => {
  const P = [
    message('p1', '2026-09-18T09:00:00', 'kimi@cortex', ['claude@cortex']),
    message('p2', '2026-09-18T10:00:00', 'kimi@cortex', ['claude@talos', 'owner'], { statut: 'lu' }),
    message('p3', '2026-09-18T11:00:00', 'claude@talos', ['owner']),
  ];
  it('un projet voit ses messages, discussion inter-projet comprise', () => {
    assert.deepEqual(filtrer(P, { ...FILTRE_INITIAL, projet: 'cortex' }, 'owner').map((m) => m.id), ['p1', 'p2']);
    assert.deepEqual(filtrer(P, { ...FILTRE_INITIAL, projet: 'talos' }, 'owner').map((m) => m.id), ['p2', 'p3']);
    const comptes = ['kimi@cortex', 'claude@cortex', 'owner'].map((nom) => ({ nom, actif: true }));
    assert.deepEqual(projets(['cortex', 'talos'], P, comptes), [
      { nom: 'cortex', messages: 2, nouveaux: 1, agents: 2 },
      { nom: 'talos', messages: 2, nouveaux: 1, agents: 0 },
    ]);
  });
  it('les agents se rangent par projet, les comptes communs à la fin', () => {
    const comptes = ['owner', 'kimi@cortex', 'claude@talos', 'claude@cortex'].map((nom) => ({ nom, actif: true }));
    const groupes = groupesAgents(agents(comptes, P), ['cortex', 'neuf']);
    assert.deepEqual(groupes.map((g) => [g.projet, g.agents.map((a) => a.nom).sort()]), [
      ['cortex', ['claude@cortex', 'kimi@cortex']],
      ['neuf', []],                 // connecté, pas encore d'agent : il se voit quand même
      ['talos', ['claude@talos']],  // inconnu de la liste : trouvé par ses agents
      [null, ['owner']],
    ]);
    assert.deepEqual(groupesAgents([], []).map((g) => g.projet), [null]);
  });
  it("un compte commun rangé dans un projet en fait partie, sans changer d'adresse", () => {
    const comptes = [
      { nom: 'windows', actif: true, projet: 'cortex' },
      { nom: 'owner', actif: true, projet: null },
      { nom: 'claude@talos', actif: true },
    ];
    const de = projetsDesComptes(comptes);
    assert.deepEqual(['windows', 'owner', 'claude@talos', 'inconnu@x'].map(de), ['cortex', null, 'talos', 'x']);
    const m = message('r1', '2026-09-18T09:00:00', 'owner', ['windows']);
    assert.deepEqual(projetsDe(m, de), ['cortex']);
    assert.deepEqual(filtrer([m], { ...FILTRE_INITIAL, projet: 'cortex' }, 'owner', de).map((x) => x.id), ['r1']);
    assert.deepEqual(filtrer([m], { ...FILTRE_INITIAL, projet: 'cortex' }, 'owner').map((x) => x.id), []);
    assert.deepEqual(groupesAgents(agents(comptes, [m]), ['cortex']).map((g) => [g.projet, g.agents.map((a) => a.nom)]), [
      ['cortex', ['windows']], ['talos', ['claude@talos']], [null, ['owner']],
    ]);
    assert.equal(projets(['cortex'], [m], comptes)[0]?.agents, 1);
  });
  it("un agent qui ne relève pas se voit : depuis quand son courrier attend", () => {
    const comptes = [{ nom: 'mac', actif: true, hote: 'inconnu' }, { nom: 'owner', actif: true, hote: 'humain' }];
    const recus = [
      message('w1', '2026-09-18T09:00:00', 'owner', ['mac']),
      message('w2', '2026-09-18T07:00:00', 'owner', ['mac']),
    ];
    const mac = agents(comptes, recus).find((a) => a.nom === 'mac');
    assert.equal(mac?.enAttente, 2);
    assert.equal(mac?.attenteDepuis?.getHours(), 7);
    assert.equal(mac?.aCompleter, true);
    const maintenant = new Date('2026-09-18T11:00:00');
    assert.equal(anciennete(new Date('2026-09-18T10:40:00'), maintenant), 'depuis 20 min');
    assert.equal(anciennete(new Date('2026-09-18T07:00:00'), maintenant), 'depuis 4 h');
    assert.equal(anciennete(new Date('2026-09-14T11:00:00'), maintenant), 'depuis 4 j');
  });
  it('un projet garde sa teinte, et un dossier propose un nom de projet valide', () => {
    assert.equal(teinteProjet('cortex'), teinteProjet('cortex'));
    assert.ok(teinteProjet('cortex') >= 0 && teinteProjet('cortex') < TEINTES);
    assert.equal(projetPropose('C:\\Users\\moi\\Projets\\Cortex Deck\\'), 'cortex-deck');
    assert.equal(projetPropose('/Users/moi/dépôts/Été_2026'), 'ete_2026');
    assert.equal(projetPropose('/'), '');
  });
  it('les agents d\'un projet, plus les comptes communs', () => {
    const comptes = ['kimi@cortex', 'claude@talos', 'owner'].map((nom) => ({ nom, actif: true }));
    assert.deepEqual(agents(comptes, P, 'cortex').map((a) => a.nom).sort(), ['kimi@cortex', 'owner']);
  });
  it('une adresse du projet affiché se lit sans son projet', () => {
    assert.equal(adresseCourte('kimi@cortex', 'cortex'), 'kimi');
    assert.equal(adresseCourte('claude@talos', 'cortex'), 'claude@talos');
    assert.equal(adresseCourte('kimi@cortex', null), 'kimi@cortex');
  });
  it('les projets qu\'un message touche, sans doublon et sans les comptes communs', () => {
    assert.deepEqual(projetsDe(P[0]!), ['cortex']);
    assert.deepEqual(projetsDe(P[1]!), ['cortex', 'talos']);
    assert.deepEqual(projetsDe(P[2]!), ['talos']);
    assert.deepEqual(projetsDe(message('x', '2026-09-18T09:00:00', 'owner', ['owner'])), []);
  });
});

describe('nom affiché', () => {
  const table = affichagesDe([
    { nom: 'cl-agent-x-win@demo', actif: true, affichage: 'CL_Agent-X_WIN' },
    { nom: 'kimi@demo', actif: true },
  ]);
  it('préfère le nom lisible enrôlé, sinon l’adresse courte', () => {
    assert.equal(nomAffiche('cl-agent-x-win@demo', table, 'demo'), 'CL_Agent-X_WIN');
    assert.equal(nomAffiche('kimi@demo', table, 'demo'), 'kimi');
    assert.equal(nomAffiche('owner', table, 'demo'), 'owner');
  });
});

describe('initiales', () => {
  it('prend une lettre par segment', () => {
    assert.equal(initiales('owner'), 'OW');
    assert.equal(initiales('claude-windows'), 'CW');
    assert.equal(initiales('claude-windows@cortex'), 'CW');
  });
});

describe('un statut par destinataire', () => {
  /** Le cas du 20/09 : l'humain a lu l'annonce dans l'interface, les agents ne l'ont pas encore vue. */
  const annonce = message('z', '2026-09-20T20:45:00', 'windows', ['owner', 'kimi'], {
    statut: 'nouveau', statuts: { owner: 'lu', kimi: 'nouveau' }, mien: 'lu',
  });

  it('dit où en est chacun, et qui attend encore', () => {
    assert.equal(statutPour(annonce, 'owner'), 'lu');
    assert.equal(statutPour(annonce, 'kimi'), 'nouveau');
    assert.equal(statutPour(annonce, 'windows'), null); // l'expéditeur n'est pas destinataire
    assert.ok(attend(annonce, 'kimi'));
    assert.ok(!attend(annonce, 'owner'));
  });

  it('filtre et compte sur le statut de celui qui regarde', () => {
    assert.deepEqual(filtrer([annonce], { ...FILTRE_INITIAL, statut: 'lu' }, 'owner').map((m) => m.id), ['z']);
    assert.deepEqual(filtrer([annonce], { ...FILTRE_INITIAL, statut: 'nouveau' }, 'owner'), []);
    assert.equal(compter([annonce], 'owner').lu, 1);
    assert.equal(compter([annonce], 'owner').nouveau, 0);
  });

  it('un agent qui n’a pas lu reste en attente sur sa fiche', () => {
    const fiches = agents([{ nom: 'owner', actif: true }, { nom: 'kimi', actif: true }], [annonce]);
    const parNom = new Map(fiches.map((f) => [f.nom, f.enAttente]));
    assert.equal(parNom.get('kimi'), 1);
    assert.equal(parNom.get('owner'), 0);
  });

  it('une réponse d’API sans `statuts` se lit quand même', () => {
    const ancien = { ...annonce, statuts: {} as Record<string, never> };
    assert.equal(statutPour(ancien, 'kimi'), 'nouveau'); // repli sur la vue d'ensemble
  });
});
