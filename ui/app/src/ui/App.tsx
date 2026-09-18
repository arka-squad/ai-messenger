import { useCallback, useEffect, useMemo, useState, useSyncExternalStore } from 'react';
import type { PortPreferences } from '../application/ports.ts';
import type { Veille } from '../application/veille.ts';
import { FILTRE_INITIAL, type Filtre, agents, compter, filtrer, recents } from '../domain/boite.ts';
import type { Message, Statut } from '../domain/types.ts';
import { Detail } from './Detail.tsx';
import { Entete } from './Entete.tsx';
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
  const visibles = useMemo(() => filtrer(tous, filtre, compte), [tous, filtre, compte]);
  const compteurs = useMemo(() => compter(tous, compte), [tous, compte]);
  const listeAgents = useMemo(() => agents(etat?.comptes ?? [], tous), [etat, tous]);
  const choisi = (choix ? tous.find((m) => m.id === choix) : undefined) ?? visibles[0] ?? tous[0] ?? null;
  const idsVisibles = useMemo(() => visibles.map((m) => m.id), [visibles]);
  const arrivees = useMemo(() => new Set(v.arrivees.map((m) => m.id)), [v.arrivees]);
  const ordre = useMemo(() => {
    const noms = listeAgents.map((a) => a.nom);
    return [...noms, ...sansCompte(tous, noms)];
  }, [listeAgents, tous]);

  const marquer = useCallback((id: string, statut: Statut) => veille.marquer(id, statut), [veille]);

  useNavigationClavier(idsVisibles, choisi?.id ?? null, setChoix);

  const chargement = !etat && !v.erreur;
  return (
    <div className="app">
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
          agents={listeAgents}
          filtre={filtre}
          onFiltre={setFiltre}
          derniereReleve={v.derniereReleve}
          constat={v.constat}
        />
        <main className="zone">
          <Outils compteurs={compteurs} filtre={filtre} onFiltre={setFiltre} />
          <Trafic
            chargement={chargement}
            messages={tous}
            ordre={ordre}
            choisi={choisi}
            agentFiltre={filtre.agent}
            onChoix={setChoix}
          />
          <div className="panneaux">
            <Liste
              cle={`${filtre.classement}|${filtre.agent ?? ''}`}
              chargement={chargement}
              erreur={etat ? null : v.erreur}
              messages={visibles}
              arrivees={arrivees}
              total={tous.length}
              choisi={choisi?.id ?? null}
              onChoix={setChoix}
            />
            <Detail
              message={choisi}
              tous={tous}
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
