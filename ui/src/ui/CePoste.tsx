/** Ce poste : ses outils d'IA sont-ils prêts à lire la boîte ? Et de quoi éteindre la boîte qu'on a allumée. */
import { Check, LoaderCircle, Power, TriangleAlert, Wrench } from 'lucide-react';
import { useEffect, useState } from 'react';
import type { Poste } from '../domain/types.ts';

interface Props {
  onPoste: () => Promise<Poste>;
  onPreparer: () => Promise<Poste>;
  onEteindre: () => Promise<void>;
}

export function CePoste({ onPoste, onPreparer, onEteindre }: Props) {
  const [poste, setPoste] = useState<Poste | null>(null);
  const [occupe, setOccupe] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);

  useEffect(() => {
    let vivant = true;
    onPoste().then((p) => { if (vivant) setPoste(p); }).catch(() => { /* API plus ancienne : pas d'encart */ });
    return () => { vivant = false; };
  }, [onPoste]);

  if (!poste) return null;
  const prets = poste.hotes.filter((h) => h.equipe);
  const aPreparer = poste.hotes.filter((h) => !h.equipe);

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
    <div className="rail__section">
      <span className="eyebrow">Ce poste</span>
      {poste.hotes.length === 0 && (
        <span className="ajout__aide">Aucun outil d’IA trouvé sur ce poste (Claude Code, Codex, Kimi Code, Antigravity, Cursor).</span>
      )}
      {prets.length > 0 && (
        <span className="poste__ligne poste__ligne--ok" title="Ces outils lisent et écrivent la boîte tout seuls">
          <Check className="ic" size={12} /><span>Prêts : {prets.map((h) => h.nom).join(', ')}</span>
        </span>
      )}
      {aPreparer.length > 0 && (
        <>
          <span className="poste__ligne poste__ligne--attention">
            <TriangleAlert className="ic" size={12} /><span>À préparer : {aPreparer.map((h) => h.nom).join(', ')}</span>
          </span>
          <button type="button" className="ajout__valider" disabled={occupe}
            onClick={() => void agir(async () => setPoste(await onPreparer()))}>
            {occupe ? <LoaderCircle className="ic spin" size={13} /> : <Wrench className="ic" size={13} />}
            <span>Préparer ce poste</span>
          </button>
          <span className="ajout__aide">Branche la boîte dans ces outils, sans rien effacer de leurs réglages. Pris en compte à leur prochaine ouverture.</span>
        </>
      )}
      {poste.eteignable && (
        <>
          <button type="button" className="rail-boite" disabled={occupe} onClick={() => void agir(onEteindre)}>
            <Power className="ic" size={15} />
            <span className="rail-boite__libelle">Éteindre la boîte</span>
          </button>
          <span className="ajout__aide">Ferme cette fenêtre sur la boîte. Tes agents, eux, continuent de s’écrire.</span>
        </>
      )}
      {erreur && <span className="ajout__erreur" role="alert">{erreur}</span>}
    </div>
  );
}
