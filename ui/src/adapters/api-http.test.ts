import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import type { Etat, Message } from '../domain/types.ts';
import { ApiHttp, messageDErreur, normaliser } from './api-http.ts';

describe("ce qu'on dit quand l'API refuse", () => {
  it("reprend le message de l'API, qui dit quoi faire", () => {
    // les textes d'erreur du backend Python sont des contrats lus par des agents : jamais traduits
    assert.equal(messageDErreur('fr', 400, 'dossier introuvable : /nulle/part'), 'dossier introuvable : /nulle/part');
    assert.equal(messageDErreur('en', 501, "la fenêtre de choix n'a pas pu s'ouvrir"), "la fenêtre de choix n'a pas pu s'ouvrir");
  });
  it("nomme une application plus ancienne que la page, au lieu d'un « introuvable » muet", () => {
    assert.match(messageDErreur('fr', 404, 'introuvable'), /relance-la/);
    assert.match(messageDErreur('fr', 404, null), /relance-la/);
    // un 404 qui s'explique lui-même (pièce jointe absente…) garde son message
    assert.equal(messageDErreur('fr', 404, 'pièce jointe introuvable : x.md'), 'pièce jointe introuvable : x.md');
  });
  it('sans message, renvoie au terminal', () => {
    assert.match(messageDErreur('fr', 500, null), /HTTP 500/);
  });
  it('trouve ses mots en anglais comme en français', () => {
    assert.match(messageDErreur('en', 404, null), /start it again/);
    assert.match(messageDErreur('en', 500, null), /HTTP 500/);
  });
});

describe("quand l'API ne répond pas", () => {
  it('conseille de relancer le serveur, dans la langue de l’interface', async () => {
    // fetch échoue (URL relative absente sous node) : le message fabriqué côté interface suit la langue
    await assert.rejects(() => new ApiHttp().eteindre(), /relance/);
    await assert.rejects(() => new ApiHttp('', () => 'en').eteindre(), /restart/);
  });
});

/** Une boîte allumée plus ancienne que cette page : elle doit s'afficher, et le dire.
 *
 * Le cas est réel (20/09/2026) : le serveur laissé allumé était en 0.1.15, la page reconstruite
 * attendait le champ `mien` arrivé en 0.1.18. Sans lui, l'interface ne s'affichait plus du tout —
 * « la boîte est down », alors que la boîte allait très bien. Le `404` ci-dessus couvre la route
 * qui n'existe pas ; ici, la route existe et c'est sa forme qui a vieilli.
 */
type Brut = Omit<Message, 'mien' | 'statuts'> & Partial<Pick<Message, 'mien' | 'statuts'>>;

function etat(messages: Brut[], compte = 'owner'): Parameters<typeof normaliser>[0] {
  return {
    source: { chemin: '/b.json', nom: 'b.json', format: 'json', lecture_seule: false, demonstration: false,
      activable: true },
    compte, projets: [], invite: null, notifications: null, version: 'v1', comptes: [], messages,
  };
}

function message(extra: Partial<Brut> = {}): Brut {
  return {
    id: 'a', date: '2026-09-20T20:45:00', de: 'windows', a: ['owner', 'kimi'], objet: 'objet',
    corps: [], pj: null, re: null, statut: 'nouveau', historique: [], suite: null, pj_presente: false,
    ...extra,
  };
}

describe('une API plus ancienne que cette page', () => {
  it('reconstruit `mien` depuis les statuts, et le signale', () => {
    const vu: Etat = normaliser(etat([message({ statuts: { owner: 'lu', kimi: 'nouveau' } })]));
    assert.equal(vu.messages[0]?.mien, 'lu');       // le statut du compte courant, comme le ferait le serveur
    assert.equal(vu.obsolete, true);
  });

  it('se rabat sur le statut d’ensemble quand rien d’autre n’est envoyé', () => {
    const vu = normaliser(etat([message({ statut: 'traité' })]));
    assert.equal(vu.messages[0]?.mien, 'traité');
    assert.deepEqual(vu.messages[0]?.statuts, {});
  });

  it('ne dit rien quand l’API est à jour', () => {
    const vu = normaliser(etat([message({ mien: 'lu', statuts: { owner: 'lu', kimi: 'nouveau' } })]));
    assert.equal(vu.obsolete, false);
    assert.equal(vu.messages[0]?.mien, 'lu');
  });

  it('une boîte vide ne se déclare pas obsolète', () => {
    assert.equal(normaliser(etat([])).obsolete, false);
  });
});
