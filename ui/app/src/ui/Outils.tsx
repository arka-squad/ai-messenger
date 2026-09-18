import { Search } from 'lucide-react';
import type { Compteurs, Filtre } from '../domain/boite.ts';
import type { Statut } from '../domain/types.ts';

interface Props {
  compteurs: Compteurs;
  filtre: Filtre;
  onFiltre: (f: Filtre) => void;
}

export function Outils({ compteurs, filtre, onFiltre }: Props) {
  const puces: [Statut | null, string, number][] = [
    [null, 'Tous', compteurs.total],
    ['nouveau', 'Nouveau', compteurs.nouveau],
    ['lu', 'Lu', compteurs.lu],
    ['traité', 'Traité', compteurs.traité],
  ];
  return (
    <div className="outils">
      {puces.map(([statut, libelle, n]) => (
        <button
          key={libelle}
          type="button"
          className={`puce${filtre.statut === statut ? ' puce--actif' : ''}`}
          onClick={() => onFiltre({ ...filtre, statut })}
        >
          <span className="puce__libelle">{libelle}</span>
          <span className="compteur">{n}</span>
        </button>
      ))}
      <span className="vide" />
      <label className="recherche">
        <Search className="ic" size={13} />
        <input
          type="search"
          value={filtre.recherche}
          placeholder="Objet, id, pièce jointe"
          aria-label="Rechercher dans la boîte"
          onChange={(e) => onFiltre({ ...filtre, recherche: e.target.value })}
          onKeyDown={(e) => {
            if (e.key === 'Escape') onFiltre({ ...filtre, recherche: '' });
          }}
        />
      </label>
    </div>
  );
}
