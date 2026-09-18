import { Bell, BellRing, Inbox, Moon, Sun } from 'lucide-react';
import { initiales } from '../domain/boite.ts';
import type { Source } from '../domain/types.ts';
import type { Theme } from './App.tsx';

interface Props {
  nouveaux: number;
  veilleActive: boolean;
  onVeille: () => void;
  alertes: boolean;
  onAlertes: () => void;
  theme: Theme;
  onTheme: () => void;
  compte: string;
  source: Source | null;
}

export function Entete(p: Props) {
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
        <span className="entete__boite-nom">Boîte partagée</span>
        <span className="badge-nouveau">{p.nouveaux} NOUVEAU{p.nouveaux > 1 ? 'X' : ''}</span>
      </div>

      <span className="vide" />

      <button
        type="button"
        className={`veille${p.veilleActive ? ' veille--active' : ''}`}
        onClick={p.onVeille}
        title={p.veilleActive ? 'Suspendre la relève automatique' : 'Reprendre la relève automatique'}
      >
        <span className={`point-rond ${p.veilleActive ? 'ok pulse' : 'eteint'}`} />
        <span className="veille__libelle">{p.veilleActive ? 'Veille active' : 'Veille suspendue'}</span>
      </button>
      <button
        type="button"
        className={`entete__outil${p.alertes ? ' entete__outil--actif' : ''}`}
        onClick={p.onAlertes}
        title={p.alertes
          ? `Notifications actives : un message pour ${p.compte} vous est signalé quand l'onglet est en arrière-plan`
          : `Être notifié des messages pour ${p.compte}`}
      >
        {p.alertes ? <BellRing size={16} /> : <Bell size={16} />}
      </button>
      <button type="button" className="entete__outil" onClick={p.onTheme} title={clair ? 'Passer en sombre' : 'Passer en clair'}>
        {clair ? <Moon size={16} /> : <Sun size={16} />}
      </button>
      <span className="avatar" title={`Vous agissez en tant que ${p.compte}`}>{initiales(p.compte)}</span>
    </header>
  );
}
