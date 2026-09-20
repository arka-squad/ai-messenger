/** La mise en place, pour un humain : créer la boîte, y connecter un projet, inviter un agent. */
import { Check, Copy, FolderOpen, FolderPlus, Inbox, LoaderCircle } from 'lucide-react';
import { useState } from 'react';
import type { Activation, Creation } from '../domain/types.ts';

type Choisir = () => Promise<string | null>;

/** Copier l'invite à coller dans le chat de son agent : il lit le guide d'accueil et s'enrôle seul. */
export function InviterAgent({ invite }: { invite: string | null }) {
  const [copie, setCopie] = useState(false);
  if (!invite) return null;
  const copier = async () => {
    try {
      await navigator.clipboard.writeText(invite);
      setCopie(true);
      setTimeout(() => setCopie(false), 2500);
    } catch {
      // presse-papiers indisponible (contexte non sécurisé) : on ne casse rien
    }
  };
  return (
    <button type="button" className="rail-boite" onClick={() => void copier()} title="Colle ce texte dans le chat de ton agent">
      {copie ? <Check className="ic" size={15} /> : <Copy className="ic" size={15} />}
      <span className="rail-boite__libelle">{copie ? 'Invite copiée — colle-la à ton agent' : "Copier l'invite pour l'agent"}</span>
    </button>
  );
}

/** Connecter un projet (un dépôt local) à la boîte. */
export function ConnecterProjet({ onConnecter, onChoisir }: {
  onConnecter: (dossier: string, projet: string) => Promise<Activation>;
  onChoisir: Choisir;
}) {
  const [ouvert, setOuvert] = useState(false);
  const [dossier, setDossier] = useState('');
  const [projet, setProjet] = useState('');
  const [envoi, setEnvoi] = useState(false);
  const [succes, setSucces] = useState<string | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);

  const soumettre = async () => {
    if (!dossier.trim() || envoi) return;
    setEnvoi(true);
    setErreur(null);
    setSucces(null);
    try {
      const r = await onConnecter(dossier.trim(), projet.trim());
      const equipes = r.hotes.filter((h) => h.equipe).map((h) => h.nom);
      setSucces(`Connecté : ${r.dossier}${r.projet ? ` · projet ${r.projet}` : ''}`
        + (equipes.length ? ` · agents prêts dans ${equipes.join(', ')}` : ''));
      setDossier('');
      setProjet('');
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
        <span className="rail-boite__libelle">Connecter un projet</span>
      </button>
      {ouvert && (
        <div className="ajout">
          <ChampDossier
            dossier={dossier} invite="Choisir le dossier du projet…" etiquette="Chemin local du dépôt"
            onDossier={setDossier} onChoisir={onChoisir} onEntree={() => void soumettre()}
          />
          <input
            className="ajout__champ" value={projet} placeholder="Projet (facultatif, ex. talos)"
            aria-label="Nom du projet" onChange={(e) => setProjet(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') void soumettre(); }}
          />
          <button type="button" className="ajout__valider" disabled={!dossier.trim() || envoi} onClick={() => void soumettre()}>
            {envoi ? <LoaderCircle className="ic spin" size={13} /> : <FolderPlus className="ic" size={13} />}
            <span>Connecter</span>
          </button>
          <span className="ajout__aide">
            Rattache un dossier de projet à la boîte et prépare les outils d’IA de ce poste. Ensuite, « Copier l’invite pour l’agent » et colle-la dans son chat : il crée son compte tout seul.
          </span>
          {succes && <span className="ajout__succes" role="status">{succes}</span>}
          {erreur && <span className="ajout__erreur" role="alert">{erreur}</span>}
        </div>
      )}
    </>
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

  if (motif) {
    return (
      <div className="rail__section">
        <span className="eyebrow">Boîte</span>
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
      <span className="eyebrow">Boîte</span>
      <button type="button" className={`rail-boite${ouvert ? ' rail-boite--actif' : ''}`} onClick={() => setOuvert((o) => !o)}>
        <Inbox className="ic" size={15} />
        <span className="rail-boite__libelle">Créer la boîte</span>
      </button>
      {ouvert && (
        <div className="ajout">
          <ChampDossier
            dossier={dossier} invite="Choisir le dossier de la boîte…" etiquette="Dossier partagé de la boîte"
            onDossier={setDossier} onChoisir={onChoisir} onEntree={() => void soumettre()}
          />
          <button type="button" className="ajout__valider" disabled={!dossier.trim() || envoi} onClick={() => void soumettre()}>
            {envoi ? <LoaderCircle className="ic spin" size={13} /> : <Inbox className="ic" size={13} />}
            <span>Créer la boîte</span>
          </button>
          <span className="ajout__aide">
            Crée la boîte dans ce dossier et l’ouvre. Choisis un dossier partagé, vu par toutes tes machines.
          </span>
          {erreur && <span className="ajout__erreur" role="alert">{erreur}</span>}
        </div>
      )}
    </div>
  );
}

/** Un dossier : le sélecteur natif du poste d'abord, le chemin collé à la main en repli. */
function ChampDossier({ dossier, invite, etiquette, onDossier, onChoisir, onEntree }: {
  dossier: string;
  invite: string;
  etiquette: string;
  onDossier: (dossier: string) => void;
  onChoisir: Choisir;
  onEntree: () => void;
}) {
  const parcourir = async () => {
    try {
      const choisi = await onChoisir();
      if (choisi) onDossier(choisi);
    } catch {
      // sélecteur natif indisponible sur ce poste : le champ texte reste utilisable
    }
  };
  return (
    <>
      <button type="button" className="ajout__parcourir" onClick={() => void parcourir()}>
        <FolderOpen className="ic" size={13} />
        <span>{dossier || invite}</span>
      </button>
      <input
        className="ajout__champ" value={dossier} placeholder="…ou colle le chemin" aria-label={etiquette}
        onChange={(e) => onDossier(e.target.value)}
        onKeyDown={(e) => { if (e.key === 'Enter') onEntree(); }}
      />
    </>
  );
}
