/** L'assemblage du front : choisit les adaptateurs et monte l'interface. */
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import '../../messenger/styles.css';
import './ui/messenger.css';
import { ApiHttp } from './adapters/api-http.ts';
import { PreferencesLocales } from './adapters/navigateur.ts';
import { Veille } from './application/veille.ts';
import { App } from './ui/App.tsx';

const veille = new Veille(new ApiHttp());
const racine = document.getElementById('app');
if (!racine) throw new Error('élément #app absent de index.html');

createRoot(racine).render(
  <StrictMode>
    <App veille={veille} preferences={new PreferencesLocales()} />
  </StrictMode>,
);
