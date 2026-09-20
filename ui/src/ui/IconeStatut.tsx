import { Circle, CircleCheck, CircleDot, type LucideIcon } from 'lucide-react';
import { utiliseLangue } from '../application/langue.tsx';
import { t } from '../domain/langue/index.ts';
import type { Statut } from '../domain/types.ts';

const ICONES: Record<Statut, LucideIcon> = { nouveau: CircleDot, lu: Circle, traité: CircleCheck };

/** Le libellé traduit de chaque statut : une clé par valeur protocole, jamais dérivée d'elle. */
const LIBELLES: Record<Statut, 'message.statut.nouveau' | 'message.statut.lu' | 'message.statut.traite'> = {
  nouveau: 'message.statut.nouveau',
  lu: 'message.statut.lu',
  traité: 'message.statut.traite',
};

export function IconeStatut({ statut }: { statut: Statut }) {
  const l = utiliseLangue();
  // Un statut inconnu (boîte plus récente que cette page) ne doit pas faire disparaître l'interface.
  const Icone = ICONES[statut] ?? ICONES.nouveau;
  const libelle = LIBELLES[statut] ?? LIBELLES.nouveau;
  return (
    <span className={`statut statut--${statut}`}>
      <Icone className="ic" size={11} />
      <span className="statut__libelle">{t(l, libelle)}</span>
    </span>
  );
}
