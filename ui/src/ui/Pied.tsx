import { utiliseLangue } from '../application/langue.tsx';
import type { Compteurs } from '../domain/boite.ts';
import { t, tp } from '../domain/langue/index.ts';
import type { Source } from '../domain/types.ts';

export function Pied({ compteurs, source }: { compteurs: Compteurs; source: Source | null }) {
  const l = utiliseLangue();
  return (
    <footer className="pied">
      <span>
        {tp(l, compteurs.total, 'message.pied.total')} · {tp(l, compteurs.nouveau, 'message.pied.nouveau')} · {tp(l, compteurs.pj, 'message.pied.pj')}
      </span>
      <span className="vide" />
      {source?.demonstration && (
        <span>{t(l, 'message.pied.demonstration')}</span>
      )}
      {source && !source.demonstration && (
        <span title={source.chemin}>
          {t(l, 'message.pied.source', { nom: source.nom })}{source.format === 'markdown' ? t(l, 'message.pied.markdown') : ''}
        </span>
      )}
    </footer>
  );
}
