import { Circle, CircleCheck, CircleDot, type LucideIcon } from 'lucide-react';
import type { Statut } from '../domain/types.ts';

const ICONES: Record<Statut, LucideIcon> = { nouveau: CircleDot, lu: Circle, traité: CircleCheck };

export function IconeStatut({ statut }: { statut: Statut }) {
  // Un statut inconnu (boîte plus récente que cette page) ne doit pas faire disparaître l'interface.
  const Icone = ICONES[statut] ?? ICONES.nouveau;
  return (
    <span className={`statut statut--${statut}`}>
      <Icone className="ic" size={11} />
      <span className="statut__libelle">{statut}</span>
    </span>
  );
}
