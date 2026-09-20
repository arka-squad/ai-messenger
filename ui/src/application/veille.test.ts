import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import type { Activation, Creation, Etat, Invitation, Message, Poste, Statut } from '../domain/types.ts';
import type { PortBoite } from './ports.ts';
import { Veille } from './veille.ts';

function message(id: string): Message {
  return {
    id, date: '2026-09-18T10:00:00', de: 'windows', a: ['owner'], objet: id, corps: [], pj: null, re: null,
    statut: 'nouveau', statuts: { owner: 'nouveau' }, mien: 'nouveau', historique: [], suite: 'lu',
    pj_presente: false,
  };
}

class BoiteFactice implements PortBoite {
  etat: Etat = {
    source: { chemin: '/b.json', nom: 'b.json', format: 'json', lecture_seule: false, demonstration: false,
      activable: true },
    compte: 'owner', projets: [], invite: 'invite de test', notifications: true, version: 'v1',
    messages: [message('a')], comptes: [],
  };
  chargements = 0;
  panne = false;

  async charger(): Promise<Etat> {
    if (this.panne) throw new Error('API injoignable');
    this.chargements += 1;
    return structuredClone(this.etat);
  }
  async version(): Promise<string> {
    if (this.panne) throw new Error('API injoignable');
    return this.etat.version;
  }
  async marquer(id: string, statut: Statut): Promise<Message> {
    const m = this.etat.messages.find((x) => x.id === id)!;
    m.statut = statut;
    this.etat.version += '+';
    return m;
  }
  async notifications(actives: boolean): Promise<boolean> {
    this.etat.notifications = actives;
    return actives;
  }
  async activer(dossier: string, projet: string): Promise<Activation> {
    return { dossier, projet: projet || null, boite: this.etat.source.chemin, hotes: [] };
  }
  async creer(dossier: string): Promise<Creation> {
    return { cree: true, boite: `${dossier}/.aimessenger/mail/boite.json` };
  }
  async ouvrirBoite(dossier: string): Promise<string> {
    this.etat.source = { ...this.etat.source, chemin: `${dossier}/boite.json` };
    return this.etat.source.chemin;
  }
  async choisirDossier(): Promise<string | null> {
    return '/dossier/choisi';
  }
  invitations: Invitation[] = [];
  eteinte = false;
  async inviter(invitation: Invitation): Promise<string> {
    this.invitations.push(invitation);
    if ('projet' in invitation && invitation.projet) this.etat.projets = [...this.etat.projets, invitation.projet];
    return 'invite de test';
  }
  async fusionner(compte: string, dans: string): Promise<void> {
    this.etat.comptes = this.etat.comptes.map((c) => (c.nom === compte ? { ...c, actif: false } : c));
    void dans;
  }
  async rattacher(compte: string, projet: string | null): Promise<void> {
    this.etat.comptes = this.etat.comptes.map((c) => (c.nom === compte ? { ...c, projet } : c));
  }
  async noterContact(compte: string, alias: string, adresses: string[], note: string): Promise<void> {
    this.etat.comptes = this.etat.comptes.map((c) => (c.nom === compte
      ? { ...c, contacts: [...(c.contacts ?? []), { alias, adresses, note }] } : c));
  }
  async retirerContact(compte: string, alias: string): Promise<void> {
    this.etat.comptes = this.etat.comptes.map((c) => (c.nom === compte
      ? { ...c, contacts: (c.contacts ?? []).filter((x) => x.alias !== alias) } : c));
  }
  async poste(): Promise<Poste> {
    return { hotes: [], eteignable: true, logiciel: 'test' };
  }
  async preparer(): Promise<Poste> {
    return this.poste();
  }
  async eteindre(): Promise<void> {
    this.eteinte = true;
  }
  lienPieceJointe(nom: string): string {
    return `/pj/${nom}`;
  }
}

describe('veille', () => {
  it('ne recharge que si la boîte a changé, et signale les arrivées', async () => {
    const boite = new BoiteFactice();
    const veille = new Veille(boite);
    await veille.recharger();
    assert.equal(boite.chargements, 1);

    await veille.relever();
    assert.equal(boite.chargements, 1);
    assert.equal(veille.lire().constat, 'boîte inchangée');

    boite.etat.messages.push(message('b'));
    boite.etat.version = 'v2';
    await veille.relever();
    assert.equal(boite.chargements, 2);
    assert.deepEqual(veille.lire().arrivees.map((m) => m.id), ['b']);
    assert.equal(veille.lire().constat, '1 nouveau message');
  });

  it('dit quand la boîte est injoignable, sans perdre ce qui est affiché', async () => {
    const boite = new BoiteFactice();
    const veille = new Veille(boite);
    await veille.recharger();
    boite.panne = true;
    await veille.relever();
    assert.equal(veille.lire().constat, 'boîte injoignable');
    assert.equal(veille.lire().etat?.messages.length, 1);
  });

  it('recharge après avoir fait avancer un statut', async () => {
    const boite = new BoiteFactice();
    const veille = new Veille(boite);
    await veille.recharger();
    await veille.marquer('a', 'lu');
    assert.equal(veille.lire().etat?.messages[0]?.statut, 'lu');
  });

  it('coupe puis rétablit les notifications système', async () => {
    const veille = new Veille(new BoiteFactice());
    await veille.recharger();
    await veille.basculerNotifications();
    assert.equal(veille.lire().etat?.notifications, false);
    await veille.basculerNotifications();
    assert.equal(veille.lire().etat?.notifications, true);
  });

  it("organise la boîte puis recharge : projet d'une invite, agent rangé, carnet tenu", async () => {
    const boite = new BoiteFactice();
    boite.etat.comptes = [{ nom: 'windows', actif: true }];
    const veille = new Veille(boite);
    await veille.recharger();
    assert.equal(await veille.inviter({ projet: 'cortex' }), 'invite de test');
    assert.deepEqual(veille.lire().etat?.projets, ['cortex']);
    await veille.rattacher('windows', 'cortex');
    assert.equal(veille.lire().etat?.comptes[0]?.projet, 'cortex');
    await veille.noterContact('windows', 'chef', ['owner'], 'mon humain');
    assert.deepEqual(veille.lire().etat?.comptes[0]?.contacts?.map((c) => c.alias), ['chef']);
    await veille.retirerContact('windows', 'chef');
    assert.deepEqual(veille.lire().etat?.comptes[0]?.contacts, []);
    await veille.fusionner('windows', 'owner');
    assert.equal(veille.lire().etat?.comptes[0]?.actif, false);
    await veille.ouvrirBoite('/nas/aimessenger');
    assert.equal(veille.lire().etat?.source.chemin, '/nas/aimessenger/boite.json');
  });

  it("éteint la boîte : la veille s'arrête et le dit", async () => {
    const boite = new BoiteFactice();
    const veille = new Veille(boite);
    await veille.recharger();
    await veille.eteindre();
    assert.equal(boite.eteinte, true);
    assert.equal(veille.lire().eteinte, true);
    assert.equal(veille.lire().active, false);
  });

  it('prévient ses abonnés', async () => {
    const veille = new Veille(new BoiteFactice());
    let appels = 0;
    const desabonner = veille.abonner(() => { appels += 1; });
    await veille.recharger();
    desabonner();
    await veille.recharger();
    assert.equal(appels, 1);
  });
});
