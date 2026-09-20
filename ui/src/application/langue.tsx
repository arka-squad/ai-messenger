/**
 * La langue de l'interface, tenue dans un contexte React.
 *
 * Source de vérité : la préférence `langue` de ce poste (localStorage via le port préférences) ;
 * à défaut, la langue du navigateur. La boîte n'est jamais consultée : la langue est un réglage
 * personnel, comme le thème. `<html lang>` suit le choix.
 */
import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import type { PortPreferences } from './ports.ts';
import {
  LANGUE_DEFAUT,
  langueDuNavigateur,
  normaliseLangue,
  type Langue,
} from '../domain/langue/index.ts';

interface ValeurLangue {
  langue: Langue;
  fixerLangue(langue: Langue): void;
}

const ContexteLangue = createContext<ValeurLangue>({ langue: LANGUE_DEFAUT, fixerLangue: () => undefined });

export function FournisseurLangue({ preferences, children }: { preferences: PortPreferences; children: ReactNode }) {
  const [langue, setLangue] = useState<Langue>(
    () => normaliseLangue(preferences.lire('langue')) ?? langueDuNavigateur(),
  );
  useEffect(() => {
    preferences.ecrire('langue', langue);
    document.documentElement.lang = langue;
  }, [langue, preferences]);
  return <ContexteLangue.Provider value={{ langue, fixerLangue: setLangue }}>{children}</ContexteLangue.Provider>;
}

export function utiliseLangue(): Langue {
  return useContext(ContexteLangue).langue;
}

/** Le commutateur visible de l'en-tête : affiche la langue visée, comme font FR/EN. */
export function CommutateurLangue() {
  const { langue, fixerLangue } = useContext(ContexteLangue);
  const autre: Langue = langue === 'fr' ? 'en' : 'fr';
  return (
    <button
      type="button"
      className="entete__langue"
      onClick={() => fixerLangue(autre)}
      title={langue === 'fr' ? 'Switch to English' : 'Passer en français'}
    >
      {autre.toUpperCase()}
    </button>
  );
}
