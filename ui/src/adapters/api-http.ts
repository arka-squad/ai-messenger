/** La boîte à travers l'API locale (`messenger.py ui`), relayée par Vite en développement. */
import type { PortBoite } from '../application/ports.ts';
import type { Etat, Message, Statut } from '../domain/types.ts';

export class ApiHttp implements PortBoite {
  readonly #base: string;

  constructor(base = '') {
    this.#base = base;
  }

  charger(): Promise<Etat> {
    return this.#demander<Etat>('/api/boite');
  }

  async version(): Promise<string> {
    return (await this.#demander<{ version: string }>('/api/version')).version;
  }

  async marquer(id: string, statut: Statut): Promise<Message> {
    const reponse = await this.#demander<{ message: Message }>('/api/statut', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id, statut }),
    });
    return reponse.message;
  }

  async notifications(actives: boolean): Promise<boolean> {
    const reponse = await this.#demander<{ notifications: boolean }>('/api/notifications', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ actives }),
    });
    return reponse.notifications;
  }

  lienPieceJointe(nom: string): string {
    return `${this.#base}/pj/${encodeURIComponent(nom)}`;
  }

  async #demander<T>(chemin: string, init?: RequestInit): Promise<T> {
    let reponse: Response;
    try {
      reponse = await fetch(this.#base + chemin, { cache: 'no-store', ...init });
    } catch {
      throw new Error("l'API locale ne répond pas — relance `npm run dev` ou `messenger.py ui`");
    }
    const texte = await reponse.text();
    let corps: unknown = null;
    try {
      corps = texte ? JSON.parse(texte) : null;
    } catch {
      // réponse non JSON : relais Vite sans API derrière, par exemple
    }
    if (!reponse.ok) {
      const erreur = corps && typeof corps === 'object' && 'erreur' in corps ? String(corps.erreur) : null;
      throw new Error(erreur ?? `l'API locale ne répond pas (HTTP ${reponse.status}) — voir le terminal`);
    }
    return corps as T;
  }
}
