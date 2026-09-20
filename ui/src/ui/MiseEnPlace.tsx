/** La mise en place, pour un humain : créer la boîte, y connecter un projet, inviter un agent. */
import { Check, Copy, FolderOpen, FolderPlus, Inbox, LoaderCircle, X } from 'lucide-react';
import { type ReactNode, useEffect, useState } from 'react';
import { utiliseLangue } from '../application/langue.tsx';
import { projetPropose } from '../domain/boite.ts';
import { t } from '../domain/langue/index.ts';
import type { Activation, Creation, Invitation } from '../domain/types.ts';

type Choisir = () => Promise<string | null>;

type Portee = 'existant' | 'nouveau' | 'aucun';

/** Met un texte dans le presse-papiers ; rend false si le navigateur le refuse (l'appelant le montre alors à copier). */
export async function copierTexte(texte: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(texte);
    return true;
  } catch {
    return false;
  }
}

/** Inviter un agent : on choisit d'abord son projet, puis on copie le texte à coller dans son chat.
 *  L'invite porte le projet : l'agent crée son compte dedans, où que soit son dossier de travail. */
export function InviterAgent({ projets, projetCourant, onInviter }: {
  projets: readonly string[];
  /** Le projet actuellement filtré : proposé d'office. */
  projetCourant: string | null;
  onInviter: (invitation: Invitation) => Promise<string>;
}) {
  const [ouvert, setOuvert] = useState(false);
  const [portee, setPortee] = useState<Portee>(projets.length ? 'existant' : 'nouveau');
  const [existant, setExistant] = useState('');
  const [nouveau, setNouveau] = useState('');
  const [envoi, setEnvoi] = useState(false);
  const [copie, setCopie] = useState(false);
  const [aCopier, setACopier] = useState<string | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const l = utiliseLangue();

  const choisi = existant || projetCourant || projets[0] || '';
  const projet = portee === 'existant' ? choisi : portee === 'nouveau' ? projetPropose(nouveau) : null;
  const pret = portee === 'aucun' || Boolean(projet);

  const copier = async () => {
    if (!pret || envoi) return;
    setEnvoi(true);
    setErreur(null);
    setACopier(null);
    try {
      const invite = await onInviter({ projet: projet || null });
      if (await copierTexte(invite)) {
        setCopie(true);
        setTimeout(() => setCopie(false), 4000);
      } else {
        setACopier(invite);  // presse-papiers refusé par le navigateur : on montre le texte
      }
      if (portee === 'nouveau' && projet) {
        setExistant(projet);
        setPortee('existant');
        setNouveau('');
      }
    } catch (e) {
      setErreur(e instanceof Error ? e.message : String(e));
    } finally {
      setEnvoi(false);
    }
  };

  return (
    <>
      <button type="button" className={`rail-boite${ouvert ? ' rail-boite--actif' : ''}`} onClick={() => setOuvert((o) => !o)}>
        <Copy className="ic" size={15} />
        <span className="rail-boite__libelle">{t(l, 'accueil.copierInviteAgent')}</span>
      </button>
      {ouvert && (
        <div className="ajout">
          <span className="ajout__question">{t(l, 'accueil.dansQuelProjet')}</span>
          {projets.length > 0 && (
            <label className="ajout__choix">
              <input type="radio" name="portee" checked={portee === 'existant'} onChange={() => setPortee('existant')} />
              <select
                className="ajout__champ" value={choisi} aria-label={t(l, 'accueil.projetExistant')}
                onFocus={() => setPortee('existant')} onChange={(e) => { setExistant(e.target.value); setPortee('existant'); }}
              >
                {projets.map((p) => <option key={p} value={p}>{p}</option>)}
              </select>
            </label>
          )}
          <label className="ajout__choix">
            <input type="radio" name="portee" checked={portee === 'nouveau'} onChange={() => setPortee('nouveau')} />
            <input
              className="ajout__champ" value={nouveau} placeholder={t(l, 'accueil.nouveauProjetExemple')} aria-label={t(l, 'accueil.nouveauProjet')}
              onFocus={() => setPortee('nouveau')} onChange={(e) => { setNouveau(e.target.value); setPortee('nouveau'); }}
              onKeyDown={(e) => { if (e.key === 'Enter') void copier(); }}
            />
          </label>
          <label className="ajout__choix">
            <input type="radio" name="portee" checked={portee === 'aucun'} onChange={() => setPortee('aucun')} />
            <span className="ajout__choix-texte">{t(l, 'accueil.sansProjet')}</span>
          </label>
          {portee === 'nouveau' && nouveau.trim() && projet !== nouveau.trim() && (
            <span className="ajout__aide">{t(l, 'accueil.projetSeraAvant')}<b>{projet || '…'}</b>{t(l, 'accueil.projetSeraApres')}</span>
          )}
          <button type="button" className="ajout__valider" disabled={!pret || envoi} onClick={() => void copier()}>
            {envoi ? <LoaderCircle className="ic spin" size={13} /> : copie ? <Check className="ic" size={13} /> : <Copy className="ic" size={13} />}
            <span>{copie ? t(l, 'accueil.inviteCopiee') : t(l, 'accueil.copierInvite')}</span>
          </button>
          <span className="ajout__aide">
            {copie
              ? t(l, 'accueil.inviteAideCopiee')
              : t(l, 'accueil.inviteAide')}
          </span>
          {aCopier && <TexteACopier texte={aCopier} />}
          {/* erreur venant du backend : laissée telle quelle, hors périmètre de ce chantier */}
          {erreur && <span className="ajout__erreur" role="alert">{erreur}</span>}
        </div>
      )}
    </>
  );
}

/** Quand le navigateur refuse le presse-papiers : le texte, sélectionné d'un clic, à copier à la main. */
export function TexteACopier({ texte }: { texte: string }) {
  const l = utiliseLangue();
  return (
    <>
      <span className="ajout__aide">{t(l, 'accueil.copieRefusee')}</span>
      <textarea className="ajout__texte" readOnly value={texte} rows={6} onFocus={(e) => e.currentTarget.select()} />
    </>
  );
}

/** Connecter un projet (un dépôt local) à la boîte. */
export function ConnecterProjet({ onConnecter, onChoisir, onInviter }: {
  onConnecter: (dossier: string, projet: string) => Promise<Activation>;
  onChoisir: Choisir;
  onInviter: (invitation: Invitation) => Promise<string>;
}) {
  const [ouvert, setOuvert] = useState(false);
  const [dossier, setDossier] = useState('');
  const [projet, setProjet] = useState('');
  // Tant que l'humain n'a pas touché au nom du projet, il suit le dossier choisi : un projet a toujours un nom.
  const [projetSaisi, setProjetSaisi] = useState(false);
  const [envoi, setEnvoi] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);
  // Le dossier est connecté : reste à inviter les agents du projet — une fenêtre le dit, invite à la main.
  const [connecte, setConnecte] = useState<Activation | null>(null);
  const l = utiliseLangue();

  const choisirDossier = (chemin: string) => {
    setDossier(chemin);
    if (!projetSaisi) setProjet(projetPropose(chemin));
  };

  const soumettre = async () => {
    if (!dossier.trim() || envoi) return;
    setEnvoi(true);
    setErreur(null);
    try {
      setConnecte(await onConnecter(dossier.trim(), projet.trim()));
      setOuvert(false);
      setDossier('');
      setProjet('');
      setProjetSaisi(false);
    } catch (e) {
      setErreur(e instanceof Error ? e.message : String(e));
    } finally {
      setEnvoi(false);
    }
  };

  return (
    <>
      <button type="button" className={`rail-boite${ouvert ? ' rail-boite--actif' : ''}`} onClick={() => setOuvert((o) => !o)}>
        <FolderPlus className="ic" size={15} />
        <span className="rail-boite__libelle">{t(l, 'accueil.connecterProjet')}</span>
      </button>
      {ouvert && (
        <div className="ajout">
          <ChampDossier
            dossier={dossier} invite={t(l, 'accueil.choisirDossierProjet')} etiquette={t(l, 'accueil.cheminLocalDepot')}
            onDossier={choisirDossier} onChoisir={onChoisir} onEntree={() => void soumettre()}
          />
          <input
            className="ajout__champ" value={projet} placeholder={t(l, 'accueil.nomProjetExemple')}
            aria-label={t(l, 'accueil.nomProjet')} onChange={(e) => { setProjet(e.target.value); setProjetSaisi(true); }}
            onKeyDown={(e) => { if (e.key === 'Enter') void soumettre(); }}
          />
          <button type="button" className="ajout__valider" disabled={!dossier.trim() || envoi} onClick={() => void soumettre()}>
            {envoi ? <LoaderCircle className="ic spin" size={13} /> : <FolderPlus className="ic" size={13} />}
            <span>{t(l, 'accueil.connecter')}</span>
          </button>
          <span className="ajout__aide">
            {t(l, 'accueil.connecterAide')}
          </span>
          {erreur && <span className="ajout__erreur" role="alert">{erreur}</span>}
        </div>
      )}
      {connecte && <ProjetConnecte activation={connecte} onInviter={onInviter} onFermer={() => setConnecte(null)} />}
    </>
  );
}

/** La dernière étape après « Connecter un projet » : envoyer l'invite à l'agent, ou aux agents, du projet. */
function ProjetConnecte({ activation, onInviter, onFermer }: {
  activation: Activation;
  onInviter: (invitation: Invitation) => Promise<string>;
  onFermer: () => void;
}) {
  const [envoi, setEnvoi] = useState(false);
  const [copie, setCopie] = useState(false);
  const [aCopier, setACopier] = useState<string | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const l = utiliseLangue();
  const prets = activation.hotes.filter((h) => h.equipe).map((h) => h.nom);

  const copier = async () => {
    if (envoi) return;
    setEnvoi(true);
    setErreur(null);
    try {
      const invite = await onInviter({ projet: activation.projet });
      if (await copierTexte(invite)) setCopie(true);
      else setACopier(invite);
    } catch (e) {
      setErreur(e instanceof Error ? e.message : String(e));
    } finally {
      setEnvoi(false);
    }
  };

  return (
    <Modale titre={activation.projet ? t(l, 'accueil.projetConnecteTitre', { projet: activation.projet }) : t(l, 'accueil.dossierConnecteTitre')} onFermer={onFermer}>
      <span className="modale__chemin">{activation.dossier}</span>
      <p className="modale__texte">
        <b>{t(l, 'accueil.modaleInviteTitre')}</b>{' '}
        {t(l, 'accueil.modaleInviteAvant')}
        {activation.projet && <>{t(l, 'accueil.modaleInviteDans')}{' '}<b>{activation.projet}</b>{' '}</>}
        {t(l, 'accueil.modaleInviteApres')}
      </p>
      <button type="button" className="modale__action" disabled={envoi} onClick={() => void copier()}>
        {envoi ? <LoaderCircle className="ic spin" size={15} /> : copie ? <Check className="ic" size={15} /> : <Copy className="ic" size={15} />}
        <span>{copie ? t(l, 'accueil.inviteCopieeColler') : t(l, 'accueil.copierInvite')}</span>
      </button>
      {copie && <p className="modale__note">{t(l, 'accueil.modaleInviteGroupe')}</p>}
      {aCopier && <TexteACopier texte={aCopier} />}
      {erreur && <span className="ajout__erreur" role="alert">{erreur}</span>}
      {prets.length > 0 && <p className="modale__note">{t(l, 'accueil.outilsPrets', { hotes: prets.join(', ') })}</p>}
    </Modale>
  );
}

/** Une fenêtre au-dessus de la page : Échap ou un clic à côté la ferme. */
export function Modale({ titre, onFermer, children }: { titre: string; onFermer: () => void; children: ReactNode }) {
  const l = utiliseLangue();
  useEffect(() => {
    const surTouche = (e: KeyboardEvent) => { if (e.key === 'Escape') onFermer(); };
    window.addEventListener('keydown', surTouche);
    return () => window.removeEventListener('keydown', surTouche);
  }, [onFermer]);
  return (
    <div className="modale__voile" role="presentation" onClick={onFermer}>
      <div className="modale rise" role="dialog" aria-modal="true" aria-label={titre} onClick={(e) => e.stopPropagation()}>
        <div className="modale__tete">
          <span className="modale__titre">{titre}</span>
          <button type="button" className="modale__fermer" aria-label={t(l, 'accueil.fermer')} onClick={onFermer}><X className="ic" size={15} /></button>
        </div>
        {children}
        <button type="button" className="modale__terminer" onClick={onFermer}>{t(l, 'accueil.terminer')}</button>
      </div>
    </div>
  );
}

/** Créer la boîte quand il n'y en a pas ; ou dire pourquoi ce n'est pas le bon geste. */
export function CreerBoite({ motif, onCreer, onChoisir }: {
  /** Non nul : une boîte existe mais n'est pas inscriptible (ancienne boîte Markdown) — on l'explique. */
  motif: string | null;
  onCreer: (dossier: string) => Promise<Creation>;
  onChoisir: Choisir;
}) {
  const [ouvert, setOuvert] = useState(false);
  const [dossier, setDossier] = useState('');
  const [envoi, setEnvoi] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);
  const l = utiliseLangue();

  if (motif) {
    return (
      <div className="rail__section">
        <span className="eyebrow">{t(l, 'accueil.boiteRubrique')}</span>
        {/* motif résumé par le backend : laissé tel quel, hors périmètre de ce chantier */}
        <span className="ajout__aide">{motif}</span>
      </div>
    );
  }

  const soumettre = async () => {
    if (!dossier.trim() || envoi) return;
    setEnvoi(true);
    setErreur(null);
    try {
      await onCreer(dossier.trim());  // la veille recharge : l'interface bascule sur la nouvelle boîte
    } catch (e) {
      setErreur(e instanceof Error ? e.message : String(e));
      setEnvoi(false);
    }
  };

  return (
    <div className="rail__section">
      <span className="eyebrow">{t(l, 'accueil.boiteRubrique')}</span>
      <button type="button" className={`rail-boite${ouvert ? ' rail-boite--actif' : ''}`} onClick={() => setOuvert((o) => !o)}>
        <Inbox className="ic" size={15} />
        <span className="rail-boite__libelle">{t(l, 'accueil.creerBoite')}</span>
      </button>
      {ouvert && (
        <div className="ajout">
          <ChampDossier
            dossier={dossier} invite={t(l, 'accueil.choisirDossierBoite')} etiquette={t(l, 'accueil.dossierPartageBoite')}
            onDossier={setDossier} onChoisir={onChoisir} onEntree={() => void soumettre()}
          />
          <button type="button" className="ajout__valider" disabled={!dossier.trim() || envoi} onClick={() => void soumettre()}>
            {envoi ? <LoaderCircle className="ic spin" size={13} /> : <Inbox className="ic" size={13} />}
            <span>{t(l, 'accueil.creerBoite')}</span>
          </button>
          <span className="ajout__aide">
            {t(l, 'accueil.creerBoiteAide')}
          </span>
          {erreur && <span className="ajout__erreur" role="alert">{erreur}</span>}
        </div>
      )}
    </div>
  );
}

/** Un dossier : le sélecteur natif du poste d'abord, le chemin collé à la main en repli. */
export function ChampDossier({ dossier, invite, etiquette, onDossier, onChoisir, onEntree }: {
  dossier: string;
  invite: string;
  etiquette: string;
  onDossier: (dossier: string) => void;
  onChoisir: Choisir;
  onEntree: () => void;
}) {
  const [ouvert, setOuvert] = useState(false);
  const [panne, setPanne] = useState<string | null>(null);
  const l = utiliseLangue();
  const parcourir = async () => {
    if (ouvert) return;
    setOuvert(true);
    setPanne(null);
    try {
      const choisi = await onChoisir();
      if (choisi) onDossier(choisi);
    } catch (e) {
      // La fenêtre n'a pas pu s'ouvrir : on le dit, et le champ texte reste utilisable.
      setPanne(e instanceof Error ? e.message : String(e));
    } finally {
      setOuvert(false);
    }
  };
  return (
    <>
      <button type="button" className="ajout__parcourir" disabled={ouvert} onClick={() => void parcourir()}>
        {ouvert ? <LoaderCircle className="ic spin" size={13} /> : <FolderOpen className="ic" size={13} />}
        <span>{ouvert ? t(l, 'accueil.fenetreOuverte') : dossier || invite}</span>
      </button>
      {ouvert && <span className="ajout__aide">{t(l, 'accueil.choisirDossierAide')}</span>}
      {/* la panne est le message d'une exception (souvent le backend) : laissée telle quelle */}
      {panne && <span className="ajout__erreur" role="alert">{panne}</span>}
      <input
        className="ajout__champ" value={dossier} placeholder={t(l, 'accueil.collerChemin')} aria-label={etiquette}
        onChange={(e) => onDossier(e.target.value)}
        onKeyDown={(e) => { if (e.key === 'Enter') onEntree(); }}
      />
    </>
  );
}
