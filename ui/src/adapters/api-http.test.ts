import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { messageDErreur } from './api-http.ts';

describe("ce qu'on dit quand l'API refuse", () => {
  it("reprend le message de l'API, qui dit quoi faire", () => {
    assert.equal(messageDErreur(400, 'dossier introuvable : /nulle/part'), 'dossier introuvable : /nulle/part');
    assert.equal(messageDErreur(501, "la fenêtre de choix n'a pas pu s'ouvrir"), "la fenêtre de choix n'a pas pu s'ouvrir");
  });
  it("nomme une application plus ancienne que la page, au lieu d'un « introuvable » muet", () => {
    assert.match(messageDErreur(404, 'introuvable'), /relance-la/);
    assert.match(messageDErreur(404, null), /relance-la/);
    // un 404 qui s'explique lui-même (pièce jointe absente…) garde son message
    assert.equal(messageDErreur(404, 'pièce jointe introuvable : x.md'), 'pièce jointe introuvable : x.md');
  });
  it('sans message, renvoie au terminal', () => {
    assert.match(messageDErreur(500, null), /HTTP 500/);
  });
});
