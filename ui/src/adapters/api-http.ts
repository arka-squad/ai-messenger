/** La boîte à travers l'API locale (`messenger.py ui`), relayée par Vite en développement. */
import { LANGUE_DEFAUT, langueDuNavigateur, normaliseLangue, t, type Langue } from '../domain/langue/index.ts';
import type { PortBoite } from '../application/ports.ts';
import type { Activation, Creation, Etat, Invitation, Message, Poste, Statut } from '../domain/types.ts';

/** Ce qu'on dit à l'humain quand l'API refuse. Une route que l'API ne connaît pas (`404 introuvable`) veut
 *  dire qu'elle est plus ancienne que cette page : un serveur resté ouvert pendant une mise à jour.
 *  `erreur` est un texte du backend Python : un contrat lu par des agents, jamais traduit ici. */
export function messageDErreur(langue: Langue, statut: number, erreur: string | null): string {
  if (statut === 404 && (erreur === null || erreur === 'introuvable')) {
    return t(langue, 'technique.api_obsolete');
  }
  return erreur ?? t(langue, 'technique.api_silencieuse', { statut });
}

/** La langue de l'interface, relue à chaque appel : cet adaptateur vit hors de React, où la langue est un
 *  contexte. La clé est celle de `PreferencesLocales` ; à défaut de préférence, la langue du navigateur,
 *  comme au premier montage du fournisseur. */
function langueCourante(): Langue {
  try {
    return normaliseLangue(window.localStorage.getItem('arkalabs-messenger:langue')) ?? langueDuNavigateur();
  } catch {
    return LANGUE_DEFAUT;
  }
}

/** Ce que l'API envoie vraiment. Une version plus ancienne, restée allumée pendant une mise à jour,
 *  ignore les champs récents : on les reconstruit au lieu de casser l'affichage. */
type MessageBrut = Omit<Message, 'mien' | 'statuts'> & Partial<Pick<Message, 'mien' | 'statuts'>>;
type EtatBrut = Omit<Etat, 'messages' | 'obsolete'> & { messages: MessageBrut[] };

/** Complète ce qu'une API plus ancienne n'envoie pas, et dit qu'elle est plus ancienne.
 *
 *  `mien` (le statut du compte courant) est arrivé avec le statut par destinataire : sans lui,
 *  l'interface n'affichait plus rien du tout. On le recalcule comme le ferait le serveur — le
 *  résultat est juste — mais on le signale, parce que d'autres fonctions, elles, manqueront.
 */
export function normaliser(brut: EtatBrut): Etat {
  return {
    ...brut,
    obsolete: brut.messages.some((m) => m.mien === undefined),
    messages: brut.messages.map((m) => ({
      ...m,
      statuts: m.statuts ?? {},
      mien: m.mien ?? m.statuts?.[brut.compte] ?? m.statut,
    })),
  };
}

export class ApiHttp implements PortBoite {
  readonly #base: string;
  readonly #langue: () => Langue;

  /** `langue` rend la langue de l'interface au moment de l'appel ; par défaut, relue des préférences du poste. */
  constructor(base = '', langue: () => Langue = langueCourante) {
    this.#base = base;
    this.#langue = langue;
  }

  async charger(): Promise<Etat> {
    return normaliser(await this.#demander<EtatBrut>('/api/boite'));
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

  async activer(dossier: string, projet: string): Promise<Activation> {
    return this.#demander<Activation>('/api/activer', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ dossier, projet }),
    });
  }

  async creer(dossier: string): Promise<Creation> {
    return this.#demander<Creation>('/api/creer', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ dossier }),
    });
  }

  async choisirDossier(): Promise<string | null> {
    const reponse = await this.#demander<{ dossier: string | null }>('/api/choisir-dossier', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: '{}',
    });
    return reponse.dossier;
  }

  async ouvrirBoite(dossier: string): Promise<string> {
    return (await this.#poster<{ boite: string }>('/api/boite-du-poste', { dossier })).boite;
  }

  async inviter(invitation: Invitation): Promise<string> {
    return (await this.#poster<{ invite: string }>('/api/invite', invitation)).invite;
  }

  async rattacher(compte: string, projet: string | null): Promise<void> {
    await this.#poster('/api/rattacher', { compte, projet });
  }

  async fusionner(compte: string, dans: string): Promise<void> {
    await this.#poster('/api/fusionner', { compte, dans });
  }

  async noterContact(compte: string, alias: string, adresses: string[], note: string, remplacer: boolean): Promise<void> {
    await this.#poster('/api/contact', { compte, alias, adresses, note, remplacer });
  }

  async retirerContact(compte: string, alias: string): Promise<void> {
    await this.#poster('/api/contact-retirer', { compte, alias });
  }

  poste(): Promise<Poste> {
    return this.#demander<Poste>('/api/poste');
  }

  preparer(): Promise<Poste> {
    return this.#poster<Poste>('/api/preparer', {});
  }

  async eteindre(): Promise<void> {
    await this.#poster('/api/eteindre', {});
  }

  #poster<T>(chemin: string, corps: unknown): Promise<T> {
    return this.#demander<T>(chemin, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(corps),
    });
  }

  lienPieceJointe(nom: string): string {
    return `${this.#base}/pj/${encodeURIComponent(nom)}`;
  }

  async #demander<T>(chemin: string, init?: RequestInit): Promise<T> {
    let reponse: Response;
    try {
      reponse = await fetch(this.#base + chemin, { cache: 'no-store', ...init });
    } catch {
      throw new Error(t(this.#langue(), 'technique.api_hors_ligne'));
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
      throw new Error(messageDErreur(this.#langue(), reponse.status, erreur));
    }
    return corps as T;
  }
}
