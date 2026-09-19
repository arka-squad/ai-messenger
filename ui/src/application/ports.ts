/** Les ports du front : ce dont l'application a besoin, implémenté dans `adapters/`. */
import type { Activation, Creation, Etat, Message, Statut } from '../domain/types.ts';

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
  lienPieceJointe(nom: string): string;
}

/** Les préférences de ce navigateur (thème…) — jamais une donnée partagée. */
export interface PortPreferences {
  lire(cle: string): string | null;
  ecrire(cle: string, valeur: string): void;
}
