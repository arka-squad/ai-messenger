/** Le format d'échange de l'API — miroir de PROTOCOLE.md et de `adapters/driving/web.py`. */

export const STATUTS = ['nouveau', 'lu', 'traité'] as const;
export type Statut = (typeof STATUTS)[number];

export interface Transition {
  date: string;
  par: string;
  statut: Statut;
}

export interface Message {
  id: string;
  date: string;
  de: string;
  a: string[];
  objet: string;
  corps: string[];
  pj: string | null;
  re: string | null;
  statut: Statut;
  historique: Transition[];
  importe?: boolean;
  /** Le statut que le compte courant peut donner à ce message, décidé par le domaine Python. */
  suite: Statut | null;
  /** La pièce jointe existe-t-elle dans le dossier de la boîte ? */
  pj_presente: boolean;
}

export interface Compte {
  nom: string;
  actif: boolean;
  hote?: string;
  machine?: string;
  role?: string;
}

export interface Source {
  chemin: string;
  nom: string;
  format: 'json' | 'markdown';
  lecture_seule: boolean;
}

export interface Etat {
  source: Source;
  /** Le compte au nom duquel l'interface agit. */
  compte: string;
  version: string;
  messages: Message[];
  comptes: Compte[];
}
