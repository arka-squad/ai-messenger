import type { FR_TECHNIQUE } from '../fr/technique.ts';

type ClesTechnique = keyof typeof FR_TECHNIQUE;
export const EN_TECHNIQUE: Record<ClesTechnique, string> = {
  'technique.inchangee': 'mailbox unchanged',
  'technique.injoignable': 'mailbox unreachable',
  'technique.ajour': 'mailbox up to date',
  'technique.eteinte': 'mailbox off',
  'technique.nouveaux__1': '{n} new message',
  'technique.nouveaux__n': '{n} new messages',
  'technique.api_obsolete': "this feature doesn't exist in the running app: it predates an update — close it and start it again",
  'technique.api_silencieuse': 'the local API is not responding (HTTP {statut}) — see the terminal',
  'technique.api_hors_ligne': 'the local API is not responding — restart `npm run dev` or `messenger.py ui`',
};
