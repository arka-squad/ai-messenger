import { FolderPlus, LoaderCircle } from 'lucide-react';
import { useState } from 'react';
import type { Activation } from '../domain/types.ts';

interface Props {
  /** La boîte est réelle et inscriptible : on peut y activer un dépôt. */
  activable: boolean;
  /** Pourquoi l'activation est indisponible, quand elle l'est (boîte de démo, lecture seule). */
  motif: string | null;
  onActiver: (dossier: string, projet: string) => Promise<Activation>;
}

/** Un dépôt local qu'un humain ajoute à la boîte : hooks et skill y sont posés, ses agents s'enrôlent. */
export function AjoutDepot({ activable, motif, onActiver }: Props) {
  const [ouvert, setOuvert] = useState(false);
  const [dossier, setDossier] = useState('');
  const [projet, setProjet] = useState('');
  const [envoi, setEnvoi] = useState(false);
  const [succes, setSucces] = useState<string | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);

  if (!activable) {
    return (
      <div className="rail__section">
        <span className="eyebrow">Dépôts</span>
        <span className="ajout__aide">{motif ?? 'Activation de dépôt indisponible pour cette boîte.'}</span>
      </div>
    );
  }

  const soumettre = async () => {
    if (!dossier.trim() || envoi) return;
    setEnvoi(true);
    setErreur(null);
    setSucces(null);
    try {
      const r = await onActiver(dossier.trim(), projet.trim());
      setSucces(`Activé : ${r.dossier}${r.projet ? ` · projet ${r.projet}` : ''}`);
      setDossier('');
      setProjet('');
    } catch (e) {
      setErreur(e instanceof Error ? e.message : String(e));
    } finally {
      setEnvoi(false);
    }
  };

  return (
    <div className="rail__section">
      <span className="eyebrow">Dépôts</span>
      <button
        type="button"
        className={`rail-boite${ouvert ? ' rail-boite--actif' : ''}`}
        onClick={() => setOuvert((o) => !o)}
      >
        <FolderPlus className="ic" size={15} />
        <span className="rail-boite__libelle">Ajouter un dépôt</span>
      </button>

      {ouvert && (
        <div className="ajout">
          <input
            className="ajout__champ"
            value={dossier}
            placeholder="Chemin du dépôt (ex. C:\\dev\\talos)"
            aria-label="Chemin local du dépôt"
            onChange={(e) => setDossier(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') void soumettre();
            }}
          />
          <input
            className="ajout__champ"
            value={projet}
            placeholder="Projet (facultatif, ex. talos)"
            aria-label="Nom du projet"
            onChange={(e) => setProjet(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') void soumettre();
            }}
          />
          <button type="button" className="ajout__valider" disabled={!dossier.trim() || envoi} onClick={() => void soumettre()}>
            {envoi ? <LoaderCircle className="ic spin" size={13} /> : <FolderPlus className="ic" size={13} />}
            <span>Activer ce dépôt</span>
          </button>
          <span className="ajout__aide">
            Pose les hooks et la skill dans <code>.claude/</code> : chaque agent qui l’ouvrira sera invité à s’enrôler.
          </span>
          {succes && <span className="ajout__succes" role="status">{succes}</span>}
          {erreur && <span className="ajout__erreur" role="alert">{erreur}</span>}
        </div>
      )}
    </div>
  );
}
