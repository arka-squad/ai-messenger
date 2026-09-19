import { FolderPlus, Inbox, LoaderCircle } from 'lucide-react';
import { useState } from 'react';
import type { Activation, Creation } from '../domain/types.ts';

/** Connecter un projet (un dépôt local) à la boîte : hooks et skill posés, ses agents s'enrôlent. */
export function ConnecterProjet({ onConnecter }: {
  onConnecter: (dossier: string, projet: string) => Promise<Activation>;
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
      setSucces(`Connecté : ${r.dossier}${r.projet ? ` · projet ${r.projet}` : ''}`);
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
          <input
            className="ajout__champ" value={dossier} placeholder="Chemin du dépôt (ex. C:\\dev\\talos)"
            aria-label="Chemin local du dépôt" onChange={(e) => setDossier(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') void soumettre(); }}
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
            Pose les hooks et la skill dans <code>.claude/</code> : chaque agent qui l’ouvrira sera invité à s’enrôler.
          </span>
          {succes && <span className="ajout__succes" role="status">{succes}</span>}
          {erreur && <span className="ajout__erreur" role="alert">{erreur}</span>}
        </div>
      )}
    </>
  );
}

/** Créer la boîte (arbo `.aimessenger/`) quand il n'y en a pas ; ou dire pourquoi c'est indisponible. */
export function CreerBoite({ motif, onCreer }: {
  motif: string | null;
  onCreer: (dossier: string) => Promise<Creation>;
}) {
  const [ouvert, setOuvert] = useState(false);
  const [dossier, setDossier] = useState('');
  const [envoi, setEnvoi] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);

  // motif non nul = une boîte existe mais n'est pas inscriptible (ex. Markdown) : on n'offre pas la création.
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
          <input
            className="ajout__champ" value={dossier} placeholder="Dossier partagé (ex. X:\\agents)"
            aria-label="Dossier partagé de la boîte" onChange={(e) => setDossier(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') void soumettre(); }}
          />
          <button type="button" className="ajout__valider" disabled={!dossier.trim() || envoi} onClick={() => void soumettre()}>
            {envoi ? <LoaderCircle className="ic spin" size={13} /> : <Inbox className="ic" size={13} />}
            <span>Créer la boîte</span>
          </button>
          <span className="ajout__aide">
            Crée l’arbo <code>.aimessenger/</code> dans ce dossier et l’ouvre. Choisis un partage vu par toutes les machines.
          </span>
          {erreur && <span className="ajout__erreur" role="alert">{erreur}</span>}
        </div>
      )}
    </div>
  );
}
