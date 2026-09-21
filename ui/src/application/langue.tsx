/**
 * Interface language, held in a React context.
 *
 * Source of truth: this machine's `langue` preference (localStorage through the preferences port).
 * English is the default when no preference exists. The mailbox is never consulted: language is
 * personal, like the theme. `<html lang>` follows the selection.
 */
import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import type { PortPreferences } from './ports.ts';
import {
  LANGUE_DEFAUT,
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
    () => normaliseLangue(preferences.lire('langue')) ?? LANGUE_DEFAUT,
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

/** Header switch: displays the language the user can switch to. */
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
