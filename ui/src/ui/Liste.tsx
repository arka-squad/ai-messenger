import { ArrowRight, Paperclip } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { type ProjetDe, heure, instant, nomAffiche, projetsDe, titre } from '../domain/boite.ts';
import type { Message } from '../domain/types.ts';
import { EtiquettesProjet } from './EtiquettesProjet.tsx';
import { IconeStatut } from './IconeStatut.tsx';

interface Props {
  /** Change quand la boîte ou l'agent filtré change : la liste se remonte et s'anime. */
  cle: string;
  chargement: boolean;
  erreur: string | null;
  messages: readonly Message[];
  /** Le projet affiché : ses adresses se lisent sans leur projet. */
  projet: string | null;
  /** Le projet d'une adresse, d'après les comptes (un compte commun peut être rangé dans un projet). */
  projetDe: ProjetDe;
  /** Adresse → nom lisible, pour les comptes enrôlés. */
  affichages: ReadonlyMap<string, string>;
  /** Les messages arrivés à la dernière relève : ils s'animent en entrant. */
  arrivees: ReadonlySet<string>;
  total: number;
  choisi: string | null;
  onChoix: (id: string) => void;
}

export function Liste(p: Props) {
  return (
    <section className="liste" aria-label="Messages">
      <div className="bandeau">
        <span className="eyebrow">Messages</span>
        <span className="vide" />
        <span className="bandeau__info">{p.chargement || p.erreur ? '' : `${p.messages.length} / ${p.total}`}</span>
      </div>
      <div className="liste__defilement">
        {p.chargement ? <Squelette /> : p.erreur ? <Panne erreur={p.erreur} /> : <Lignes key={p.cle} {...p} />}
      </div>
    </section>
  );
}

function Lignes({ messages, projet, projetDe, affichages, arrivees, choisi, onChoix, total }: Props) {
  // Comme la maquette : les douze premières lignes entrent au montage, puis chaque arrivée.
  const [entrees] = useState(() => new Set(messages.slice(0, 12).map((m) => m.id)));
  const choisie = useRef<HTMLButtonElement | null>(null);
  useEffect(() => {
    choisie.current?.scrollIntoView({ block: 'nearest' });
  }, [choisi]);

  if (messages.length === 0) {
    return <div className="liste__vide">{total ? 'Aucun message ne correspond.' : 'La boîte est vide.'}</div>;
  }
  return (
    <div>
      {messages.map((m) => {
        const estChoisi = m.id === choisi;
        return (
          <button
            key={m.id}
            ref={estChoisi ? choisie : undefined}
            type="button"
            className={[
              'ligne',
              m.mien === 'nouveau' ? 'ligne--nouveau' : '',
              estChoisi ? 'ligne--choisie' : '',
              entrees.has(m.id) || arrivees.has(m.id) ? 'drop' : '',
            ].filter(Boolean).join(' ')}
            aria-current={estChoisi}
            onClick={() => onChoix(m.id)}
          >
            <span className="ligne__tete">
              <span className="ligne__heure">{heure(instant(m))}</span>
              <span className="adresse-de">{nomAffiche(m.de, affichages, projet)}</span>
              <ArrowRight className="ic" size={11} />
              <span className="adresse-a">{m.a.map((x) => nomAffiche(x, affichages, projet)).join(', ')}</span>
              <span className="vide" />
              {/* Chaque ligne dit à quel projet elle appartient ; celui qu'on filtre est en plein. */}
              <EtiquettesProjet projets={projetsDe(m, projetDe)} filtre={projet} />
              {m.pj && <Paperclip className="ic" size={12} />}
              <IconeStatut statut={m.mien} />
            </span>
            <span className="ligne__objet">{titre(m)}</span>
          </button>
        );
      })}
    </div>
  );
}

function Squelette() {
  return (
    <div className="liste__squelette">
      {[1, 2, 3, 4, 5, 6, 7, 8].map((n) => (
        <div key={n}>
          <div className="sk" style={{ height: 10, width: '34%' }} />
          <div className="sk" style={{ height: 12, width: '78%' }} />
        </div>
      ))}
    </div>
  );
}

function Panne({ erreur }: { erreur: string }) {
  return (
    <div className="panne" role="alert">
      <span className="panne__titre">La boîte n’a pas pu être lue</span>
      <span className="panne__message">{erreur}</span>
      <ul className="panne__aide">
        <li>Indique la boîte : <code>MESSENGER_BOX</code> dans <code>ui/.env.local</code>, ou <code>python3 messenger.py setup --box &lt;chemin&gt;</code>.</li>
        <li>Le détail est dans le terminal où tourne <code>npm run dev</code>.</li>
      </ul>
    </div>
  );
}
