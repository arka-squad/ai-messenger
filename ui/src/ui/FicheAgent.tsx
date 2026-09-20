/** La fiche d'un agent : qui il est, son projet, son carnet d'adresses — et de quoi l'organiser. */
import { BookUser, Check, Copy, LoaderCircle, Merge, Plus, Trash2, X } from 'lucide-react';
import { useState } from 'react';
import { utiliseLangue } from '../application/langue.tsx';
import { type Agent, anciennete, projetDe, projetPropose } from '../domain/boite.ts';
import { t, tp } from '../domain/langue/index.ts';
import type { Invitation } from '../domain/types.ts';
import { EtiquetteProjet } from './EtiquettesProjet.tsx';
import { TexteACopier, copierTexte } from './MiseEnPlace.tsx';

interface Props {
  agent: Agent;
  /** Tous les agents : ceux qu'on peut mettre dans son carnet. */
  agents: readonly Agent[];
  projets: readonly string[];
  /** La boîte est inscriptible : on peut ranger, inviter, tenir le carnet. */
  modifiable: boolean;
  onRattacher: (compte: string, projet: string | null) => Promise<void>;
  onNoterContact: (compte: string, alias: string, adresses: string[], note: string) => Promise<void>;
  onRetirerContact: (compte: string, alias: string) => Promise<void>;
  onInviter: (invitation: Invitation) => Promise<string>;
  /** Fusionne cet agent dans un autre compte : le sien est fermé, son courrier suit. */
  onFusionner: (compte: string, dans: string) => Promise<void>;
  onFermer: () => void;
}

/** Une valeur qu'aucun projet ne peut porter : un nom de projet n'a pas d'espace. */
const NOUVEAU = 'nouveau projet';

export function FicheAgent({ agent: a, agents, projets, modifiable, onRattacher, onNoterContact, onRetirerContact,
  onInviter, onFusionner, onFermer }: Props) {
  const l = utiliseLangue();
  const [erreur, setErreur] = useState<string | null>(null);
  const [occupe, setOccupe] = useState(false);

  /** Un geste sur la boîte : son refus s'affiche ici, en clair. */
  const agir = async (geste: () => Promise<void>) => {
    if (occupe) return;
    setOccupe(true);
    setErreur(null);
    try {
      await geste();
    } catch (e) {
      setErreur(e instanceof Error ? e.message : String(e));
    } finally {
      setOccupe(false);
    }
  };

  return (
    <section className="fiche rise" aria-label={t(l, 'accueil.agentAria', { nom: a.affichage ?? a.nom })}>
      <div className="fiche__tete">
        <span className={`point-rond ${a.enAttente ? 'attente pulse' : 'ok'}`} />
        <span className="fiche__nom">{a.affichage ?? a.nom.split('@')[0]}</span>
        <span className="fiche__adresse" title={t(l, 'accueil.adresseTitle')}>{a.nom}</span>
        <EtiquetteProjet projet={a.projet} avecIcone />
        <span className="vide" />
        <button type="button" className="modale__fermer" aria-label={t(l, 'accueil.fermerFiche')} onClick={onFermer}><X className="ic" size={15} /></button>
      </div>
      <div className="fiche__infos">
        {[a.hote && a.hote !== 'inconnu' ? a.hote : null, a.machine, a.role].filter(Boolean).join(' · ') || t(l, 'accueil.aucuneInfo')}
      </div>
      {(a.enAttente > 0 || a.aCompleter) && (
        <div className="fiche__alerte" role="status">
          {a.aCompleter
            ? t(l, 'accueil.alerteReprise')
            : ''}
          {a.enAttente > 0 && a.attenteDepuis
            ? tp(l, a.enAttente, 'accueil.alerteAttente', { anciennete: anciennete(a.attenteDepuis, new Date(), l) })
            : ''}
          {t(l, 'accueil.alerteInvite')}
        </div>
      )}

      <div className="fiche__colonnes">
        <div className="fiche__bloc">
          <span className="eyebrow">{t(l, 'accueil.projetRubrique')}</span>
          <ChoixProjet agent={a} projets={projets} modifiable={modifiable && !occupe}
            onChoix={(projet) => agir(() => onRattacher(a.nom, projet))} />
          <InviteAgent compte={a.nom} modifiable={modifiable} onInviter={onInviter} />
          {modifiable && (
            <FusionCompte agent={a} agents={agents} occupe={occupe}
              onFusionner={(dans) => agir(() => onFusionner(a.nom, dans))} />
          )}
        </div>
        <div className="fiche__bloc fiche__bloc--large">
          <span className="eyebrow"><BookUser className="ic" size={11} /> {t(l, 'accueil.carnet')}</span>
          {a.contacts.length === 0 && <span className="detail__aucun">{t(l, 'accueil.aucunContact')}</span>}
          {a.contacts.map((c) => (
            <div key={c.alias} className="contact">
              <span className="contact__alias">{c.alias}</span>
              <span className="contact__fleche">→</span>
              <span className="contact__adresses">{c.adresses.join(', ')}</span>
              {c.note && <span className="contact__note">{c.note}</span>}
              {modifiable && (
                <button type="button" className="contact__retirer" disabled={occupe} aria-label={t(l, 'accueil.retirerContactAria', { alias: c.alias })}
                  title={t(l, 'accueil.retirerContactTitle')} onClick={() => void agir(() => onRetirerContact(a.nom, c.alias))}>
                  <Trash2 className="ic" size={12} />
                </button>
              )}
            </div>
          ))}
          {modifiable && (
            <NouveauContact agent={a} agents={agents} occupe={occupe}
              onAjouter={(alias, adresses, note) => agir(() => onNoterContact(a.nom, alias, adresses, note))} />
          )}
        </div>
      </div>
      {erreur && <span className="ajout__erreur" role="alert">{erreur}</span>}
    </section>
  );
}

/** Ranger l'agent dans un projet. Une adresse `nom@projet` porte déjà le sien : il ne se change pas. */
function ChoixProjet({ agent: a, projets, modifiable, onChoix }: {
  agent: Agent;
  projets: readonly string[];
  modifiable: boolean;
  onChoix: (projet: string | null) => Promise<void>;
}) {
  const l = utiliseLangue();
  const [nouveau, setNouveau] = useState<string | null>(null);
  if (projetDe(a.nom)) {
    return <span className="fiche__aide">{t(l, 'accueil.projetAdresseAvant')}<b>{a.projet}</b>{t(l, 'accueil.projetAdresseApres')}</span>;
  }
  if (!modifiable && nouveau === null) {
    return <span className="fiche__aide">{a.projet ? t(l, 'accueil.rangeDans', { projet: a.projet }) : t(l, 'accueil.sansProjetCompte')}</span>;
  }
  const propose = nouveau === null ? '' : projetPropose(nouveau);
  return (
    <>
      <select
        className="ajout__champ" aria-label={t(l, 'accueil.projetAgentAria')} value={nouveau !== null ? NOUVEAU : a.projet ?? ''}
        onChange={(e) => {
          if (e.target.value === NOUVEAU) setNouveau('');
          else { setNouveau(null); void onChoix(e.target.value || null); }
        }}
      >
        <option value="">{t(l, 'accueil.optionSansProjet')}</option>
        {[...new Set([...projets, ...(a.projet ? [a.projet] : [])])].sort().map((p) => <option key={p} value={p}>{p}</option>)}
        <option value={NOUVEAU}>{t(l, 'accueil.nouveauProjetOption')}</option>
      </select>
      {nouveau !== null && (
        <div className="fiche__ligne">
          <input className="ajout__champ" autoFocus value={nouveau} placeholder={t(l, 'accueil.nomProjet')} aria-label={t(l, 'accueil.nouveauProjet')}
            onChange={(e) => setNouveau(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && propose) { void onChoix(propose); setNouveau(null); } }} />
          <button type="button" className="ajout__valider" disabled={!propose}
            onClick={() => { void onChoix(propose); setNouveau(null); }}>
            <Check className="ic" size={13} /><span>{t(l, 'accueil.ranger')}</span>
          </button>
        </div>
      )}
      <span className="fiche__aide">{t(l, 'accueil.adresseNeChangePas')}</span>
    </>
  );
}

/** Deux comptes pour le même agent ? On les fusionne : celui-ci se ferme, son courrier en attente passe
 *  à l'autre, et ce qui s'écrit encore à son adresse y arrive. Les messages déjà envoyés ne changent pas. */
function FusionCompte({ agent: a, agents, occupe, onFusionner }: {
  agent: Agent;
  agents: readonly Agent[];
  occupe: boolean;
  onFusionner: (dans: string) => Promise<void>;
}) {
  const l = utiliseLangue();
  const [dans, setDans] = useState('');
  const autres = agents.filter((x) => x.nom !== a.nom);
  if (autres.length === 0) return null;
  return (
    <>
      <span className="eyebrow fiche__eyebrow-espace">{t(l, 'accueil.deuxComptes')}</span>
      <select
        className="ajout__champ" aria-label={t(l, 'accueil.fusionnerDansAria')} value={dans}
        onChange={(e) => setDans(e.target.value)}
      >
        <option value="">{t(l, 'accueil.fusionnerDansOption')}</option>
        {autres.map((x) => <option key={x.nom} value={x.nom}>{x.affichage ?? x.nom}</option>)}
      </select>
      {dans && (
        <>
          <button type="button" className="ajout__valider" disabled={occupe} onClick={() => void onFusionner(dans)}>
            {occupe ? <LoaderCircle className="ic spin" size={13} /> : <Merge className="ic" size={13} />}
            <span>{t(l, 'accueil.fusionner')}</span>
          </button>
          <span className="fiche__aide">
            {t(l, 'accueil.fusionAvant', { nom: a.affichage ?? a.nom })}<b>{dans}</b>{t(l, 'accueil.fusionApres')}
          </span>
        </>
      )}
    </>
  );
}

/** L'invite pour un agent qui a déjà son compte : il le reprend depuis son dossier de travail. */
function InviteAgent({ compte, modifiable, onInviter }: {
  compte: string;
  modifiable: boolean;
  onInviter: (invitation: Invitation) => Promise<string>;
}) {
  const l = utiliseLangue();
  const [etat, setEtat] = useState<'repos' | 'envoi' | 'copie'>('repos');
  const [aCopier, setACopier] = useState<string | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  if (!modifiable) return null;
  const copier = async () => {
    setEtat('envoi');
    setErreur(null);
    try {
      const invite = await onInviter({ compte });
      if (await copierTexte(invite)) {
        setEtat('copie');
        setTimeout(() => setEtat('repos'), 4000);
        return;
      }
      setACopier(invite);
    } catch (e) {
      setErreur(e instanceof Error ? e.message : String(e));
    }
    setEtat('repos');
  };
  return (
    <>
      <button type="button" className="ajout__valider" disabled={etat === 'envoi'} onClick={() => void copier()}>
        {etat === 'envoi' ? <LoaderCircle className="ic spin" size={13} /> : etat === 'copie' ? <Check className="ic" size={13} /> : <Copy className="ic" size={13} />}
        <span>{etat === 'copie' ? t(l, 'accueil.inviteCopiee') : t(l, 'accueil.copierSonInvite')}</span>
      </button>
      <span className="fiche__aide">{t(l, 'accueil.aCollerAide')}</span>
      {aCopier && <TexteACopier texte={aCopier} />}
      {erreur && <span className="ajout__erreur" role="alert">{erreur}</span>}
    </>
  );
}

/** Ajouter un contact : un nom court, et l'agent — ou les agents — qu'il désigne. */
function NouveauContact({ agent: a, agents, occupe, onAjouter }: {
  agent: Agent;
  agents: readonly Agent[];
  occupe: boolean;
  onAjouter: (alias: string, adresses: string[], note: string) => Promise<void>;
}) {
  const l = utiliseLangue();
  const [ouvert, setOuvert] = useState(false);
  const [alias, setAlias] = useState('');
  const [note, setNote] = useState('');
  const [choisis, setChoisis] = useState<string[]>([]);
  const propose = projetPropose(alias);
  const pret = Boolean(propose) && choisis.length > 0 && !occupe;

  if (!ouvert) {
    return (
      <button type="button" className="fiche__ajouter" onClick={() => setOuvert(true)}>
        <Plus className="ic" size={12} /><span>{t(l, 'accueil.ajouterContact')}</span>
      </button>
    );
  }
  const ajouter = async () => {
    if (!pret) return;
    await onAjouter(propose, choisis, note.trim());
    setAlias('');
    setNote('');
    setChoisis([]);
    setOuvert(false);
  };
  return (
    <div className="fiche__formulaire">
      <input className="ajout__champ" autoFocus value={alias} placeholder={t(l, 'accueil.nomCourtExemple')} aria-label={t(l, 'accueil.nomCourtAria')}
        onChange={(e) => setAlias(e.target.value)} />
      <span className="fiche__aide">{t(l, 'accueil.quiDesigne')}</span>
      <div className="fiche__choix">
        {agents.filter((x) => x.nom !== a.nom).map((x) => {
          const coche = choisis.includes(x.nom);
          return (
            <button key={x.nom} type="button" className={`puce${coche ? ' puce--cochee' : ''}`} aria-pressed={coche} title={x.nom}
              onClick={() => setChoisis((c) => (coche ? c.filter((n) => n !== x.nom) : [...c, x.nom]))}>
              {coche && <Check className="ic" size={10} />}{x.affichage ?? x.nom}
            </button>
          );
        })}
      </div>
      <input className="ajout__champ" value={note} placeholder={t(l, 'accueil.notePlaceholder')} aria-label={t(l, 'accueil.noteAria')}
        maxLength={200} onChange={(e) => setNote(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') void ajouter(); }} />
      <div className="fiche__ligne">
        <button type="button" className="ajout__valider" disabled={!pret} onClick={() => void ajouter()}>
          <Plus className="ic" size={13} /><span>{t(l, 'accueil.ajouter')}{propose && propose !== alias.trim() ? t(l, 'accueil.ajouterNomme', { propose }) : ''}</span>
        </button>
        <button type="button" className="fiche__annuler" onClick={() => setOuvert(false)}>{t(l, 'accueil.annuler')}</button>
      </div>
    </div>
  );
}
