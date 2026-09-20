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

/** Une entrée du carnet d'adresses d'un compte : un alias pour une adresse, ou pour un groupe. */
export interface Contact {
  alias: string;
  adresses: string[];
  note?: string;
}

export interface Compte {
  nom: string;
  actif: boolean;
  hote?: string;
  machine?: string;
  role?: string;
  /** Nom lisible pour un humain (`CL_Agent-MessengerAI_WIN`) ; `nom` reste l'adresse. */
  affichage?: string;
  /** Son carnet d'adresses : lui seul le modifie. */
  contacts?: Contact[];
}

export interface Source {
  chemin: string;
  nom: string;
  format: 'json' | 'markdown';
  lecture_seule: boolean;
  /** Aucune boîte n'est configurée : l'interface montre la démonstration du dépôt. */
  demonstration: boolean;
  /** La boîte est réelle et inscriptible : on peut y activer un dépôt depuis l'interface. */
  activable: boolean;
}

/** Où en est un hôte IA du poste (Claude Code, Codex, Kimi Code…) après qu'on l'a équipé. */
export interface HoteEquipe {
  id: string;
  nom: string;
  present: boolean;
  /** Serveur MCP et relève posés et conformes. */
  equipe: boolean;
  note: string | null;
}

/** Le résumé rendu après la connexion d'un dépôt local : le dépôt déclaré, les hôtes du poste équipés. */
export interface Activation {
  dossier: string;
  projet: string | null;
  boite: string | null;
  hotes: HoteEquipe[];
}

/** Le résultat de la création d'une boîte depuis l'interface. */
export interface Creation {
  cree: boolean;
  boite: string;
}

export interface Etat {
  source: Source;
  /** Le compte au nom duquel l'interface agit. */
  compte: string;
  /** Les projets connus : une adresse est `nom` (commun) ou `nom@projet`. */
  projets: string[];
  /** Le texte à copier-coller à un agent pour qu'il s'enrôle ; null s'il n'y a pas de vraie boîte. */
  invite: string | null;
  /** Notifications système du poste : actives, coupées, ou null si indisponibles. */
  notifications: boolean | null;
  version: string;
  messages: Message[];
  comptes: Compte[];
}
