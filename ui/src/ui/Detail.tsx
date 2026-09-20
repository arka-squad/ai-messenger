import { ArrowRight, CheckCheck, ExternalLink, FileText, LoaderCircle, Lock } from 'lucide-react';
import { useState } from 'react';
import { utiliseLangue } from '../application/langue.tsx';
import { type ProjetDe, fil, horodatage, instant, projetsDe, statutPour, titre } from '../domain/boite.ts';
import { t } from '../domain/langue/index.ts';
import { type Message, STATUTS, type Statut } from '../domain/types.ts';
import { EtiquetteProjet, EtiquettesProjet } from './EtiquettesProjet.tsx';

interface Props {
  message: Message | null;
  tous: readonly Message[];
  /** Le projet affiché : ses adresses se lisent sans leur projet. */
  projet: string | null;
  /** Le projet d'une adresse, d'après les comptes (un compte commun peut être rangé dans un projet). */
  projetDe: ProjetDe;
  /** Adresse → nom lisible, pour les comptes enrôlés. */
  affichages: ReadonlyMap<string, string>;
  lectureSeule: boolean;
  lienPieceJointe: (nom: string) => string;
  onMarquer: (id: string, statut: Statut) => Promise<void>;
  onChoix: (id: string) => void;
}

/** Le libellé traduit de chaque statut : une clé par valeur protocole, jamais dérivée d'elle. */
const LIBELLES: Record<Statut, 'message.statut.nouveau' | 'message.statut.lu' | 'message.statut.traite'> = {
  nouveau: 'message.statut.nouveau',
  lu: 'message.statut.lu',
  traité: 'message.statut.traite',
};

export function Detail({ message, ...reste }: Props) {
  const l = utiliseLangue();
  return (
    <section className="detail" aria-label={t(l, 'message.detail.aria')}>
      <div className="bandeau">
        <span className="eyebrow">{t(l, 'message.detail.aria')}</span>
        <span className="vide" />
        <span className="bandeau__info">{message?.id}</span>
      </div>
      {message
        ? <Contenu key={message.id} message={message} {...reste} />
        : <div className="detail__corps"><span className="detail__aucun">{t(l, 'message.detail.aucun')}</span></div>}
    </section>
  );
}

function Contenu({ message: m, tous, projet, projetDe, affichages, lectureSeule, lienPieceJointe, onMarquer, onChoix }: Props & { message: Message }) {
  const l = utiliseLangue();
  const lies = fil(tous, m);
  const paris = Intl.DateTimeFormat().resolvedOptions().timeZone === 'Europe/Paris';
  return (
    <div className="detail__corps rise">
      <div className="detail__bloc detail__bloc--serre">
        {/* La portée du message, d'abord : tous les projets qu'il touche, la discussion inter-projet comprise. */}
        <div className="detail__portee">
          <EtiquettesProjet projets={projetsDe(m, projetDe)} avecIcone filtre={projet} />
          <span className="vide" />
          <span className="detail__date">{horodatage(instant(m), l)}{paris ? ` ${t(l, 'message.detail.fuseau')}` : ''}</span>
        </div>
        <span className="detail__objet">{titre(m, l)}</span>
        <div className="detail__correspondants">
          <span className="detail__sens">{t(l, 'message.detail.de')}</span>
          <Correspondant adresse={m.de} affichages={affichages} projetDe={projetDe} filtre={projet} emetteur />
          <span className="detail__sens">{t(l, 'message.detail.a')}</span>
          <div className="detail__destinataires">
            {/* Le statut est propre à chacun : la fiche dit qui a lu, et qui n'a pas encore. */}
            {m.a.map((x) => (
              <Correspondant key={x} adresse={x} affichages={affichages} projetDe={projetDe} filtre={projet}
                             statut={statutPour(m, x)} />
            ))}
          </div>
        </div>
      </div>

      <div className="detail__bloc detail__bloc--serre">
        <span className="eyebrow">{t(l, 'message.detail.statut')}</span>
        <Etapes message={m} />
        <Action message={m} lectureSeule={lectureSeule} onMarquer={onMarquer} />
      </div>

      <div className="detail__bloc">
        <span className="eyebrow">{t(l, 'message.detail.corps')}</span>
        {m.corps.length
          ? m.corps.map((ligne, i) => <span key={i} className="detail__texte">{ligne}</span>)
          : <span className="detail__aucun">{t(l, 'message.detail.corps-vide')}</span>}
      </div>

      <div className="detail__bloc">
        <span className="eyebrow">{t(l, 'message.detail.pj')}</span>
        {!m.pj ? (
          <span className="detail__aucun">{t(l, 'message.detail.pj-vide')}</span>
        ) : m.pj_presente ? (
          <a className="piece" href={lienPieceJointe(m.pj)} target="_blank" rel="noopener noreferrer">
            <FileText className="ic" size={15} />
            <span className="piece__nom">{m.pj}</span>
            <ExternalLink className="ic" size={13} />
          </a>
        ) : (
          <span className="piece piece--absente" title={t(l, 'message.detail.pj-absente-infobulle')}>
            <FileText className="ic" size={15} />
            <span className="piece__nom">{m.pj}</span>
            <span className="detail__aucun">{t(l, 'message.detail.pj-absente')}</span>
          </span>
        )}
      </div>

      <div className="detail__bloc">
        <span className="eyebrow">{t(l, 'message.detail.fil')}</span>
        {lies.length ? lies.map((x) => (
          <button key={x.id} type="button" className="fil" onClick={() => onChoix(x.id)}>
            <span className={`fil__point fil__point--${x.statut}`} />
            <span className="fil__texte">
              <span className="fil__id">{x.id}</span>
              <span className="fil__objet">{titre(x, l)}</span>
            </span>
          </button>
        )) : <span className="detail__aucun">{t(l, 'message.detail.fil-vide')}</span>}
      </div>
    </div>
  );
}

/** Un correspondant sur la fiche : son nom lisible, son adresse, et le projet auquel il appartient. */
function Correspondant({ adresse, affichages, projetDe, filtre, emetteur = false, statut = null }: {
  adresse: string;
  affichages: ReadonlyMap<string, string>;
  projetDe: ProjetDe;
  filtre: string | null;
  emetteur?: boolean;
  /** Où en est ce destinataire, s'il s'agit d'un destinataire. */
  statut?: Statut | null;
}) {
  const l = utiliseLangue();
  const nom = adresse.split('@')[0] ?? adresse;
  const affichage = affichages.get(adresse);
  const projet = projetDe(adresse);
  return (
    <span className="correspondant" title={adresse}>
      <span className={emetteur ? 'adresse-de' : 'adresse-a'}>{affichage ?? nom}</span>
      {affichage && <span className="correspondant__adresse">{nom}</span>}
      <EtiquetteProjet projet={projet} actif={projet !== null && projet === filtre} />
      {statut && <span className={`correspondant__statut statut--${statut}`}
                       title={statut === 'nouveau' ? t(l, 'message.detail.pas-lu') : t(l, 'message.detail.marque', { statut: t(l, LIBELLES[statut]) })}>{t(l, LIBELLES[statut])}</span>}
    </span>
  );
}

/** nouveau — lu — traité *pour le compte courant*, avec au survol qui a fait avancer le statut, et quand. */
function Etapes({ message: m }: { message: Message }) {
  const l = utiliseLangue();
  const courant = STATUTS.indexOf(m.mien);
  return (
    <div className="etapes">
      {STATUTS.map((s, i) => {
        const trace = m.historique.find((tr) => tr.statut === s);
        const info = s === 'nouveau'
          ? t(l, 'message.detail.envoye', { par: m.de, date: horodatage(instant(m), l) })
          : trace ? t(l, 'message.detail.statut-par', { statut: t(l, LIBELLES[s]), par: trace.par, date: horodatage(new Date(trace.date), l) }) : undefined;
        const etat = i === courant ? ' etape--courante' : i < courant ? ' etape--passee' : '';
        return (
          <span key={s} className={`etape${etat}`} title={info}>
            <span className={`etape__point${i === courant && m.mien !== 'traité' ? ' pulse' : ''}`} />
            <span className="etape__libelle">{t(l, LIBELLES[s])}</span>
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
  const l = utiliseLangue();
  const [enCours, setEnCours] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);

  const suite = m.suite;
  let libelle: string;
  let aide: string | undefined;
  let Icone = ArrowRight;
  if (lectureSeule) {
    [libelle, aide, Icone] = [t(l, 'message.action.lecture-seule'), t(l, 'message.action.lecture-seule-infobulle'), Lock];
  } else if (m.mien === 'traité') {
    [libelle, Icone] = [t(l, 'message.action.terminal'), CheckCheck];
  } else if (!suite) {
    [libelle, aide, Icone] = [t(l, 'message.action.reserve', { destinataires: m.a.join(', ') }), t(l, 'message.action.reserve-infobulle'), Lock];
  } else {
    libelle = suite === 'lu' ? t(l, 'message.action.marquer-lu') : t(l, 'message.action.marquer-traite');
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
