/**
 * Ce que l'interface calcule à partir de l'état : filtres, compteurs, agents,
 * couloirs du trafic, fil de discussion. Fonctions pures, sans DOM ni React.
 *
 * Les règles (qui peut faire avancer quoi) ne sont PAS ici : l'API les rend
 * dans `Message.suite`, décidées par le domaine Python.
 */
import type { Langue } from './langue/index.ts';
import { t, tp } from './langue/index.ts';
import type { Compte, Contact, Message, Statut } from './types.ts';

export type Classement = 'toutes' | 'fils' | 'pj' | 'moi';

export interface Filtre {
  classement: Classement;
  statut: Statut | null;
  agent: string | null;
  projet: string | null;
  recherche: string;
}

export const FILTRE_INITIAL: Filtre = { classement: 'toutes', statut: null, agent: null, projet: null, recherche: '' };

/** Le projet d'une adresse `nom@projet`, ou null pour un compte commun. */
export function projetDe(adresse: string): string | null {
  const i = adresse.indexOf('@');
  return i < 0 ? null : adresse.slice(i + 1);
}

/** Le projet d'une adresse. Par défaut celui qu'elle porte ; avec les comptes, celui où on a rangé un compte commun. */
export type ProjetDe = (adresse: string) => string | null;

/** Le projet de chaque adresse d'après les comptes : un compte commun rangé dans un projet en fait partie,
 *  sans que son adresse ait changé. Une adresse sans compte garde le projet qu'elle porte. */
export function projetsDesComptes(comptes: readonly Compte[]): ProjetDe {
  const table = new Map<string, string | null>();
  for (const c of comptes) table.set(c.nom, c.projet !== undefined ? c.projet : projetDe(c.nom));
  return (adresse) => (table.has(adresse) ? table.get(adresse) ?? null : projetDe(adresse));
}

/** Écrit ou reçu par un compte du projet — la discussion avec les autres projets comprise. */
export function toucheLeProjet(m: Message, projet: string, de: ProjetDe = projetDe): boolean {
  return [m.de, ...m.a].some((x) => de(x) === projet);
}

/** Une adresse du projet affiché se lit sans son projet ; les autres le gardent. */
export function adresseCourte(adresse: string, projet: string | null): string {
  return projet && projetDe(adresse) === projet ? adresse.slice(0, adresse.indexOf('@')) : adresse;
}

/** Le nom lisible d'une adresse si son compte s'est enrôlé (`CL_Agent-…_WIN`), sinon l'adresse courte. */
export function nomAffiche(adresse: string, affichages: ReadonlyMap<string, string>, projet: string | null): string {
  return affichages.get(adresse) ?? adresseCourte(adresse, projet);
}

/** La table adresse → nom lisible, pour les comptes qui en ont un. */
export function affichagesDe(comptes: readonly Compte[]): Map<string, string> {
  const table = new Map<string, string>();
  for (const c of comptes) if (c.affichage) table.set(c.nom, c.affichage);
  return table;
}

/** Les projets que ce message touche (émetteur et destinataires), sans doublon, dans l'ordre d'apparition.
 *  Un message entre comptes communs (`owner`) n'en touche aucun. */
export function projetsDe(m: Message, de: ProjetDe = projetDe): string[] {
  const vus: string[] = [];
  for (const adresse of [m.de, ...m.a]) {
    const p = de(adresse);
    if (p && !vus.includes(p)) vus.push(p);
  }
  return vus;
}

/** Le nombre de teintes dont disposent les étiquettes de projet (voir `.projet-etiquette--t*`). */
export const TEINTES = 4;

/** La teinte d'un projet : toujours la même pour un même nom, partout dans l'interface. */
export function teinteProjet(projet: string): number {
  let h = 0;
  for (const c of projet) h = (h * 31 + (c.codePointAt(0) ?? 0)) % 9973;
  return h % TEINTES;
}

/** L'objet tel qu'on l'affiche : préfixé de `Re : <id> — ` pour une réponse, dans la langue choisie. */
export function titre(m: Message, langue: Langue): string {
  return (m.re ? t(langue, 'domaine.titre.reponse', { id: m.re }) : '') + m.objet;
}

export function instant(m: Message): Date {
  return new Date(m.date);
}

/** `AAAAMMJJ` dans le fuseau du navigateur. */
export function cleJour(d: Date): string {
  return `${d.getFullYear()}${deux(d.getMonth() + 1)}${deux(d.getDate())}`;
}

/** La locale de chaque langue, pour tout le formatage temporel. */
const LOCALES: Record<Langue, string> = { fr: 'fr-FR', en: 'en-US' };

/** « 23:05 » ou « 11:05 PM » selon la langue. */
export function heure(d: Date, langue: Langue): string {
  return new Intl.DateTimeFormat(LOCALES[langue], { hour: '2-digit', minute: '2-digit' }).format(d);
}

export function minutesDuJour(d: Date): number {
  return d.getHours() * 60 + d.getMinutes();
}

/** « 18 septembre », suivi de l'année si ce n'est pas l'année en cours. */
export function libelleJour(cle: string, aujourdhui: Date = new Date(), langue: Langue): string {
  const annee = Number(cle.slice(0, 4));
  const options: Intl.DateTimeFormatOptions = { day: 'numeric', month: 'long' };
  if (annee !== aujourdhui.getFullYear()) options.year = 'numeric';
  return new Intl.DateTimeFormat(LOCALES[langue], options)
    .format(new Date(annee, Number(cle.slice(4, 6)) - 1, Number(cle.slice(6, 8))));
}

/** « 18/09 23:00 » en français ; l'ordre et le séparateur suivent la langue (« 09/18, 11:00 PM »). */
export function horodatage(d: Date, langue: Langue): string {
  return new Intl.DateTimeFormat(LOCALES[langue], { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }).format(d);
}

/** Du plus récent au plus ancien ; à date égale, le dernier écrit d'abord. */
/** Où en est ce message pour `compte` — null s'il n'en est pas destinataire. */
export function statutPour(m: Message, compte: string): Statut | null {
  if (!m.a.includes(compte)) return null;
  return m.statuts?.[compte] ?? m.statut;
}

/** Ce message attend-il encore `compte` ? C'est ce qui le fait apparaître comme du courrier à lui. */
export function attend(m: Message, compte: string): boolean {
  return statutPour(m, compte) === 'nouveau';
}

export function recents(messages: readonly Message[]): Message[] {
  return messages
    .map((m, i) => ({ m, i, t: instant(m).getTime() }))
    .sort((x, y) => y.t - x.t || y.i - x.i)
    .map(({ m }) => m);
}

export function filtrer(messages: readonly Message[], filtre: Filtre, compte: string, de: ProjetDe = projetDe): Message[] {
  const cherche = filtre.recherche.trim().toLowerCase();
  return messages.filter((m) => {
    if (filtre.statut && m.mien !== filtre.statut) return false;
    if (filtre.classement === 'fils' && !m.re) return false;
    if (filtre.classement === 'pj' && !m.pj) return false;
    if (filtre.classement === 'moi' && !m.a.includes(compte)) return false;
    if (filtre.agent && m.de !== filtre.agent && !m.a.includes(filtre.agent)) return false;
    if (filtre.projet && !toucheLeProjet(m, filtre.projet, de)) return false;
    if (cherche) {
      // le contenu, sans habillage typographique : la recherche ne dépend pas de la langue affichée
      const texte = [m.id, m.re ?? '', m.objet, m.pj ?? '', m.de, ...m.a, ...m.corps].join(' ').toLowerCase();
      if (!texte.includes(cherche)) return false;
    }
    return true;
  });
}

export interface Compteurs {
  total: number;
  nouveau: number;
  lu: number;
  traité: number;
  fils: number;
  pj: number;
  moi: number;
}

export function compter(messages: readonly Message[], compte: string): Compteurs {
  const c: Compteurs = { total: messages.length, nouveau: 0, lu: 0, traité: 0, fils: 0, pj: 0, moi: 0 };
  for (const m of messages) {
    c[m.mien] += 1;
    if (m.re) c.fils += 1;
    if (m.pj) c.pj += 1;
    if (m.a.includes(compte)) c.moi += 1;
  }
  return c;
}

export interface Agent {
  nom: string;
  projet: string | null;
  role: string | undefined;
  /** Nom lisible pour un humain, si l'agent s'est enrôlé ; sinon l'adresse fait foi. */
  affichage: string | undefined;
  hote: string | undefined;
  machine: string | undefined;
  contacts: readonly Contact[];
  envois: number;
  dernierEnvoi: Date | null;
  /** Messages « nouveau » qui lui sont adressés. */
  enAttente: number;
  /** Depuis quand le plus ancien attend : un agent qui ne relève pas se voit. */
  attenteDepuis: Date | null;
  /** Compte importé que son agent n'a jamais repris : il ne relève pas. */
  aCompleter: boolean;
}

/** Les comptes actifs — ceux du projet et les comptes communs, si un projet est choisi —
 *  du plus récemment actif au silencieux. */
export function agents(comptes: readonly Compte[], messages: readonly Message[], projet: string | null = null): Agent[] {
  const de = projetsDesComptes(comptes);
  return comptes
    .filter((c) => c.actif && (!projet || de(c.nom) === projet || de(c.nom) === null))
    .map((c) => {
      const envoyes = messages.filter((m) => m.de === c.nom);
      const attendus = messages.filter((m) => attend(m, c.nom));
      const dernier = envoyes.reduce<Date | null>((acc, m) => {
        const d = instant(m);
        return !acc || d > acc ? d : acc;
      }, null);
      return {
        nom: c.nom,
        projet: de(c.nom),
        role: c.role,
        affichage: c.affichage,
        hote: c.hote,
        machine: c.machine,
        contacts: c.contacts ?? [],
        envois: envoyes.length,
        dernierEnvoi: dernier,
        enAttente: attendus.length,
        attenteDepuis: attendus.reduce<Date | null>((acc, m) => (!acc || instant(m) < acc ? instant(m) : acc), null),
        aCompleter: c.hote === 'inconnu',
      };
    })
    .sort((x, y) => (y.dernierEnvoi?.getTime() ?? -1) - (x.dernierEnvoi?.getTime() ?? -1));
}

export interface GroupeAgents {
  /** Le projet du groupe ; null pour les comptes communs à tous les projets. */
  projet: string | null;
  agents: Agent[];
}

/** Les agents rangés par projet : les projets dans l'ordre donné (même sans agent — un projet tout juste
 *  connecté se voit), puis ceux qu'on ne connaissait pas, puis les comptes communs. L'ordre des agents est gardé. */
export function groupesAgents(liste: readonly Agent[], projets: readonly string[]): GroupeAgents[] {
  const noms = [...projets];
  for (const a of liste) if (a.projet && !noms.includes(a.projet)) noms.push(a.projet);
  const groupes: GroupeAgents[] = noms.map((projet) => ({ projet, agents: liste.filter((a) => a.projet === projet) }));
  const communs = liste.filter((a) => a.projet === null);
  if (communs.length > 0 || groupes.length === 0) groupes.push({ projet: null, agents: communs });
  return groupes;
}

export interface Point {
  message: Message;
  minutes: number;
  envoye: boolean;
}

export interface Couloir {
  agent: string;
  points: Point[];
}

/** Un couloir par agent ayant écrit ou reçu ce jour-là, dans l'ordre donné. */
export function couloirs(messages: readonly Message[], jour: string, ordre: readonly string[]): Couloir[] {
  const duJour = messages.filter((m) => cleJour(instant(m)) === jour);
  return ordre
    .map((agent) => ({
      agent,
      points: duJour
        .filter((m) => m.de === agent || m.a.includes(agent))
        .map((m) => ({ message: m, minutes: minutesDuJour(instant(m)), envoye: m.de === agent })),
    }))
    .filter((c) => c.points.length > 0);
}

/** Le message auquel celui-ci répond, puis ses réponses, dans l'ordre d'envoi. */
export function fil(messages: readonly Message[], m: Message): Message[] {
  const parent = m.re ? messages.filter((x) => x.id === m.re) : [];
  const reponses = messages.filter((x) => x.re === m.id);
  return [...parent, ...[...reponses].sort((x, y) => instant(x).getTime() - instant(y).getTime())];
}

export interface Projet {
  nom: string;
  messages: number;
  /** Messages « nouveau » qui le touchent. */
  nouveaux: number;
  /** Comptes actifs du projet. */
  agents: number;
}

export function projets(noms: readonly string[], messages: readonly Message[], comptes: readonly Compte[] = []): Projet[] {
  const de = projetsDesComptes(comptes);
  return noms.map((nom) => {
    const siens = messages.filter((m) => toucheLeProjet(m, nom, de));
    return {
      nom,
      messages: siens.length,
      nouveaux: siens.filter((m) => m.statut === 'nouveau').length,
      agents: comptes.filter((c) => c.actif && de(c.nom) === nom).length,
    };
  });
}

/** « depuis 4 h », « depuis 3 j » : l'ancienneté d'une attente, en un mot, dans la langue choisie. */
export function anciennete(depuis: Date, maintenant: Date = new Date(), langue: Langue): string {
  const minutes = Math.max(0, Math.round((maintenant.getTime() - depuis.getTime()) / 60000));
  if (minutes < 60) return tp(langue, Math.max(1, minutes), 'domaine.attente.minute');
  if (minutes < 48 * 60) return tp(langue, Math.round(minutes / 60), 'domaine.attente.heure');
  return tp(langue, Math.round(minutes / 1440), 'domaine.attente.jour');
}

/** Le nom de projet qu'on propose pour un dossier : son dernier segment, réduit à ce qu'un projet admet. */
export function projetPropose(dossier: string): string {
  const segment = dossier.replace(/[\\/]+$/, '').split(/[\\/]/).pop() ?? '';
  return segment.normalize('NFKD').replace(/\p{M}/gu, '').toLowerCase()
    .replace(/[^a-z0-9._-]+/g, '-').replace(/^[^a-z0-9]+|-+$/g, '').slice(0, 32).replace(/-+$/, '');
}

/** « OW » pour owner, « CW » pour claude-windows (le projet ne compte pas). */
export function initiales(adresse: string): string {
  const nom = adresse.split('@')[0] ?? adresse;
  const parts = nom.split(/[-_.]/).filter(Boolean);
  const lettres = parts.length > 1 ? (parts[0]?.[0] ?? '') + (parts[1]?.[0] ?? '') : nom.slice(0, 2);
  return lettres.toUpperCase();
}

function deux(n: number): string {
  return String(n).padStart(2, '0');
}
