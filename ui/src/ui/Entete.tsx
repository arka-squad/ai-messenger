import { Bell, BellOff, BellRing, Inbox, Moon, Sun } from 'lucide-react';
import { CommutateurLangue, utiliseLangue } from '../application/langue.tsx';
import { initiales } from '../domain/boite.ts';
import { t, tp } from '../domain/langue/index.ts';
import type { Source } from '../domain/types.ts';
import type { Theme } from './App.tsx';

interface Props {
  nouveaux: number;
  veilleActive: boolean;
  onVeille: () => void;
  /** Notifications système : actives, coupées, ou null si indisponibles. */
  notifications: boolean | null;
  onNotifications: () => void;
  theme: Theme;
  onTheme: () => void;
  compte: string;
  source: Source | null;
}

export function Entete(p: Props) {
  const l = utiliseLangue();
  const clair = p.theme === 'light';
  return (
    <header className="entete">
      <img className="entete__logo" src="https://arkalabs.app/assets/arka-icon.svg" alt="arkalabs" />
      <span className="entete__marque">
        <span className="t-wordmark entete__wordmark"><b>arka</b><i>labs</i></span>
        <span className="entete__produit">Messenger<em>.</em></span>
      </span>

      <span className="entete__sep">/</span>
      <div className="entete__boite" title={p.source?.chemin}>
        <Inbox className="ic" size={14} />
        <span className="entete__boite-nom">
          {p.source?.demonstration ? t(l, 'coquille.boiteDemonstration') : t(l, 'coquille.boitePartagee')}
        </span>
        <span className="badge-nouveau">{tp(l, p.nouveaux, 'coquille.nouveaux')}</span>
      </div>

      <span className="vide" />

      <button
        type="button"
        className={`veille${p.veilleActive ? ' veille--active' : ''}`}
        onClick={p.onVeille}
        title={p.veilleActive ? t(l, 'coquille.veilleSuspendre') : t(l, 'coquille.veilleReprendre')}
      >
        <span className={`point-rond ${p.veilleActive ? 'ok pulse' : 'eteint'}`} />
        <span className="veille__libelle">{p.veilleActive ? t(l, 'coquille.veilleActive') : t(l, 'coquille.veilleSuspendue')}</span>
      </button>
      <button
        type="button"
        className={`entete__outil${p.notifications ? ' entete__outil--actif' : ''}`}
        onClick={p.onNotifications}
        disabled={p.notifications === null}
        title={p.notifications === null
          ? t(l, 'coquille.notificationsIndisponibles')
          : p.notifications
            ? t(l, 'coquille.notificationsActives')
            : t(l, 'coquille.notificationsCoupees')}
      >
        {p.notifications === null ? <Bell size={16} /> : p.notifications ? <BellRing size={16} /> : <BellOff size={16} />}
      </button>
      <CommutateurLangue />
      <button type="button" className="entete__outil" onClick={p.onTheme}
        title={clair ? t(l, 'coquille.themeSombre') : t(l, 'coquille.themeClair')}>
        {clair ? <Moon size={16} /> : <Sun size={16} />}
      </button>
      <span className="avatar" title={t(l, 'coquille.agirEnTant', { compte: p.compte })}>{initiales(p.compte)}</span>
    </header>
  );
}
