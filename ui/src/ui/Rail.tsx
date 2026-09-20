import { BookUser, FolderGit2, Inbox, Layers, type LucideIcon, Paperclip, Reply, UserRound } from 'lucide-react';
import { utiliseLangue } from '../application/langue.tsx';
import { libelleConstat, type Constat } from '../application/veille.ts';
import { t, tp } from '../domain/langue/index.ts';
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
  constat: Constat;
}

export function Rail({ compte, compteurs, projets, groupes, filtre, onFiltre, activable, motifCreation,
  onInviter, onPoste, onPreparer, onEteindre, onActiver, onCreer, onOuvrirBoite, source, onChoisir,
  derniereReleve, constat }: Props) {
  const l = utiliseLangue();
  // Les valeurs 'toutes'/'fils'/'pj'/'moi' servent de filtre et de classe CSS : on traduit les libellés, pas elles.
  const boites: [Classement, string, LucideIcon, number][] = [
    ['toutes', t(l, 'coquille.tousMessages'), Inbox, compteurs.total],
    ['fils', t(l, 'coquille.reponses'), Reply, compteurs.fils],
    ['pj', t(l, 'coquille.avecPieceJointe'), Paperclip, compteurs.pj],
    ['moi', t(l, 'coquille.adressesA', {
      compte: compte === 'owner' ? t(l, 'coquille.proprietaire') : compte,
    }), UserRound, compteurs.moi],
  ];
  const aujourdhui = cleJour(new Date());

  return (
    <aside className="rail">
      <nav className="rail__boites" aria-label={t(l, 'coquille.navBoites')}>
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
          <span className="eyebrow">{t(l, 'coquille.projets')}</span>
          {projets.length > 0 && (
            <button
              type="button"
              className={`rail-boite${filtre.projet === null ? ' rail-boite--actif' : ''}`}
              onClick={() => onFiltre({ ...filtre, projet: null })}
            >
              <Layers className="ic" size={15} />
              <span className="rail-boite__libelle">{t(l, 'coquille.tousProjets')}</span>
              <span className="compteur">{compteurs.total}</span>
            </button>
          )}
          {projets.map((p) => (
            <button
              key={p.nom}
              type="button"
              className={`rail-boite${filtre.projet === p.nom ? ' rail-boite--actif' : ''}`}
              title={`${tp(l, p.agents, 'coquille.projetAgents')} · ${tp(l, p.messages, 'coquille.projetMessages')}, ${t(l, 'coquille.projetEchanges')}`}
              // Changer de projet libère le filtre d'agent : ses agents ne sont pas ceux d'un autre projet.
              onClick={() => onFiltre({ ...filtre, projet: filtre.projet === p.nom ? null : p.nom, agent: null })}
            >
              <FolderGit2 className={`ic teinte--t${teinteProjet(p.nom)}`} size={15} />
              <span className="rail-boite__libelle rail-boite__libelle--mono">{p.nom}</span>
              {p.nouveaux > 0 && <span className="point-rond attente" title={tp(l, p.nouveaux, 'coquille.projetNouveaux')} />}
              <span className="compteur">{p.messages}</span>
            </button>
          ))}
          {activable && <ConnecterProjet onConnecter={onActiver} onChoisir={onChoisir} onInviter={onInviter} />}
          {activable && <InviterAgent projets={projets.map((p) => p.nom)} projetCourant={filtre.projet} onInviter={onInviter} />}
        </div>
      )}

      {!activable && <CreerBoite motif={motifCreation} onCreer={onCreer} onChoisir={onChoisir} />}

      <div className="rail__section">
        <span className="eyebrow">{t(l, 'coquille.agents')}</span>
        {groupes.map((g) => (
          <div key={g.projet ?? '·commun'} className="rail-groupe">
            <div className="rail-groupe__tete">
              {g.projet === null ? <EtiquetteProjet projet={null} avecIcone /> : (
                <button
                  type="button"
                  className="rail-groupe__projet"
                  title={filtre.projet === g.projet
                    ? t(l, 'coquille.voirTousProjets')
                    : t(l, 'coquille.voirProjetSeul', { projet: g.projet })}
                  onClick={() => onFiltre({ ...filtre, projet: filtre.projet === g.projet ? null : g.projet, agent: null })}
                >
                  <EtiquetteProjet projet={g.projet} avecIcone actif={filtre.projet === g.projet} />
                </button>
              )}
              <span className="vide" />
              <span className="compteur">{g.agents.length}</span>
            </div>
            {g.agents.length === 0 && (
              <span className="rail-groupe__vide">{t(l, 'coquille.groupeVide')}</span>
            )}
            {g.agents.map((a) => <LigneAgent key={a.nom} agent={a} filtre={filtre} onFiltre={onFiltre} aujourdhui={aujourdhui} />)}
          </div>
        ))}
      </div>

      <CePoste source={source} onPoste={onPoste} onPreparer={onPreparer} onEteindre={onEteindre}
        onOuvrirBoite={onOuvrirBoite} onChoisir={onChoisir} />

      <div className="rail__releve">
        <span className="eyebrow">{t(l, 'coquille.releve')}</span>
        <span className="rail__releve-texte">{t(l, 'coquille.releveExplication')}</span>
        <span className="rail__releve-constat">
          {derniereReleve
            ? t(l, 'coquille.releveDerniere', { heure: heure(derniereReleve, l), constat: libelleConstat(l, constat) })
            : t(l, 'coquille.relevePremiere')}
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
  const l = utiliseLangue();
  const actif = filtre.agent === a.nom;
  const quand = a.dernierEnvoi
    ? (cleJour(a.dernierEnvoi) === aujourdhui ? heure(a.dernierEnvoi, l) : horodatage(a.dernierEnvoi, l).slice(0, 5))
    : null;
  const dernier = quand ? t(l, 'coquille.agentDernier', { quand }) : t(l, 'coquille.agentSilencieux');
  const attente = a.attenteDepuis ? anciennete(a.attenteDepuis, new Date(), l) : null;
  const fiche = [
    a.nom,
    [a.hote, a.machine].filter(Boolean).join(' · '),
    a.role,
    tp(l, a.envois, 'coquille.agentEnvois'),
    a.contacts.length ? t(l, 'coquille.agentCarnet', { carnet: a.contacts.map((c) => `${c.alias} → ${c.adresses.join(', ')}`).join(' ; ') }) : '',
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
            <span className="rail-agent__attente"
              title={attente ? t(l, 'coquille.agentAttenteDepuis', { anciennete: attente }) : undefined}>
              {tp(l, a.enAttente, 'coquille.agentEnAttente')}{attente ? ` ${attente}` : ''}
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
