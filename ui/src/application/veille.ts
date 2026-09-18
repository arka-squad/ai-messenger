/**
 * La veille : charge la boîte, la relève à intervalle, signale les nouveaux messages.
 * Sans React : l'interface s'y abonne (`useSyncExternalStore`).
 */
import type { Etat, Message, Statut } from '../domain/types.ts';
import type { PortBoite } from './ports.ts';

export interface EtatVeille {
  etat: Etat | null;
  erreur: string | null;
  active: boolean;
  derniereReleve: Date | null;
  /** Ce que la dernière relève a trouvé, en une phrase. */
  constat: string;
  /** Les messages arrivés depuis le chargement précédent. */
  arrivees: readonly Message[];
}

type Abonne = () => void;

export class Veille {
  readonly #boite: PortBoite;
  readonly #intervalle: number;
  readonly #abonnes = new Set<Abonne>();
  #minuteur: ReturnType<typeof setInterval> | null = null;
  #etat: EtatVeille = { etat: null, erreur: null, active: true, derniereReleve: null, constat: '', arrivees: [] };

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
      this.#publier({ derniereReleve: new Date(), constat: 'boîte inchangée', erreur: null });
    } catch (e) {
      this.#publier({ derniereReleve: new Date(), constat: 'boîte injoignable', erreur: message(e) });
    }
  }

  async recharger(): Promise<void> {
    try {
      const etat = await this.#boite.charger();
      const connus = new Set(this.#etat.etat?.messages.map((m) => m.id) ?? []);
      const arrivees = this.#etat.etat ? etat.messages.filter((m) => !connus.has(m.id)) : [];
      const constat = arrivees.length
        ? `${arrivees.length} nouveau${arrivees.length > 1 ? 'x' : ''} message${arrivees.length > 1 ? 's' : ''}`
        : 'boîte à jour';
      this.#publier({ etat, arrivees, constat, erreur: null, derniereReleve: new Date() });
    } catch (e) {
      this.#publier({ erreur: message(e), constat: 'boîte injoignable', derniereReleve: new Date() });
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
