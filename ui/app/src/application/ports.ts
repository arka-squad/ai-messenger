/** Les ports du front : ce dont l'application a besoin, implémenté dans `adapters/`. */
import type { Etat, Message, Statut } from '../domain/types.ts';

/** La boîte, vue à travers l'API locale. */
export interface PortBoite {
  charger(): Promise<Etat>;
  /** Une empreinte qui change à chaque écriture : la veille ne recharge que si elle change. */
  version(): Promise<string>;
  /** Fait avancer un statut au nom du compte courant ; le refus arrive en erreur lisible. */
  marquer(id: string, statut: Statut): Promise<Message>;
  lienPieceJointe(nom: string): string;
}

/** Les notifications du système. */
export interface PortNotifications {
  autorisees(): boolean;
  demander(): Promise<boolean>;
  notifier(titre: string, corps: string): void;
}

/** Les préférences de ce navigateur (thème…) — jamais une donnée partagée. */
export interface PortPreferences {
  lire(cle: string): string | null;
  ecrire(cle: string, valeur: string): void;
}
