/** Interface language: a machine-local preference, never shared mailbox data. */
export type Langue = 'fr' | 'en';

export const LANGUE_DEFAUT: Langue = 'en';

export function normaliseLangue(valeur: string | null): Langue | null {
  return valeur === 'fr' || valeur === 'en' ? valeur : null;
}

/** Browser language reduced to fr or en. Kept for explicit opt-in or migrations. */
export function langueDuNavigateur(): Langue {
  return typeof navigator !== 'undefined' && navigator.language.toLowerCase().startsWith('fr') ? 'fr' : 'en';
}
