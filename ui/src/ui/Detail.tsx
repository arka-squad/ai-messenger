import { ArrowRight, CheckCheck, ExternalLink, FileText, LoaderCircle, Lock } from 'lucide-react';
import { useState } from 'react';
import { fil, horodatage, instant, nomAffiche, projetsDe, titre } from '../domain/boite.ts';
import { type Message, STATUTS, type Statut } from '../domain/types.ts';
import { EtiquettesProjet } from './EtiquettesProjet.tsx';

interface Props {
  message: Message | null;
  tous: readonly Message[];
  /** Le projet affiché : ses adresses se lisent sans leur projet. */
  projet: string | null;
  /** Adresse → nom lisible, pour les comptes enrôlés. */
  affichages: ReadonlyMap<string, string>;
  lectureSeule: boolean;
  lienPieceJointe: (nom: string) => string;
  onMarquer: (id: string, statut: Statut) => Promise<void>;
  onChoix: (id: string) => void;
}

export function Detail({ message, ...reste }: Props) {
  return (
    <section className="detail" aria-label="Message">
      <div className="bandeau">
        <span className="eyebrow">Message</span>
        <span className="vide" />
        <span className="bandeau__info">{message?.id}</span>
      </div>
      {message
        ? <Contenu key={message.id} message={message} {...reste} />
        : <div className="detail__corps"><span className="detail__aucun">Aucun message à afficher.</span></div>}
    </section>
  );
}

function Contenu({ message: m, tous, projet, affichages, lectureSeule, lienPieceJointe, onMarquer, onChoix }: Props & { message: Message }) {
  const lies = fil(tous, m);
  const fuseau = Intl.DateTimeFormat().resolvedOptions().timeZone === 'Europe/Paris' ? ' Paris' : '';
  return (
    <div className="detail__corps rise">
      <div className="detail__bloc detail__bloc--serre">
        <span className="detail__objet">{titre(m)}</span>
        <div className="detail__adresse">
          <span className="adresse-de">{nomAffiche(m.de, affichages, projet)}</span>
          <ArrowRight className="ic" size={11} />
          <span className="adresse-a">{m.a.map((x) => nomAffiche(x, affichages, projet)).join(', ')}</span>
          <span className="detail__point-median">·</span>
          <span className="detail__date">{horodatage(instant(m))}{fuseau}</span>
          {/* La portée du message : tous les projets qu'il touche, la discussion inter-projet comprise. */}
          <EtiquettesProjet projets={projetsDe(m)} avecIcone />
        </div>
      </div>

      <div className="detail__bloc detail__bloc--serre">
        <span className="eyebrow">Statut</span>
        <Etapes message={m} />
        <Action message={m} lectureSeule={lectureSeule} onMarquer={onMarquer} />
      </div>

      <div className="detail__bloc">
        <span className="eyebrow">Corps</span>
        {m.corps.length
          ? m.corps.map((ligne, i) => <span key={i} className="detail__texte">{ligne}</span>)
          : <span className="detail__aucun">Aucun — l’objet suffit.</span>}
      </div>

      <div className="detail__bloc">
        <span className="eyebrow">Pièce jointe</span>
        {!m.pj ? (
          <span className="detail__aucun">Aucune — le corps suffit.</span>
        ) : m.pj_presente ? (
          <a className="piece" href={lienPieceJointe(m.pj)} target="_blank" rel="noopener noreferrer">
            <FileText className="ic" size={15} />
            <span className="piece__nom">{m.pj}</span>
            <ExternalLink className="ic" size={13} />
          </a>
        ) : (
          <span className="piece piece--absente" title="Ce fichier n’est pas dans le dossier de la boîte.">
            <FileText className="ic" size={15} />
            <span className="piece__nom">{m.pj}</span>
            <span className="detail__aucun">absente</span>
          </span>
        )}
      </div>

      <div className="detail__bloc">
        <span className="eyebrow">Fil</span>
        {lies.length ? lies.map((x) => (
          <button key={x.id} type="button" className="fil" onClick={() => onChoix(x.id)}>
            <span className={`fil__point fil__point--${x.statut}`} />
            <span className="fil__texte">
              <span className="fil__id">{x.id}</span>
              <span className="fil__objet">{titre(x)}</span>
            </span>
          </button>
        )) : <span className="detail__aucun">Pas de réponse à ce jour.</span>}
      </div>
    </div>
  );
}

/** nouveau — lu — traité, avec au survol qui a fait avancer le statut, et quand. */
function Etapes({ message: m }: { message: Message }) {
  const courant = STATUTS.indexOf(m.statut);
  return (
    <div className="etapes">
      {STATUTS.map((s, i) => {
        const trace = m.historique.find((t) => t.statut === s);
        const info = s === 'nouveau'
          ? `envoyé par ${m.de} le ${horodatage(instant(m))}`
          : trace ? `${s} par ${trace.par} le ${horodatage(new Date(trace.date))}` : undefined;
        const etat = i === courant ? ' etape--courante' : i < courant ? ' etape--passee' : '';
        return (
          <span key={s} className={`etape${etat}`} title={info}>
            <span className={`etape__point${i === courant && m.statut !== 'traité' ? ' pulse' : ''}`} />
            <span className="etape__libelle">{s}</span>
            <span className="etape__trait" />
          </span>
        );
      })}
    </div>
  );
}

function Action({ message: m, lectureSeule, onMarquer }: {
  message: Message;
  lectureSeule: boolean;
  onMarquer: (id: string, statut: Statut) => Promise<void>;
}) {
  const [enCours, setEnCours] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);

  const suite = m.suite;
  let libelle: string;
  let aide: string | undefined;
  let Icone = ArrowRight;
  if (lectureSeule) {
    [libelle, aide, Icone] = ['Lecture seule', 'Ancienne boîte Markdown : migre-la en JSON pour agir (messenger.py migrate).', Lock];
  } else if (m.statut === 'traité') {
    [libelle, Icone] = ['Statut terminal', CheckCheck];
  } else if (!suite) {
    [libelle, aide, Icone] = [`Réservé à ${m.a.join(', ')}`, 'Seul un destinataire fait avancer le statut.', Lock];
  } else {
    libelle = suite === 'lu' ? 'Marquer lu' : 'Marquer traité';
  }

  const agir = async () => {
    if (!suite || enCours) return;
    setEnCours(true);
    setErreur(null);
    try {
      await onMarquer(m.id, suite);
    } catch (e) {
      setErreur(e instanceof Error ? e.message : String(e));
    } finally {
      setEnCours(false);
    }
  };

  return (
    <>
      <button type="button" className="action" disabled={!suite || lectureSeule || enCours} title={aide} onClick={() => void agir()}>
        {enCours ? <LoaderCircle className="ic spin" size={13} /> : <Icone className="ic" size={13} />}
        <span className="action__libelle">{libelle}</span>
      </button>
      {erreur && <span className="detail__erreur" role="alert">{erreur}</span>}
    </>
  );
}
