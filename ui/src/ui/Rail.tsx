import { BookUser, FolderGit2, Inbox, Layers, type LucideIcon, Paperclip, Reply, UserRound } from 'lucide-react';
import {
  type Agent,
  type Classement,
  type Compteurs,
  type Filtre,
  type GroupeAgents,
  type Projet,
  anciennete,
  cleJour,
  heure,
  horodatage,
  teinteProjet,
} from '../domain/boite.ts';
import type { Activation, Creation, Invitation, Poste, Source } from '../domain/types.ts';
import { CePoste } from './CePoste.tsx';
import { EtiquetteProjet } from './EtiquettesProjet.tsx';
import { ConnecterProjet, CreerBoite, InviterAgent } from './MiseEnPlace.tsx';

interface Props {
  compte: string;
  compteurs: Compteurs;
  projets: readonly Projet[];
  /** Les agents, rangés par projet ; les comptes communs à la fin. */
  groupes: readonly GroupeAgents[];
  filtre: Filtre;
  onFiltre: (f: Filtre) => void;
  /** La boîte est réelle et inscriptible : on peut y connecter un projet. */
  activable: boolean;
  /** Quand il n'y a pas de boîte inscriptible : le motif (boîte Markdown…), ou null pour offrir la création. */
  motifCreation: string | null;
  onInviter: (invitation: Invitation) => Promise<string>;
  onPoste: () => Promise<Poste>;
  onPreparer: () => Promise<Poste>;
  onEteindre: () => Promise<void>;
  onActiver: (dossier: string, projet: string) => Promise<Activation>;
  onCreer: (dossier: string) => Promise<Creation>;
  onOuvrirBoite: (dossier: string) => Promise<string>;
  /** La boîte que ce poste lit, pour l'encart « Ce poste ». */
  source: Source | null;
  onChoisir: () => Promise<string | null>;
  derniereReleve: Date | null;
  constat: string;
}

export function Rail({ compte, compteurs, projets, groupes, filtre, onFiltre, activable, motifCreation,
  onInviter, onPoste, onPreparer, onEteindre, onActiver, onCreer, onOuvrirBoite, source, onChoisir,
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

      {(activable || projets.length > 0) && (
        <div className="rail__section">
          <span className="eyebrow">Projets</span>
          {projets.length > 0 && (
            <button
              type="button"
              className={`rail-boite${filtre.projet === null ? ' rail-boite--actif' : ''}`}
              onClick={() => onFiltre({ ...filtre, projet: null })}
            >
              <Layers className="ic" size={15} />
              <span className="rail-boite__libelle">Tous les projets</span>
              <span className="compteur">{compteurs.total}</span>
            </button>
          )}
          {projets.map((p) => (
            <button
              key={p.nom}
              type="button"
              className={`rail-boite${filtre.projet === p.nom ? ' rail-boite--actif' : ''}`}
              title={`${p.agents} agent${p.agents > 1 ? 's' : ''} · ${p.messages} message${p.messages > 1 ? 's' : ''}, dont les échanges avec les autres projets`}
              // Changer de projet libère le filtre d'agent : ses agents ne sont pas ceux d'un autre projet.
              onClick={() => onFiltre({ ...filtre, projet: filtre.projet === p.nom ? null : p.nom, agent: null })}
            >
              <FolderGit2 className={`ic teinte--t${teinteProjet(p.nom)}`} size={15} />
              <span className="rail-boite__libelle rail-boite__libelle--mono">{p.nom}</span>
              {p.nouveaux > 0 && <span className="point-rond attente" title={`${p.nouveaux} nouveau(x)`} />}
              <span className="compteur">{p.messages}</span>
            </button>
          ))}
          {activable && <ConnecterProjet onConnecter={onActiver} onChoisir={onChoisir} onInviter={onInviter} />}
          {activable && <InviterAgent projets={projets.map((p) => p.nom)} projetCourant={filtre.projet} onInviter={onInviter} />}
        </div>
      )}

      {!activable && <CreerBoite motif={motifCreation} onCreer={onCreer} onChoisir={onChoisir} />}

      <div className="rail__section">
        <span className="eyebrow">Agents</span>
        {groupes.map((g) => (
          <div key={g.projet ?? '·commun'} className="rail-groupe">
            <div className="rail-groupe__tete">
              {g.projet === null ? <EtiquetteProjet projet={null} avecIcone /> : (
                <button
                  type="button"
                  className="rail-groupe__projet"
                  title={filtre.projet === g.projet ? 'Voir tous les projets' : `Ne voir que le projet ${g.projet}`}
                  onClick={() => onFiltre({ ...filtre, projet: filtre.projet === g.projet ? null : g.projet, agent: null })}
                >
                  <EtiquetteProjet projet={g.projet} avecIcone actif={filtre.projet === g.projet} />
                </button>
              )}
              <span className="vide" />
              <span className="compteur">{g.agents.length}</span>
            </div>
            {g.agents.length === 0 && (
              <span className="rail-groupe__vide">Aucun agent encore — copie l’invite et colle-la à ton agent.</span>
            )}
            {g.agents.map((a) => <LigneAgent key={a.nom} agent={a} filtre={filtre} onFiltre={onFiltre} aujourdhui={aujourdhui} />)}
          </div>
        ))}
      </div>

      <CePoste source={source} onPoste={onPoste} onPreparer={onPreparer} onEteindre={onEteindre}
        onOuvrirBoite={onOuvrirBoite} onChoisir={onChoisir} />

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

/** Un agent dans son groupe : le projet est déjà dit par l'en-tête, on lit donc son nom seul. */
function LigneAgent({ agent: a, filtre, onFiltre, aujourdhui }: {
  agent: Agent;
  filtre: Filtre;
  onFiltre: (f: Filtre) => void;
  aujourdhui: string;
}) {
  const actif = filtre.agent === a.nom;
  const dernier = a.dernierEnvoi
    ? `dernier ${cleJour(a.dernierEnvoi) === aujourdhui ? heure(a.dernierEnvoi) : horodatage(a.dernierEnvoi).slice(0, 5)}`
    : 'silencieux';
  const fiche = [
    a.nom,
    [a.hote, a.machine].filter(Boolean).join(' · '),
    a.role,
    `${a.envois} envoi${a.envois > 1 ? 's' : ''}`,
    a.contacts.length ? `carnet : ${a.contacts.map((c) => `${c.alias} → ${c.adresses.join(', ')}`).join(' ; ')}` : '',
  ].filter(Boolean).join('\n');
  return (
    <button
      type="button"
      className={`rail-agent${actif ? ' rail-agent--actif' : ''}`}
      title={fiche}
      onClick={() => onFiltre({ ...filtre, agent: actif ? null : a.nom })}
    >
      <span className={`point-rond ${a.enAttente ? 'attente pulse' : 'ok'}`} />
      <span className="rail-agent__texte">
        <span className="rail-agent__nom">{a.affichage ?? a.nom.split('@')[0]}</span>
        <span className="rail-agent__meta">
          <span className="rail-agent__dernier">{dernier}</span>
          {a.enAttente > 0 && (
            <span className="rail-agent__attente" title={a.attenteDepuis ? `Le plus ancien attend ${anciennete(a.attenteDepuis)}` : undefined}>
              {a.enAttente} en attente{a.attenteDepuis ? ` ${anciennete(a.attenteDepuis)}` : ''}
            </span>
          )}
          {a.contacts.length > 0 && (
            <span className="rail-agent__carnet"><BookUser className="ic" size={10} />{a.contacts.length}</span>
          )}
        </span>
      </span>
    </button>
  );
}
