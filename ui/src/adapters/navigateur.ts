/** Les services du navigateur : les préférences de ce poste. */
import type { PortPreferences } from '../application/ports.ts';

/** localStorage peut être indisponible (navigation privée, stockage bloqué) : on s'en passe. */
export class PreferencesLocales implements PortPreferences {
  lire(cle: string): string | null {
    try {
      return window.localStorage.getItem(`arkalabs-messenger:${cle}`);
    } catch {
      return null;
    }
  }

  ecrire(cle: string, valeur: string): void {
    try {
      window.localStorage.setItem(`arkalabs-messenger:${cle}`, valeur);
    } catch {
      // préférence non retenue : sans conséquence
    }
  }
}
