/** Dates, heures et âges — tout le formatage temporel de `domain/boite.ts`. */

/**
 * Vocabulaire qui tranche :
 * - la réponse se préfixe « Re : » — l'habitude du courrier, reprise par les messageries ; l'anglais
 *   écrit « Re: », sans espace avant le deux-points ;
 * - l'ancienneté d'une attente se lit « depuis … » ; l'anglais dit « for … » ;
 * - les unités restent compactes : min, h, j — l'anglais emprunte h et d (« 4h », « 3d », comme chez
 *   GitHub), et n'abrévie pas « 1 min ».
 */
export const FR_DOMAINE = {
  'domaine.titre.reponse': 'Re\u202f: {id} — ',
  'domaine.attente.minute__1': 'depuis {n} min',
  'domaine.attente.minute__n': 'depuis {n} min',
  'domaine.attente.heure__1': 'depuis {n} h',
  'domaine.attente.heure__n': 'depuis {n} h',
  'domaine.attente.jour__1': 'depuis {n} j',
  'domaine.attente.jour__n': 'depuis {n} j',
} as const;
