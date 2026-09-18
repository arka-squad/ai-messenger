import { Circle, CircleCheck, CircleDot, type LucideIcon } from 'lucide-react';
import type { Statut } from '../domain/types.ts';

const ICONES: Record<Statut, LucideIcon> = { nouveau: CircleDot, lu: Circle, traité: CircleCheck };

export function IconeStatut({ statut }: { statut: Statut }) {
  const Icone = ICONES[statut];
  return (
    <span className={`statut statut--${statut}`}>
      <Icone className="ic" size={11} />
      <span className="statut__libelle">{statut}</span>
    </span>
  );
}
