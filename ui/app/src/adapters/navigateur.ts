/** Les services du navigateur : notifications système et préférences locales. */
import type { PortNotifications, PortPreferences } from '../application/ports.ts';

export class NotificationsNavigateur implements PortNotifications {
  autorisees(): boolean {
    return typeof Notification !== 'undefined' && Notification.permission === 'granted';
  }

  async demander(): Promise<boolean> {
    if (typeof Notification === 'undefined') return false;
    if (Notification.permission === 'granted') return true;
    return (await Notification.requestPermission()) === 'granted';
  }

  notifier(titre: string, corps: string): void {
    if (this.autorisees()) new Notification(titre, { body: corps, tag: titre });
  }
}

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
