/** La veille (constats de relève) et les erreurs réseau de l'adaptateur HTTP. */
export const FR_TECHNIQUE = {
  'technique.inchangee': 'boîte inchangée',
  'technique.injoignable': 'boîte injoignable',
  'technique.ajour': 'boîte à jour',
  'technique.eteinte': 'boîte éteinte',
  'technique.nouveaux__1': '{n} nouveau message',
  'technique.nouveaux__n': '{n} nouveaux messages',
  'technique.api_obsolete': 'cette fonction n’existe pas dans l’application en cours : elle date d’avant une mise à jour — ferme-la et relance-la',
  'technique.api_silencieuse': 'l’API locale ne répond pas (HTTP {statut}) — voir le terminal',
  'technique.api_hors_ligne': 'l’API locale ne répond pas — relance `npm run dev` ou `messenger.py ui`',
} as const;
