import type { Compteurs } from '../domain/boite.ts';
import type { Source } from '../domain/types.ts';

export function Pied({ compteurs, source }: { compteurs: Compteurs; source: Source | null }) {
  return (
    <footer className="pied">
      <span>
        {compteurs.total} messages · {compteurs.nouveau} nouveau{compteurs.nouveau > 1 ? 'x' : ''} · {compteurs.pj} pièce{compteurs.pj > 1 ? 's' : ''} jointe{compteurs.pj > 1 ? 's' : ''}
      </span>
      <span className="vide" />
      {source?.demonstration && (
        <span>Démonstration — ta boîte : MESSENGER_BOX dans ui/.env.local</span>
      )}
      {source && !source.demonstration && (
        <span title={source.chemin}>
          Source : {source.nom}{source.format === 'markdown' ? ' · converti en JSON · lecture seule' : ''}
        </span>
      )}
    </footer>
  );
}
