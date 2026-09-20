import { Search } from 'lucide-react';
import { utiliseLangue } from '../application/langue.tsx';
import type { Compteurs, Filtre } from '../domain/boite.ts';
import { t } from '../domain/langue/index.ts';
import type { Statut } from '../domain/types.ts';

interface Props {
  compteurs: Compteurs;
  filtre: Filtre;
  onFiltre: (f: Filtre) => void;
}

/** Le libellé traduit de chaque statut : une clé par valeur protocole, jamais dérivée d'elle. */
const LIBELLES: Record<Statut, 'message.statut.nouveau' | 'message.statut.lu' | 'message.statut.traite'> = {
  nouveau: 'message.statut.nouveau',
  lu: 'message.statut.lu',
  traité: 'message.statut.traite',
};

export function Outils({ compteurs, filtre, onFiltre }: Props) {
  const l = utiliseLangue();
  const puces: [Statut | null, number][] = [
    [null, compteurs.total],
    ['nouveau', compteurs.nouveau],
    ['lu', compteurs.lu],
    ['traité', compteurs.traité],
  ];
  return (
    <div className="outils">
      {puces.map(([statut, n]) => (
        <button
          key={statut ?? 'tous'}
          type="button"
          className={`puce${filtre.statut === statut ? ' puce--actif' : ''}`}
          onClick={() => onFiltre({ ...filtre, statut })}
        >
          <span className="puce__libelle">{statut === null ? t(l, 'message.filtre.toutes') : t(l, LIBELLES[statut])}</span>
          <span className="compteur">{n}</span>
        </button>
      ))}
      <span className="vide" />
      <label className="recherche">
        <Search className="ic" size={13} />
        <input
          type="search"
          value={filtre.recherche}
          placeholder={t(l, 'message.filtre.recherche')}
          aria-label={t(l, 'message.filtre.recherche-aria')}
          onChange={(e) => onFiltre({ ...filtre, recherche: e.target.value })}
          onKeyDown={(e) => {
            if (e.key === 'Escape') onFiltre({ ...filtre, recherche: '' });
          }}
        />
      </label>
    </div>
  );
}
