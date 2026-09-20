/** Les ports du front : ce dont l'application a besoin, implémenté dans `adapters/`. */
import type { Activation, Creation, Etat, Invitation, Message, Poste, Statut } from '../domain/types.ts';

/** La boîte, vue à travers l'API locale. */
export interface PortBoite {
  charger(): Promise<Etat>;
  /** Une empreinte qui change à chaque écriture : la veille ne recharge que si elle change. */
  version(): Promise<string>;
  /** Fait avancer un statut au nom du compte courant ; le refus arrive en erreur lisible. */
  marquer(id: string, statut: Statut): Promise<Message>;
  /** Active ou coupe les notifications système du poste ; rend l'état obtenu. */
  notifications(actives: boolean): Promise<boolean>;
  /** Connecte un projet (dépôt local) à la boîte : hooks + skill posés ; rend le résumé. */
  activer(dossier: string, projet: string): Promise<Activation>;
  /** Crée une boîte (arbo `.aimessenger/`) dans un dossier et s'y branche ; rend le résumé. */
  creer(dossier: string): Promise<Creation>;
  /** Dit à ce poste où est la boîte (un dossier partagé qui en contient une) ; rend son chemin. */
  ouvrirBoite(dossier: string): Promise<string>;
  /** Ouvre le sélecteur de dossier natif du poste ; rend le chemin choisi, ou null si annulé. */
  choisirDossier(): Promise<string | null>;
  /** Le texte à coller à un agent ; un projet nouveau est créé au passage. */
  inviter(invitation: Invitation): Promise<string>;
  /** Range un compte commun dans un projet, ou l'en sort (`null`). */
  rattacher(compte: string, projet: string | null): Promise<void>;
  /** Fusionne deux comptes d'un même agent : `compte` est fermé, son courrier et son adresse mènent à `dans`. */
  fusionner(compte: string, dans: string): Promise<void>;
  /** Note un contact dans le carnet d'un agent, ou le remplace. */
  noterContact(compte: string, alias: string, adresses: string[], note: string, remplacer: boolean): Promise<void>;
  retirerContact(compte: string, alias: string): Promise<void>;
  poste(): Promise<Poste>;
  /** Prépare les outils d'IA du poste (serveur MCP, relève) ; rend l'état obtenu. */
  preparer(): Promise<Poste>;
  eteindre(): Promise<void>;
  lienPieceJointe(nom: string): string;
}

/** Les préférences de ce navigateur (thème…) — jamais une donnée partagée. */
export interface PortPreferences {
  lire(cle: string): string | null;
  ecrire(cle: string, valeur: string): void;
}
