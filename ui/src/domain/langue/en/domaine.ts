import type { FR_DOMAINE } from '../fr/domaine.ts';

type ClesDomaine = keyof typeof FR_DOMAINE;
export const EN_DOMAINE: Record<ClesDomaine, string> = {
  'domaine.titre.reponse': 'Re: {id} — ',
  'domaine.attente.minute__1': 'for {n} min',
  'domaine.attente.minute__n': 'for {n} min',
  'domaine.attente.heure__1': 'for {n} h',
  'domaine.attente.heure__n': 'for {n} h',
  'domaine.attente.jour__1': 'for {n} d',
  'domaine.attente.jour__n': 'for {n} d',
};
