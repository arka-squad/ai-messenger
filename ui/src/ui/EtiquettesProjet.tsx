import { FolderGit2 } from 'lucide-react';

/** Les projets qu'un message touche, en pastilles. Rien ne s'affiche si la liste est vide :
 *  un message entre comptes communs, ou dont le seul projet est déjà celui qu'on filtre. */
export function EtiquettesProjet({ projets, avecIcone = false }: { projets: readonly string[]; avecIcone?: boolean }) {
  if (projets.length === 0) return null;
  return (
    <span className="projets">
      {projets.map((p) => (
        <span key={p} className="projet-etiquette" title={`Projet ${p}`}>
          {avecIcone && <FolderGit2 className="ic" size={9} />}
          {p}
        </span>
      ))}
    </span>
  );
}
