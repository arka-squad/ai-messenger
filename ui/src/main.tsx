/** L'assemblage du front : choisit les adaptateurs et monte l'interface. */
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './design/styles.css';
import './ui/messenger.css';
import { ApiHttp } from './adapters/api-http.ts';
import { PreferencesLocales } from './adapters/navigateur.ts';
import { FournisseurLangue } from './application/langue.tsx';
import { Veille } from './application/veille.ts';
import { App } from './ui/App.tsx';

const veille = new Veille(new ApiHttp());
const preferences = new PreferencesLocales();
const racine = document.getElementById('app');
if (!racine) throw new Error('missing #app element in index.html');

createRoot(racine).render(
  <StrictMode>
    <FournisseurLangue preferences={preferences}>
      <App veille={veille} preferences={preferences} />
    </FournisseurLangue>
  </StrictMode>,
);
