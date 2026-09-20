/**
 * La veille : charge la boîte, la relève à intervalle, signale les nouveaux messages.
 * Sans React : l'interface s'y abonne (`useSyncExternalStore`).
 */
import { t, tp, type Langue } from '../domain/langue/index.ts';
import type { Activation, Creation, Etat, Invitation, Message, Poste, Statut } from '../domain/types.ts';
import type { PortBoite } from './ports.ts';

/** Ce que la dernière relève a trouvé : une donnée, pas un texte affichable — le libellé se fabrique dans
 *  la langue voulue avec `libelleConstat`. */
export type Constat =
  | { type: 'inchangee' }
  | { type: 'injoignable' }
  | { type: 'ajour' }
  | { type: 'eteinte' }
  | { type: 'nouveaux'; n: number };

/** Le texte d'un constat de relève, dans la langue de l'interface. */
export function libelleConstat(langue: Langue, c: Constat): string {
  switch (c.type) {
    case 'inchangee':
      return t(langue, 'technique.inchangee');
    case 'injoignable':
      return t(langue, 'technique.injoignable');
    case 'ajour':
      return t(langue, 'technique.ajour');
    case 'eteinte':
      return t(langue, 'technique.eteinte');
    case 'nouveaux':
      return tp(langue, c.n, 'technique.nouveaux');
  }
}

export interface EtatVeille {
  etat: Etat | null;
  erreur: string | null;
  active: boolean;
  derniereReleve: Date | null;
  /** Ce que la dernière relève a trouvé ; à libeller avec `libelleConstat`. */
  constat: Constat;
  /** Les messages arrivés depuis le chargement précédent. */
  arrivees: readonly Message[];
  /** L'humain vient d'éteindre la boîte depuis cette page. */
  eteinte: boolean;
}

type Abonne = () => void;

export class Veille {
  readonly #boite: PortBoite;
  readonly #intervalle: number;
  readonly #abonnes = new Set<Abonne>();
  #minuteur: ReturnType<typeof setInterval> | null = null;
  // Placeholder jamais affiché : le rail ne libelle le constat qu'après une première relève.
  #etat: EtatVeille = { etat: null, erreur: null, active: true, derniereReleve: null, constat: { type: 'inchangee' },
    arrivees: [], eteinte: false };

  constructor(boite: PortBoite, intervalleMs = 3000) {
    this.#boite = boite;
    this.#intervalle = intervalleMs;
  }

  lire = (): EtatVeille => this.#etat;

  abonner = (abonne: Abonne): (() => void) => {
    this.#abonnes.add(abonne);
    return () => this.#abonnes.delete(abonne);
  };

  demarrer(): void {
    void this.recharger();
    this.#armer();
  }

  arreter(): void {
    if (this.#minuteur) clearInterval(this.#minuteur);
    this.#minuteur = null;
  }

  basculer(): void {
    const active = !this.#etat.active;
    this.#publier({ active });
    if (active) {
      void this.relever();
      this.#armer();
    } else {
      this.arreter();
    }
  }

  /** Relit l'empreinte ; recharge seulement si la boîte a changé. */
  async relever(): Promise<void> {
    try {
      const version = await this.#boite.version();
      if (version !== this.#etat.etat?.version) {
        await this.recharger();
        return;
      }
      this.#publier({ derniereReleve: new Date(), constat: { type: 'inchangee' }, erreur: null });
    } catch (e) {
      this.#publier({ derniereReleve: new Date(), constat: { type: 'injoignable' }, erreur: message(e) });
    }
  }

  async recharger(): Promise<void> {
    try {
      const etat = await this.#boite.charger();
      const connus = new Set(this.#etat.etat?.messages.map((m) => m.id) ?? []);
      const arrivees = this.#etat.etat ? etat.messages.filter((m) => !connus.has(m.id)) : [];
      const constat: Constat = arrivees.length
        ? { type: 'nouveaux', n: arrivees.length }
        : { type: 'ajour' };
      this.#publier({ etat, arrivees, constat, erreur: null, derniereReleve: new Date() });
    } catch (e) {
      this.#publier({ erreur: message(e), constat: { type: 'injoignable' }, derniereReleve: new Date() });
    }
  }

  async marquer(id: string, statut: Statut): Promise<void> {
    await this.#boite.marquer(id, statut);
    await this.recharger();
  }

  /** Coupe ou rétablit les notifications système du poste. */
  async basculerNotifications(): Promise<void> {
    const etat = this.#etat.etat;
    if (!etat || etat.notifications === null) return;
    const notifications = await this.#boite.notifications(!etat.notifications);
    this.#publier({ etat: { ...etat, notifications } });
  }

  /** Connecte un projet, puis recharge (le projet apparaîtra dès qu'un agent s'y enrôle). */
  async activer(dossier: string, projet: string): Promise<Activation> {
    const resume = await this.#boite.activer(dossier, projet);
    await this.recharger();
    return resume;
  }

  /** Crée une boîte dans un dossier et bascule dessus, puis recharge. */
  async creer(dossier: string): Promise<Creation> {
    const resume = await this.#boite.creer(dossier);
    await this.recharger();
    return resume;
  }

  /** Dit à ce poste où est la boîte, puis recharge : l'interface bascule dessus. */
  async ouvrirBoite(dossier: string): Promise<string> {
    const boite = await this.#boite.ouvrirBoite(dossier);
    await this.recharger();
    return boite;
  }

  /** Ouvre le sélecteur de dossier natif du poste. */
  choisirDossier(): Promise<string | null> {
    return this.#boite.choisirDossier();
  }

  /** L'invite à coller à un agent ; un projet nouveau apparaît aussitôt. */
  async inviter(invitation: Invitation): Promise<string> {
    const invite = await this.#boite.inviter(invitation);
    await this.recharger();
    return invite;
  }

  async rattacher(compte: string, projet: string | null): Promise<void> {
    await this.#boite.rattacher(compte, projet);
    await this.recharger();
  }

  /** Fusionne deux comptes d'un même agent, puis recharge : l'ancien disparaît de la liste. */
  async fusionner(compte: string, dans: string): Promise<void> {
    await this.#boite.fusionner(compte, dans);
    await this.recharger();
  }

  async noterContact(compte: string, alias: string, adresses: string[], note: string, remplacer = false): Promise<void> {
    await this.#boite.noterContact(compte, alias, adresses, note, remplacer);
    await this.recharger();
  }

  async retirerContact(compte: string, alias: string): Promise<void> {
    await this.#boite.retirerContact(compte, alias);
    await this.recharger();
  }

  poste(): Promise<Poste> {
    return this.#boite.poste();
  }

  preparer(): Promise<Poste> {
    return this.#boite.preparer();
  }

  /** Éteint la boîte allumée d'ici : la veille s'arrête, il n'y a plus personne à relever. */
  async eteindre(): Promise<void> {
    await this.#boite.eteindre();
    this.arreter();
    this.#publier({ active: false, constat: { type: 'eteinte' }, eteinte: true });
  }

  lienPieceJointe(nom: string): string {
    return this.#boite.lienPieceJointe(nom);
  }

  #armer(): void {
    this.arreter();
    this.#minuteur = setInterval(() => void this.relever(), this.#intervalle);
  }

  #publier(partiel: Partial<EtatVeille>): void {
    this.#etat = { ...this.#etat, ...partiel };
    for (const abonne of this.#abonnes) abonne();
  }
}

function message(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}
