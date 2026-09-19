import { FolderGit2, Inbox, Layers, type LucideIcon, Paperclip, Reply, UserRound } from 'lucide-react';
import {
  type Agent,
  type Classement,
  type Compteurs,
  type Filtre,
  type Projet,
  adresseCourte,
  cleJour,
  heure,
  horodatage,
} from '../domain/boite.ts';
import type { Activation } from '../domain/types.ts';
import { AjoutDepot } from './AjoutDepot.tsx';

interface Props {
  compte: string;
  compteurs: Compteurs;
  projets: readonly Projet[];
  agents: readonly Agent[];
  filtre: Filtre;
  onFiltre: (f: Filtre) => void;
  /** La boîte est réelle : on peut y activer un dépôt depuis l'interface. */
  activable: boolean;
  onActiver: (dossier: string, projet: string) => Promise<Activation>;
  derniereReleve: Date | null;
  constat: string;
}

export function Rail({ compte, compteurs, projets, agents, filtre, onFiltre, activable, onActiver,
  derniereReleve, constat }: Props) {
  const boites: [Classement, string, LucideIcon, number][] = [
    ['toutes', 'Tous les messages', Inbox, compteurs.total],
    ['fils', 'Réponses', Reply, compteurs.fils],
    ['pj', 'Avec pièce jointe', Paperclip, compteurs.pj],
    ['moi', compte === 'owner' ? 'Adressés à l’Owner' : `Adressés à ${compte}`, UserRound, compteurs.moi],
  ];
  const aujourdhui = cleJour(new Date());

  return (
    <aside className="rail">
      <nav className="rail__boites" aria-label="Boîtes">
        {boites.map(([id, libelle, Icone, n]) => (
          <button
            key={id}
            type="button"
            className={`rail-boite${filtre.classement === id ? ' rail-boite--actif' : ''}`}
            onClick={() => onFiltre({ ...filtre, classement: id })}
          >
            <Icone className="ic" size={15} />
            <span className="rail-boite__libelle">{libelle}</span>
            <span className="compteur">{n}</span>
          </button>
        ))}
      </nav>

      {projets.length > 0 && (
        <div className="rail__section">
          <span className="eyebrow">Projets</span>
          <button
            type="button"
            className={`rail-boite${filtre.projet === null ? ' rail-boite--actif' : ''}`}
            onClick={() => onFiltre({ ...filtre, projet: null })}
          >
            <Layers className="ic" size={15} />
            <span className="rail-boite__libelle">Tous les projets</span>
            <span className="compteur">{compteurs.total}</span>
          </button>
          {projets.map((p) => (
            <button
              key={p.nom}
              type="button"
              className={`rail-boite${filtre.projet === p.nom ? ' rail-boite--actif' : ''}`}
              title={`${p.messages} message${p.messages > 1 ? 's' : ''}, dont les échanges avec les autres projets`}
              // Changer de projet libère le filtre d'agent : ses agents ne sont pas ceux d'un autre projet.
              onClick={() => onFiltre({ ...filtre, projet: filtre.projet === p.nom ? null : p.nom, agent: null })}
            >
              <FolderGit2 className="ic" size={15} />
              <span className="rail-boite__libelle rail-boite__libelle--mono">{p.nom}</span>
              {p.nouveaux > 0 && <span className="point-rond attente" title={`${p.nouveaux} nouveau(x)`} />}
              <span className="compteur">{p.messages}</span>
            </button>
          ))}
        </div>
      )}

      {activable && <AjoutDepot onActiver={onActiver} />}

      <div className="rail__section">
        <span className="eyebrow">Agents</span>
        {agents.map((a) => {
          const actif = filtre.agent === a.nom;
          const dernier = a.dernierEnvoi
            ? `dernier ${cleJour(a.dernierEnvoi) === aujourdhui ? heure(a.dernierEnvoi) : horodatage(a.dernierEnvoi).slice(0, 5)}`
            : 'silencieux';
          return (
            <button
              key={a.nom}
              type="button"
              className={`rail-agent${actif ? ' rail-agent--actif' : ''}`}
              title={`${a.nom} · ${a.envois} envoi${a.envois > 1 ? 's' : ''}${a.role ? ` · ${a.role}` : ''}`}
              onClick={() => onFiltre({ ...filtre, agent: actif ? null : a.nom })}
            >
              <span className={`point-rond ${a.enAttente ? 'attente pulse' : 'ok'}`} />
              <span className="rail-agent__nom">{a.affichage ?? adresseCourte(a.nom, filtre.projet)}</span>
              <span className="rail-agent__dernier">{dernier}</span>
            </button>
          );
        })}
      </div>

      <div className="rail__releve">
        <span className="eyebrow">Relève</span>
        <span className="rail__releve-texte">
          Toute écriture dans la boîte réveille l’agent en session ; sinon il relève au démarrage suivant.
        </span>
        <span className="rail__releve-constat">
          {derniereReleve ? `Dernière relève ${heure(derniereReleve)} · ${constat}` : 'Première relève…'}
        </span>
      </div>
    </aside>
  );
}
