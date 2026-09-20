import { useCallback, useEffect, useMemo, useState, useSyncExternalStore } from 'react';
import { utiliseLangue } from '../application/langue.tsx';
import type { PortPreferences } from '../application/ports.ts';
import type { Veille } from '../application/veille.ts';
import {
  FILTRE_INITIAL,
  type Filtre,
  affichagesDe,
  agents,
  compter,
  filtrer,
  groupesAgents,
  projets,
  projetsDesComptes,
  recents,
  toucheLeProjet,
} from '../domain/boite.ts';
import { t } from '../domain/langue/index.ts';
import type { Message, Statut } from '../domain/types.ts';
import { Detail } from './Detail.tsx';
import { Entete } from './Entete.tsx';
import { FicheAgent } from './FicheAgent.tsx';
import { Liste } from './Liste.tsx';
import { Outils } from './Outils.tsx';
import { Pied } from './Pied.tsx';
import { Rail } from './Rail.tsx';
import { Trafic } from './Trafic.tsx';

export type Theme = 'dark' | 'light';

interface Props {
  veille: Veille;
  preferences: PortPreferences;
}

export function App({ veille, preferences }: Props) {
  const v = useSyncExternalStore(veille.abonner, veille.lire);
  const l = utiliseLangue();
  const [theme, setTheme] = useState<Theme>(() => (preferences.lire('theme') === 'light' ? 'light' : 'dark'));
  const [filtre, setFiltreBrut] = useState<Filtre>(FILTRE_INITIAL);
  // Une notification système ouvre l'interface sur son message : /?message=<id>
  const [choix, setChoix] = useState<string | null>(() => new URLSearchParams(window.location.search).get('message'));
  // Un nouveau filtre choisit son premier message ; un clic (liste, trafic, fil) choisit librement.
  const setFiltre = useCallback((f: Filtre) => {
    setFiltreBrut(f);
    setChoix(null);
  }, []);

  useEffect(() => {
    veille.demarrer();
    return () => veille.arreter();
  }, [veille]);

  useEffect(() => {
    const clair = theme === 'light';
    document.documentElement.classList.toggle('theme-light', clair);
    document.body.classList.toggle('theme-light', clair);
    preferences.ecrire('theme', theme);
  }, [theme, preferences]);

  const etat = v.etat;
  const compte = etat?.compte ?? 'owner';
  const tous = useMemo(() => recents(etat?.messages ?? []), [etat]);
  // Le projet d'une adresse vient de son compte : un compte commun rangé dans un projet en fait partie.
  const projetDe = useMemo(() => projetsDesComptes(etat?.comptes ?? []), [etat]);
  const visibles = useMemo(() => filtrer(tous, filtre, compte, projetDe), [tous, filtre, compte, projetDe]);
  const compteurs = useMemo(() => compter(tous, compte), [tous, compte]);
  const listeAgents = useMemo(() => agents(etat?.comptes ?? [], tous, filtre.projet), [etat, tous, filtre.projet]);
  const listeProjets = useMemo(() => projets(etat?.projets ?? [], tous, etat?.comptes ?? []), [etat, tous]);
  // Rangés par projet ; sous un filtre de projet, il ne reste que le sien et les comptes communs.
  const groupes = useMemo(
    () => groupesAgents(listeAgents, filtre.projet ? [filtre.projet] : etat?.projets ?? []),
    [listeAgents, filtre.projet, etat],
  );
  const affichages = useMemo(() => affichagesDe(etat?.comptes ?? []), [etat]);
  // Quand il n'y a pas de boîte inscriptible : null → on propose « Créer la boîte » (cas démo/rien) ;
  // un texte → on explique pourquoi la création n'est pas la bonne action (boîte Markdown à migrer).
  const motifCreation = useMemo(() => {
    const s = etat?.source;
    if (!s || s.activable || s.demonstration) return null;
    if (s.lecture_seule) return t(l, 'coquille.creationLectureSeule');
    return t(l, 'coquille.creationIndisponible');
  }, [etat, l]);
  // Le trafic suit le projet choisi, pas les autres filtres : il montre la journée du projet.
  const duProjet = useMemo(
    () => (filtre.projet ? tous.filter((m) => toucheLeProjet(m, filtre.projet as string, projetDe)) : tous),
    [tous, filtre.projet, projetDe],
  );
  const choisi = (choix ? tous.find((m) => m.id === choix) : undefined) ?? visibles[0] ?? tous[0] ?? null;
  const idsVisibles = useMemo(() => visibles.map((m) => m.id), [visibles]);
  const arrivees = useMemo(() => new Set(v.arrivees.map((m) => m.id)), [v.arrivees]);
  const ordre = useMemo(() => {
    const noms = groupes.flatMap((g) => g.agents.map((a) => a.nom));  // les couloirs suivent les groupes du rail
    return [...noms, ...sansCompte(duProjet, noms)];
  }, [groupes, duProjet]);

  const marquer = useCallback((id: string, statut: Statut) => veille.marquer(id, statut), [veille]);

  useNavigationClavier(idsVisibles, choisi?.id ?? null, setChoix);

  const tousLesAgents = useMemo(() => agents(etat?.comptes ?? [], tous), [etat, tous]);
  const agentChoisi = filtre.agent ? tousLesAgents.find((a) => a.nom === filtre.agent) ?? null : null;
  // Les gestes passent par la veille, qui recharge ensuite : stables, pour ne pas relancer les effets.
  const inviter = useCallback((i: Parameters<Veille['inviter']>[0]) => veille.inviter(i), [veille]);
  const lirePoste = useCallback(() => veille.poste(), [veille]);
  const preparer = useCallback(() => veille.preparer(), [veille]);
  const eteindre = useCallback(() => veille.eteindre(), [veille]);

  const chargement = !etat && !v.erreur;
  if (v.eteinte) {
    return (
      <div className="app app--eteinte">
        <div className="eteinte">
          <span className="eteinte__titre">{t(l, 'coquille.eteinteTitre')}</span>
          <span className="eteinte__texte">
            {t(l, 'coquille.eteinteTexteAvant')}<b>Messenger</b>{t(l, 'coquille.eteinteTexteApres')}
          </span>
        </div>
      </div>
    );
  }
  return (
    <div className="app">
      {etat?.obsolete && (
        <div className="obsolete" role="status">
          La boîte allumée date d’avant cette page : ferme-la et relance-la (double-clic sur l’icône
          <b> Messenger</b>) pour retrouver toutes les fonctions.
        </div>
      )}
      <Entete
        nouveaux={compteurs.nouveau}
        veilleActive={v.active}
        onVeille={() => veille.basculer()}
        notifications={etat?.notifications ?? null}
        onNotifications={() => void veille.basculerNotifications()}
        theme={theme}
        onTheme={() => setTheme((t) => (t === 'light' ? 'dark' : 'light'))}
        compte={compte}
        source={etat?.source ?? null}
      />
      <div className="app__corps">
        <Rail
          compte={compte}
          compteurs={compteurs}
          projets={listeProjets}
          groupes={groupes}
          filtre={filtre}
          onFiltre={setFiltre}
          activable={etat?.source.activable ?? false}
          motifCreation={motifCreation}
          onInviter={inviter}
          onPoste={lirePoste}
          onPreparer={preparer}
          onEteindre={eteindre}
          onActiver={(dossier, projet) => veille.activer(dossier, projet)}
          onCreer={(dossier) => veille.creer(dossier)}
          onOuvrirBoite={(dossier) => veille.ouvrirBoite(dossier)}
          source={etat?.source ?? null}
          onChoisir={() => veille.choisirDossier()}
          derniereReleve={v.derniereReleve}
          constat={v.constat}
        />
        <main className="zone">
          <Outils compteurs={compteurs} filtre={filtre} onFiltre={setFiltre} />
          <Trafic
            chargement={chargement}
            messages={duProjet}
            ordre={ordre}
            projet={filtre.projet}
            affichages={affichages}
            choisi={choisi}
            agentFiltre={filtre.agent}
            onChoix={setChoix}
          />
          {agentChoisi && (
            <FicheAgent
              key={agentChoisi.nom}
              agent={agentChoisi}
              agents={tousLesAgents}
              projets={etat?.projets ?? []}
              modifiable={etat?.source.activable ?? false}
              onRattacher={(c, p) => veille.rattacher(c, p)}
              onNoterContact={(c, alias, adresses, note) => veille.noterContact(c, alias, adresses, note)}
              onRetirerContact={(c, alias) => veille.retirerContact(c, alias)}
              onInviter={inviter}
              onFusionner={async (c, dans) => {
                await veille.fusionner(c, dans);
                setFiltre({ ...filtre, agent: dans });  // la fiche passe au compte gardé
              }}
              onFermer={() => setFiltre({ ...filtre, agent: null })}
            />
          )}
          <div className="panneaux">
            <Liste
              cle={`${filtre.classement}|${filtre.agent ?? ''}`}
              chargement={chargement}
              erreur={etat ? null : v.erreur}
              messages={visibles}
              projet={filtre.projet}
              projetDe={projetDe}
              affichages={affichages}
              arrivees={arrivees}
              total={tous.length}
              choisi={choisi?.id ?? null}
              onChoix={setChoix}
            />
            <Detail
              message={choisi}
              tous={tous}
              projet={filtre.projet}
              projetDe={projetDe}
              affichages={affichages}
              lectureSeule={etat?.source.lecture_seule ?? true}
              lienPieceJointe={(nom) => veille.lienPieceJointe(nom)}
              onMarquer={marquer}
              onChoix={setChoix}
            />
          </div>
        </main>
      </div>
      <Pied compteurs={compteurs} source={etat?.source ?? null} />
    </div>
  );
}

/** Les expéditeurs ou destinataires qui n'ont pas de compte, pour qu'ils aient quand même un couloir. */
function sansCompte(messages: readonly Message[], connus: readonly string[]): string[] {
  const vus = new Set(connus);
  const autres: string[] = [];
  for (const m of messages) {
    for (const nom of [m.de, ...m.a]) {
      if (!vus.has(nom)) {
        vus.add(nom);
        autres.push(nom);
      }
    }
  }
  return autres;
}

/** ↑ ↓ (ou k j) parcourent la liste ; jamais pendant la saisie. */
function useNavigationClavier(ids: readonly string[], courant: string | null, choisir: (id: string) => void) {
  useEffect(() => {
    const surTouche = (e: KeyboardEvent) => {
      const cible = e.target as HTMLElement | null;
      if (cible && (cible.tagName === 'INPUT' || cible.isContentEditable)) return;
      const pas = e.key === 'ArrowDown' || e.key === 'j' ? 1 : e.key === 'ArrowUp' || e.key === 'k' ? -1 : 0;
      if (!pas || ids.length === 0) return;
      e.preventDefault();
      const i = courant ? ids.indexOf(courant) : -1;
      const suivant = ids[Math.min(ids.length - 1, Math.max(0, i + pas))];
      if (suivant) choisir(suivant);
    };
    window.addEventListener('keydown', surTouche);
    return () => window.removeEventListener('keydown', surTouche);
  }, [ids, courant, choisir]);
}
