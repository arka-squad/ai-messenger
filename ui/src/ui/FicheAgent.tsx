/** La fiche d'un agent : qui il est, son projet, son carnet d'adresses — et de quoi l'organiser. */
import { BookUser, Check, Copy, LoaderCircle, Merge, Plus, Trash2, X } from 'lucide-react';
import { useState } from 'react';
import { type Agent, anciennete, projetDe, projetPropose } from '../domain/boite.ts';
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
    <section className="fiche rise" aria-label={`Agent ${a.affichage ?? a.nom}`}>
      <div className="fiche__tete">
        <span className={`point-rond ${a.enAttente ? 'attente pulse' : 'ok'}`} />
        <span className="fiche__nom">{a.affichage ?? a.nom.split('@')[0]}</span>
        <span className="fiche__adresse" title="Son adresse dans la boîte">{a.nom}</span>
        <EtiquetteProjet projet={a.projet} avecIcone />
        <span className="vide" />
        <button type="button" className="modale__fermer" aria-label="Fermer la fiche" onClick={onFermer}><X className="ic" size={15} /></button>
      </div>
      <div className="fiche__infos">
        {[a.hote && a.hote !== 'inconnu' ? a.hote : null, a.machine, a.role].filter(Boolean).join(' · ') || 'Aucune information sur ce compte.'}
      </div>
      {(a.enAttente > 0 || a.aCompleter) && (
        <div className="fiche__alerte" role="status">
          {a.aCompleter
            ? 'Ce compte a été repris d’une ancienne boîte : son agent ne l’a jamais repris, il ne relève donc pas son courrier. '
            : ''}
          {a.enAttente > 0 && a.attenteDepuis
            ? `${a.enAttente} message${a.enAttente > 1 ? 's' : ''} l’attend${a.enAttente > 1 ? 'ent' : ''} ${anciennete(a.attenteDepuis)}. `
            : ''}
          S’il ne répond pas, envoie-lui son invite : il reprendra son compte depuis son dossier de travail.
        </div>
      )}

      <div className="fiche__colonnes">
        <div className="fiche__bloc">
          <span className="eyebrow">Projet</span>
          <ChoixProjet agent={a} projets={projets} modifiable={modifiable && !occupe}
            onChoix={(projet) => agir(() => onRattacher(a.nom, projet))} />
          <InviteAgent compte={a.nom} modifiable={modifiable} onInviter={onInviter} />
          {modifiable && (
            <FusionCompte agent={a} agents={agents} occupe={occupe}
              onFusionner={(dans) => agir(() => onFusionner(a.nom, dans))} />
          )}
        </div>
        <div className="fiche__bloc fiche__bloc--large">
          <span className="eyebrow"><BookUser className="ic" size={11} /> Carnet d’adresses</span>
          {a.contacts.length === 0 && <span className="detail__aucun">Aucun contact. Un contact donne un nom court à un agent, ou à un groupe, à qui il écrit souvent.</span>}
          {a.contacts.map((c) => (
            <div key={c.alias} className="contact">
              <span className="contact__alias">{c.alias}</span>
              <span className="contact__fleche">→</span>
              <span className="contact__adresses">{c.adresses.join(', ')}</span>
              {c.note && <span className="contact__note">{c.note}</span>}
              {modifiable && (
                <button type="button" className="contact__retirer" disabled={occupe} aria-label={`Retirer le contact ${c.alias}`}
                  title="Retirer ce contact" onClick={() => void agir(() => onRetirerContact(a.nom, c.alias))}>
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
  const [nouveau, setNouveau] = useState<string | null>(null);
  if (projetDe(a.nom)) {
    return <span className="fiche__aide">Son adresse porte son projet (<b>{a.projet}</b>) : il ne se range pas ailleurs.</span>;
  }
  if (!modifiable && nouveau === null) {
    return <span className="fiche__aide">{a.projet ? `Rangé dans ${a.projet}.` : 'Sans projet : compte commun à tous les projets.'}</span>;
  }
  const propose = nouveau === null ? '' : projetPropose(nouveau);
  return (
    <>
      <select
        className="ajout__champ" aria-label="Projet de l’agent" value={nouveau !== null ? NOUVEAU : a.projet ?? ''}
        onChange={(e) => {
          if (e.target.value === NOUVEAU) setNouveau('');
          else { setNouveau(null); void onChoix(e.target.value || null); }
        }}
      >
        <option value="">Sans projet (compte commun)</option>
        {[...new Set([...projets, ...(a.projet ? [a.projet] : [])])].sort().map((p) => <option key={p} value={p}>{p}</option>)}
        <option value={NOUVEAU}>Nouveau projet…</option>
      </select>
      {nouveau !== null && (
        <div className="fiche__ligne">
          <input className="ajout__champ" autoFocus value={nouveau} placeholder="Nom du projet" aria-label="Nouveau projet"
            onChange={(e) => setNouveau(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && propose) { void onChoix(propose); setNouveau(null); } }} />
          <button type="button" className="ajout__valider" disabled={!propose}
            onClick={() => { void onChoix(propose); setNouveau(null); }}>
            <Check className="ic" size={13} /><span>Ranger</span>
          </button>
        </div>
      )}
      <span className="fiche__aide">Son adresse ne change pas : son courrier et son carnet restent valables.</span>
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
  const [dans, setDans] = useState('');
  const autres = agents.filter((x) => x.nom !== a.nom);
  if (autres.length === 0) return null;
  return (
    <>
      <span className="eyebrow fiche__eyebrow-espace">Deux comptes, un agent ?</span>
      <select
        className="ajout__champ" aria-label="Fusionner ce compte dans" value={dans}
        onChange={(e) => setDans(e.target.value)}
      >
        <option value="">Fusionner ce compte dans…</option>
        {autres.map((x) => <option key={x.nom} value={x.nom}>{x.affichage ?? x.nom}</option>)}
      </select>
      {dans && (
        <>
          <button type="button" className="ajout__valider" disabled={occupe} onClick={() => void onFusionner(dans)}>
            {occupe ? <LoaderCircle className="ic spin" size={13} /> : <Merge className="ic" size={13} />}
            <span>Fusionner</span>
          </button>
          <span className="fiche__aide">
            « {a.affichage ?? a.nom} » sera fermé : son courrier en attente passe à <b>{dans}</b>, et ce qui
            s’écrit encore à son adresse y arrive. Les messages déjà envoyés ne changent pas.
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
        <span>{etat === 'copie' ? 'Invite copiée' : 'Copier son invite'}</span>
      </button>
      <span className="fiche__aide">À coller dans le chat de cet agent : il reprend ce compte et relève son courrier.</span>
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
  const [ouvert, setOuvert] = useState(false);
  const [alias, setAlias] = useState('');
  const [note, setNote] = useState('');
  const [choisis, setChoisis] = useState<string[]>([]);
  const propose = projetPropose(alias);
  const pret = Boolean(propose) && choisis.length > 0 && !occupe;

  if (!ouvert) {
    return (
      <button type="button" className="fiche__ajouter" onClick={() => setOuvert(true)}>
        <Plus className="ic" size={12} /><span>Ajouter un contact</span>
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
      <input className="ajout__champ" autoFocus value={alias} placeholder="Nom court (ex. release)" aria-label="Nom court du contact"
        onChange={(e) => setAlias(e.target.value)} />
      <span className="fiche__aide">Qui désigne-t-il ? Un agent, ou plusieurs pour un groupe.</span>
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
      <input className="ajout__champ" value={note} placeholder="Note (facultatif) : quand lui écrire" aria-label="Note du contact"
        maxLength={200} onChange={(e) => setNote(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') void ajouter(); }} />
      <div className="fiche__ligne">
        <button type="button" className="ajout__valider" disabled={!pret} onClick={() => void ajouter()}>
          <Plus className="ic" size={13} /><span>Ajouter{propose && propose !== alias.trim() ? ` « ${propose} »` : ''}</span>
        </button>
        <button type="button" className="fiche__annuler" onClick={() => setOuvert(false)}>Annuler</button>
      </div>
    </div>
  );
}
