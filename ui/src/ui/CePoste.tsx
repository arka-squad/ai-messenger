/** Ce poste : où est sa boîte, ses outils d'IA sont-ils prêts, et de quoi éteindre la boîte qu'on a allumée. */
import { Check, FolderInput, LoaderCircle, Power, TriangleAlert, Wrench } from 'lucide-react';
import { useEffect, useState } from 'react';
import { utiliseLangue } from '../application/langue.tsx';
import { t } from '../domain/langue/index.ts';
import type { Poste, Source } from '../domain/types.ts';
import { ChampDossier } from './MiseEnPlace.tsx';

interface Props {
  /** La boîte que ce poste lit en ce moment (null tant que l'état n'est pas chargé). */
  source: Source | null;
  onPoste: () => Promise<Poste>;
  onPreparer: () => Promise<Poste>;
  onEteindre: () => Promise<void>;
  onOuvrirBoite: (dossier: string) => Promise<string>;
  onChoisir: () => Promise<string | null>;
}

export function CePoste({ source, onPoste, onPreparer, onEteindre, onOuvrirBoite, onChoisir }: Props) {
  const [poste, setPoste] = useState<Poste | null>(null);
  const [occupe, setOccupe] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);
  const l = utiliseLangue();

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
      <span className="eyebrow">{t(l, 'accueil.cePoste')}</span>
      <BoiteDuPoste source={source} onOuvrirBoite={onOuvrirBoite} onChoisir={onChoisir} />
      {poste.hotes.length === 0 && (
        <span className="ajout__aide">{t(l, 'accueil.aucunOutil')}</span>
      )}
      {prets.length > 0 && (
        <span className="poste__ligne poste__ligne--ok" title={t(l, 'accueil.pretsTitle')}>
          <Check className="ic" size={12} /><span>{t(l, 'accueil.prets', { noms: prets.map((h) => h.nom).join(', ') })}</span>
        </span>
      )}
      {aPreparer.length > 0 && (
        <>
          <span className="poste__ligne poste__ligne--attention">
            <TriangleAlert className="ic" size={12} /><span>{t(l, 'accueil.aPreparer', { noms: aPreparer.map((h) => h.nom).join(', ') })}</span>
          </span>
          <button type="button" className="ajout__valider" disabled={occupe}
            onClick={() => void agir(async () => setPoste(await onPreparer()))}>
            {occupe ? <LoaderCircle className="ic spin" size={13} /> : <Wrench className="ic" size={13} />}
            <span>{t(l, 'accueil.preparerPoste')}</span>
          </button>
          <span className="ajout__aide">{t(l, 'accueil.preparerAide')}</span>
        </>
      )}
      {poste.eteignable && (
        <>
          <button type="button" className="rail-boite" disabled={occupe} onClick={() => void agir(onEteindre)}>
            <Power className="ic" size={15} />
            <span className="rail-boite__libelle">{t(l, 'accueil.eteindreBoite')}</span>
          </button>
          <span className="ajout__aide">{t(l, 'accueil.eteindreAide')}</span>
        </>
      )}
      {/* erreur venant du backend : laissée telle quelle, hors périmètre de ce chantier */}
      {erreur && <span className="ajout__erreur" role="alert">{erreur}</span>}
    </div>
  );
}

/** Où est la boîte de ce poste, et de quoi la changer : chaque machine désigne le même dossier
 *  partagé, vu par son propre chemin (X:\… sur Windows, /Volumes/… sur le Mac). */
function BoiteDuPoste({ source, onOuvrirBoite, onChoisir }: {
  source: Source | null;
  onOuvrirBoite: (dossier: string) => Promise<string>;
  onChoisir: () => Promise<string | null>;
}) {
  const [ouvert, setOuvert] = useState(false);
  const [dossier, setDossier] = useState('');
  const [envoi, setEnvoi] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);
  const l = utiliseLangue();

  const soumettre = async () => {
    if (!dossier.trim() || envoi) return;
    setEnvoi(true);
    setErreur(null);
    try {
      await onOuvrirBoite(dossier.trim());  // la relève recharge : l'interface bascule sur cette boîte
      setOuvert(false);
      setDossier('');
    } catch (e) {
      setErreur(e instanceof Error ? e.message : String(e));
    } finally {
      setEnvoi(false);
    }
  };

  return (
    <>
      {source && (
        <span className="poste__boite" title={source.chemin}>
          {source.demonstration ? t(l, 'accueil.boiteDemo') : t(l, 'accueil.boiteChemin', { chemin: source.chemin })}
        </span>
      )}
      <button type="button" className={`rail-boite${ouvert ? ' rail-boite--actif' : ''}`} onClick={() => setOuvert((o) => !o)}>
        <FolderInput className="ic" size={15} />
        <span className="rail-boite__libelle">{t(l, source?.demonstration ? 'accueil.ouvrirMaBoite' : 'accueil.changerBoite')}</span>
      </button>
      {ouvert && (
        <div className="ajout">
          <ChampDossier
            dossier={dossier} invite={t(l, 'accueil.choisirDossierBoite')} etiquette={t(l, 'accueil.dossierPartageBoite')}
            onDossier={setDossier} onChoisir={onChoisir} onEntree={() => void soumettre()}
          />
          <button type="button" className="ajout__valider" disabled={!dossier.trim() || envoi} onClick={() => void soumettre()}>
            {envoi ? <LoaderCircle className="ic spin" size={13} /> : <FolderInput className="ic" size={13} />}
            <span>{t(l, 'accueil.ouvrirCetteBoite')}</span>
          </button>
          <span className="ajout__aide">{t(l, 'accueil.changerBoiteAide')}</span>
          {erreur && <span className="ajout__erreur" role="alert">{erreur}</span>}
        </div>
      )}
    </>
  );
}
