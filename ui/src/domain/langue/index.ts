/**
 * Le dictionnaire bilingue de l'interface.
 *
 * Le français est la source (en cas de doute sur une formulation, c'est lui qui fait foi).
 * TypeScript garantit la complétude : `EN` est un `Record<Cle, string>`, donc `npm run typecheck`
 * échoue tant qu'une clé française n'a pas son anglais. Le test `parite.test.ts` redit la même
 * chose pour l'exécution, et documente l'intention.
 *
 * Conventions :
 * - les clés sont préfixées par leur module : `domaine.*`, `technique.*`, `coquille.*`,
 *   `message.*`, `accueil.*` ;
 * - l'interpolation est minimale : `{nom}` dans le texte est remplacé par `vars` ;
 * - le pluriel tient en deux clés : `ma.cle__1` (singulier) et `ma.cle__n` (pluriel), choisies
 *   par `tp(langue, n, 'ma.cle')` ; le français comme l'anglais passent au pluriel dès n > 1 ;
 * - typographie : le français garde l'espace fine insécable avant `; : ! ?` et les guillemets
 *   « … », et l'apostrophe typographique ’ ; l'anglais n'hérite d'aucune de ces habitudes.
 *
 * Vocabulaire arrêté une fois pour toutes (le commentaire dit pourquoi quand le choix tranche) :
 * - boîte → mailbox        (la donnée partagée ; « box » est pris par la boîte de réception)
 * - relève → mail check    (le geste de checker ; « pickup » sonne logistique)
 * - veille → watch         (le processus qui surveille)
 * - poste → machine        (cet ordinateur)
 * - fil → thread           (le fil d'un message)
 * - pièce jointe → attachment
 * - compte → account
 * - carnet → address book
 */
import { FR_ACCUEIL } from './fr/accueil.ts';
import { FR_COQUILLE } from './fr/coquille.ts';
import { FR_DOMAINE } from './fr/domaine.ts';
import { FR_MESSAGE } from './fr/message.ts';
import { FR_TECHNIQUE } from './fr/technique.ts';
import { EN_ACCUEIL } from './en/accueil.ts';
import { EN_COQUILLE } from './en/coquille.ts';
import { EN_DOMAINE } from './en/domaine.ts';
import { EN_MESSAGE } from './en/message.ts';
import { EN_TECHNIQUE } from './en/technique.ts';
import type { Langue } from './types.ts';

export const FR = {
  ...FR_DOMAINE,
  ...FR_TECHNIQUE,
  ...FR_COQUILLE,
  ...FR_MESSAGE,
  ...FR_ACCUEIL,
} as const;

export type Cle = keyof typeof FR;

export const EN: Record<Cle, string> = {
  ...EN_DOMAINE,
  ...EN_TECHNIQUE,
  ...EN_COQUILLE,
  ...EN_MESSAGE,
  ...EN_ACCUEIL,
};

export type { Langue } from './types.ts';
export { LANGUE_DEFAUT, langueDuNavigateur, normaliseLangue } from './types.ts';

/** Le texte d'une clé dans la langue voulue ; une clé absente d'EN retombe sur le français. */
export function t(langue: Langue, cle: Cle, vars?: Record<string, string | number>): string {
  const brut = (langue === 'en' ? EN[cle] : undefined) ?? FR[cle];
  if (!vars) return brut;
  return brut.replace(/\{(\w+)\}/g, (mot, nom: string) => (nom in vars ? String(vars[nom]) : mot));
}

/** Pluriel à deux formes : `base__1` puis `base__n` dès que n dépasse 1 ; `{n}` est toujours fourni. */
export function tp(langue: Langue, n: number, base: string, vars: Record<string, string | number> = {}): string {
  const cle = `${base}__${n > 1 ? 'n' : '1'}` as Cle;
  return t(langue, cle, { n, ...vars });
}
