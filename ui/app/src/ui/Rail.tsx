import { Inbox, type LucideIcon, Paperclip, Reply, UserRound } from 'lucide-react';
import { type Agent, type Classement, type Compteurs, type Filtre, cleJour, heure, horodatage } from '../domain/boite.ts';

interface Props {
  compte: string;
  compteurs: Compteurs;
  agents: readonly Agent[];
  filtre: Filtre;
  onFiltre: (f: Filtre) => void;
  derniereReleve: Date | null;
  constat: string;
}

export function Rail({ compte, compteurs, agents, filtre, onFiltre, derniereReleve, constat }: Props) {
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
              <span className="rail-agent__nom">{a.nom}</span>
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
