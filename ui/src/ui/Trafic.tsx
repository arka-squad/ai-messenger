import type { CSSProperties } from 'react';
import { utiliseLangue } from '../application/langue.tsx';
import { cleJour, couloirs, heure, instant, libelleJour, minutesDuJour, nomAffiche, titre } from '../domain/boite.ts';
import { t, tp } from '../domain/langue/index.ts';
import type { Message } from '../domain/types.ts';

interface Props {
  chargement: boolean;
  messages: readonly Message[];
  ordre: readonly string[];
  /** Le projet affiché : ses adresses se lisent sans leur projet. */
  projet: string | null;
  /** Adresse → nom lisible, pour les comptes enrôlés. */
  affichages: ReadonlyMap<string, string>;
  choisi: Message | null;
  agentFiltre: string | null;
  onChoix: (id: string) => void;
}

const GRADUATIONS = [0, 6, 12, 18, 24];
const HAUTEUR_COULOIR = 22;

/** Le trafic du jour du message choisi : un couloir par agent, un point par message. */
export function Trafic({ chargement, messages, ordre, projet, affichages, choisi, agentFiltre, onChoix }: Props) {
  const l = utiliseLangue();
  const maintenant = new Date();
  const jour = choisi ? cleJour(instant(choisi)) : cleJour(maintenant);
  const lignes = couloirs(messages, jour, ordre);
  const duJour = messages.filter((m) => cleJour(instant(m)) === jour).length;
  const largeurNom = Math.min(140, Math.max(54,
    Math.max(0, ...lignes.map((li) => nomAffiche(li.agent, affichages, projet).length)) * 6.2 + 2));
  const style = { '--couloir': `${largeurNom}px` } as CSSProperties;
  const paris = Intl.DateTimeFormat().resolvedOptions().timeZone === 'Europe/Paris';

  return (
    <section className="trafic" style={style} aria-label={t(l, 'message.trafic.aria')}>
      <div className="trafic__tete">
        <span className="trafic__titre">{t(l, 'message.trafic.titre', { jour: libelleJour(jour, undefined, l) })}</span>
        {!chargement && (
          <span className="trafic__legende">
            {tp(l, duJour, 'message.trafic.messages')} · {tp(l, lignes.length, 'message.trafic.agents')}
          </span>
        )}
        <span className="vide" />
        <span className="trafic__echelle">00:00 → 24:00 · {t(l, paris ? 'message.trafic.fuseau-paris' : 'message.trafic.fuseau-local')}</span>
      </div>

      {chargement ? (
        <div className="trafic__squelette">{[1, 2, 3, 4, 5].map((n) => <div key={n} className="sk" />)}</div>
      ) : lignes.length === 0 ? (
        <div className="trafic__vide">{t(l, 'message.trafic.vide')}</div>
      ) : (
        <div key={jour} className="trafic__couloirs">
          {lignes.map((li) => (
            <div key={li.agent} className="couloir">
              <span className={`couloir__nom${agentFiltre === li.agent ? ' couloir__nom--actif' : ''}`} title={li.agent}>
                {nomAffiche(li.agent, affichages, projet)}
              </span>
              <div className="couloir__piste">
                {li.points.map((p, i) => {
                  const estChoisi = p.message.id === choisi?.id;
                  const taille = estChoisi ? 11 : p.envoye ? 9 : 7;
                  return (
                    <button
                      key={p.message.id}
                      type="button"
                      className={`point dot-in ${p.envoye ? 'point--envoye' : 'point--recu'}${estChoisi ? ' point--choisi' : ''}`}
                      style={{ left: `${(p.minutes / 1440) * 100}%`, width: taille, height: taille, animationDelay: `${i * 45}ms` }}
                      title={t(l, 'message.trafic.point', { heure: heure(instant(p.message), l), de: p.message.de, destinataires: p.message.a.join(', '), titre: titre(p.message, l) })}
                      aria-label={titre(p.message, l)}
                      onClick={() => onChoix(p.message.id)}
                    />
                  );
                })}
              </div>
            </div>
          ))}
          <div className="trafic__graduations">
            <span className="trafic__graduations-marge" />
            <div className="trafic__graduations-piste">
              {GRADUATIONS.map((h, i) => (
                <span
                  key={h}
                  className="graduation"
                  style={{
                    left: `${(h / 24) * 100}%`,
                    transform: i === 0 ? 'none' : i === GRADUATIONS.length - 1 ? 'translateX(-100%)' : 'translateX(-50%)',
                  }}
                >
                  {String(h).padStart(2, '0')}:00
                </span>
              ))}
              {jour === cleJour(maintenant) && (
                <span
                  className="maintenant sweep"
                  style={{
                    left: `${(minutesDuJour(maintenant) / 1440) * 100}%`,
                    top: -(lignes.length * HAUTEUR_COULOIR - 14),
                    height: lignes.length * HAUTEUR_COULOIR - 10,
                  }}
                />
              )}
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
