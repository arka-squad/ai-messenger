/** La langue de l'interface : un réglage de ce poste, jamais de la boîte (qui est partagée). */
export type Langue = 'fr' | 'en';

export const LANGUE_DEFAUT: Langue = 'fr';

export function normaliseLangue(valeur: string | null): Langue | null {
  return valeur === 'fr' || valeur === 'en' ? valeur : null;
}

/** La langue du navigateur, ramenée à fr ou en : tout ce qui n'est pas francophone donne en. */
export function langueDuNavigateur(): Langue {
  return typeof navigator !== 'undefined' && navigator.language.toLowerCase().startsWith('fr') ? 'fr' : 'en';
}
