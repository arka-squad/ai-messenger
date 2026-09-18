import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import {
  FILTRE_INITIAL,
  adresseCourte,
  agents,
  cleJour,
  compter,
  couloirs,
  fil,
  filtrer,
  initiales,
  libelleJour,
  projets,
  projetsDe,
  recents,
  titre,
} from './boite.ts';
import type { Message } from './types.ts';

function message(id: string, date: string, de: string, a: string[], extra: Partial<Message> = {}): Message {
  return {
    id, date, de, a, objet: `objet ${id}`, corps: [], pj: null, re: null, statut: 'nouveau',
    historique: [], suite: null, pj_presente: false, ...extra,
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
    assert.deepEqual(projets(['cortex', 'talos'], P), [
      { nom: 'cortex', messages: 2, nouveaux: 1 },
      { nom: 'talos', messages: 2, nouveaux: 1 },
    ]);
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

describe('initiales', () => {
  it('prend une lettre par segment', () => {
    assert.equal(initiales('owner'), 'OW');
    assert.equal(initiales('claude-windows'), 'CW');
    assert.equal(initiales('claude-windows@cortex'), 'CW');
  });
});
