import { FolderGit2, Users } from 'lucide-react';
import { teinteProjet } from '../domain/boite.ts';

/** Un projet, en pastille : la même teinte pour un même projet partout dans l'interface.
 *  `null` est le cas des comptes communs à tous les projets (`owner`…). */
export function EtiquetteProjet({ projet, avecIcone = false, actif = false }: {
  projet: string | null;
  avecIcone?: boolean;
  /** Le projet actuellement filtré : sa pastille est pleine. */
  actif?: boolean;
}) {
  if (projet === null) {
    return (
      <span className="projet-etiquette projet-etiquette--commun" title="Compte commun à tous les projets">
        {avecIcone && <Users className="ic" size={9} />}
        commun
      </span>
    );
  }
  return (
    <span
      className={`projet-etiquette projet-etiquette--t${teinteProjet(projet)}${actif ? ' projet-etiquette--actif' : ''}`}
      title={`Projet ${projet}`}
    >
      {avecIcone && <FolderGit2 className="ic" size={9} />}
      {projet}
    </span>
  );
}

/** Les projets qu'un message touche, en pastilles ; « commun » s'il ne circule qu'entre comptes communs.
 *  Tout message en porte donc une : on sait toujours à quel projet il appartient. */
export function EtiquettesProjet({ projets, avecIcone = false, filtre = null }: {
  projets: readonly string[];
  avecIcone?: boolean;
  filtre?: string | null;
}) {
  return (
    <span className="projets">
      {projets.length === 0
        ? <EtiquetteProjet projet={null} avecIcone={avecIcone} />
        : projets.map((p) => <EtiquetteProjet key={p} projet={p} avecIcone={avecIcone} actif={p === filtre} />)}
    </span>
  );
}
