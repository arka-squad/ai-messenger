/**
 * Ce que l'interface calcule à partir de l'état : filtres, compteurs, agents,
 * couloirs du trafic, fil de discussion. Fonctions pures, sans DOM ni React.
 *
 * Les règles (qui peut faire avancer quoi) ne sont PAS ici : l'API les rend
 * dans `Message.suite`, décidées par le domaine Python.
 */
import type { Compte, Message, Statut } from './types.ts';

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

/** Écrit ou reçu par un compte du projet — la discussion avec les autres projets comprise. */
export function toucheLeProjet(m: Message, projet: string): boolean {
  return [m.de, ...m.a].some((x) => projetDe(x) === projet);
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
export function projetsDe(m: Message): string[] {
  const vus: string[] = [];
  for (const adresse of [m.de, ...m.a]) {
    const p = projetDe(adresse);
    if (p && !vus.includes(p)) vus.push(p);
  }
  return vus;
}

/** L'objet tel qu'on l'affiche : préfixé de `Re : <id> — ` pour une réponse. */
export function titre(m: Message): string {
  return (m.re ? `Re : ${m.re} — ` : '') + m.objet;
}

export function instant(m: Message): Date {
  return new Date(m.date);
}

/** `AAAAMMJJ` dans le fuseau du navigateur. */
export function cleJour(d: Date): string {
  return `${d.getFullYear()}${deux(d.getMonth() + 1)}${deux(d.getDate())}`;
}

export function heure(d: Date): string {
  return `${deux(d.getHours())}:${deux(d.getMinutes())}`;
}

export function minutesDuJour(d: Date): number {
  return d.getHours() * 60 + d.getMinutes();
}

const MOIS = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre',
  'octobre', 'novembre', 'décembre'];

/** « 18 septembre », suivi de l'année si ce n'est pas l'année en cours. */
export function libelleJour(cle: string, aujourdhui: Date = new Date()): string {
  const annee = Number(cle.slice(0, 4));
  const jour = `${Number(cle.slice(6, 8))} ${MOIS[Number(cle.slice(4, 6)) - 1] ?? ''}`;
  return annee === aujourdhui.getFullYear() ? jour : `${jour} ${annee}`;
}

/** « 18/09 23:00 » */
export function horodatage(d: Date): string {
  return `${deux(d.getDate())}/${deux(d.getMonth() + 1)} ${heure(d)}`;
}

/** Du plus récent au plus ancien ; à date égale, le dernier écrit d'abord. */
export function recents(messages: readonly Message[]): Message[] {
  return messages
    .map((m, i) => ({ m, i, t: instant(m).getTime() }))
    .sort((x, y) => y.t - x.t || y.i - x.i)
    .map(({ m }) => m);
}

export function filtrer(messages: readonly Message[], filtre: Filtre, compte: string): Message[] {
  const cherche = filtre.recherche.trim().toLowerCase();
  return messages.filter((m) => {
    if (filtre.statut && m.statut !== filtre.statut) return false;
    if (filtre.classement === 'fils' && !m.re) return false;
    if (filtre.classement === 'pj' && !m.pj) return false;
    if (filtre.classement === 'moi' && !m.a.includes(compte)) return false;
    if (filtre.agent && m.de !== filtre.agent && !m.a.includes(filtre.agent)) return false;
    if (filtre.projet && !toucheLeProjet(m, filtre.projet)) return false;
    if (cherche) {
      const texte = [m.id, titre(m), m.pj ?? '', m.de, ...m.a, ...m.corps].join(' ').toLowerCase();
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
    c[m.statut] += 1;
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
  envois: number;
  dernierEnvoi: Date | null;
  /** Messages « nouveau » qui lui sont adressés. */
  enAttente: number;
}

/** Les comptes actifs — ceux du projet et les comptes communs, si un projet est choisi —
 *  du plus récemment actif au silencieux. */
export function agents(comptes: readonly Compte[], messages: readonly Message[], projet: string | null = null): Agent[] {
  return comptes
    .filter((c) => c.actif && (!projet || projetDe(c.nom) === projet || projetDe(c.nom) === null))
    .map((c) => {
      const envoyes = messages.filter((m) => m.de === c.nom);
      const dernier = envoyes.reduce<Date | null>((acc, m) => {
        const d = instant(m);
        return !acc || d > acc ? d : acc;
      }, null);
      return {
        nom: c.nom,
        projet: projetDe(c.nom),
        role: c.role,
        affichage: c.affichage,
        envois: envoyes.length,
        dernierEnvoi: dernier,
        enAttente: messages.filter((m) => m.a.includes(c.nom) && m.statut === 'nouveau').length,
      };
    })
    .sort((x, y) => (y.dernierEnvoi?.getTime() ?? -1) - (x.dernierEnvoi?.getTime() ?? -1));
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
}

export function projets(noms: readonly string[], messages: readonly Message[]): Projet[] {
  return noms.map((nom) => {
    const siens = messages.filter((m) => toucheLeProjet(m, nom));
    return { nom, messages: siens.length, nouveaux: siens.filter((m) => m.statut === 'nouveau').length };
  });
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
