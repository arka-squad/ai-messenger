/**
 * Plugin de développement : `npm run dev` lance l'API Python (`messenger.py ui --api`)
 * sur un port libre et la relaie sous /api et /pj. Une seule commande, un seul onglet.
 *
 * - L'API démarre quand Vite écoute : elle connaît alors l'adresse de l'interface, que
 *   les notifications système ouvrent au clic.
 * - Si l'API ne tourne pas, /api et /pj répondent la vraie raison, pas un 502 muet.
 * - Les écritures restent protégées : l'origine n'est réécrite vers l'API que pour une
 *   requête venue de cette page elle-même ; toute autre origine est retirée, et l'API refuse.
 */
import { type ChildProcess, spawn, spawnSync } from 'node:child_process';
import { createServer } from 'node:net';
import { join } from 'node:path';
import type { Logger, Plugin, ProxyOptions } from 'vite';

export interface OptionsApi {
  /** Racine du dépôt, où se trouve messenger.py. */
  depot: string;
  /** Chemin de la boîte ; sinon MESSENGER_BOX, sinon `setup`, sinon la démonstration du dépôt. */
  boite?: string | undefined;
  /** Compte au nom duquel l'interface fait avancer les statuts (défaut : owner). */
  agent?: string | undefined;
  /** Interpréteur Python ; sinon python3, python ou py selon le système. */
  python?: string | undefined;
}

export function apiMessenger(options: OptionsApi): Plugin {
  let port = 0;

  return {
    name: 'arkalabs-messenger:api',
    apply: 'serve',

    async config() {
      port = await portLibre();
      const cible = `http://127.0.0.1:${port}`;
      return { server: { proxy: { '/api': relais(cible, true), '/pj': relais(cible, false) } } };
    },

    configureServer(serveur) {
      const api = new ApiPython(options, port, serveur.config.logger);
      serveur.middlewares.use((requete, reponse, suite) => {
        const url = requete.url ?? '';
        if (!api.panne || !(url.startsWith('/api/') || url.startsWith('/pj/'))) return suite();
        reponse.statusCode = 503;
        reponse.setHeader('Content-Type', 'application/json; charset=utf-8');
        reponse.end(JSON.stringify({ erreur: api.panne }));
      });

      const http = serveur.httpServer;
      if (!http) {
        api.demarrer(null);
        return;
      }
      http.once('listening', () => {
        const adresse = http.address();
        api.demarrer(typeof adresse === 'object' && adresse ? `http://127.0.0.1:${adresse.port}/` : null);
      });
      http.once('close', () => api.arreter());
      process.once('exit', () => api.arreter());
    },
  };
}

/** Le processus de l'API Python, son journal et la raison de son absence. */
class ApiPython {
  /** Pourquoi l'API ne tourne pas ; null tant qu'elle tourne. */
  panne: string | null = null;
  readonly #options: OptionsApi;
  readonly #port: number;
  readonly #journal: Logger;
  readonly #erreurs: string[] = [];
  #processus: ChildProcess | null = null;
  #arretVoulu = false;

  constructor(options: OptionsApi, port: number, journal: Logger) {
    this.#options = options;
    this.#port = port;
    this.#journal = journal;
  }

  demarrer(adresseInterface: string | null): void {
    let interpreteur: string;
    try {
      interpreteur = trouverPython(this.#options.python);
    } catch (e) {
      this.#tomber(e instanceof Error ? e.message : String(e));
      return;
    }
    const { depot, boite, agent } = this.#options;
    const args = [
      join(depot, 'messenger.py'), 'ui', '--api', '--no-browser', '--exit-with-parent', '--port', String(this.#port),
      ...(adresseInterface ? ['--link', adresseInterface] : []),
      ...(boite ? ['--box', boite] : []),
      ...(agent ? ['--agent', agent] : []),
    ];
    const processus = spawn(interpreteur, args, {
      cwd: depot,
      env: { ...process.env, PYTHONIOENCODING: 'utf-8', PYTHONUNBUFFERED: '1' },
      // L'entrée standard reste ouverte : sa fermeture, à la mort de Vite, arrête l'API.
      stdio: ['pipe', 'pipe', 'pipe'],
    });
    this.#processus = processus;
    processus.stdout?.on('data', (morceau: Buffer) => lignes(morceau).forEach((l) => this.#dire('info', l)));
    processus.stderr?.on('data', (morceau: Buffer) => lignes(morceau).forEach((l) => {
      this.#erreurs.push(l);
      this.#dire('error', l);
    }));
    processus.on('error', (e) => this.#tomber(`l'API Python n'a pas pu démarrer : ${e.message}`));
    processus.on('exit', (code) => {
      this.#processus = null;
      if (this.#arretVoulu) return;
      this.#tomber(`l'API Python s'est arrêtée : ${this.#erreurs.at(-1) ?? `code ${code ?? '?'}`}`);
      this.#dire('info', 'Corrige ui/.env.local (MESSENGER_BOX=…) : Vite redémarre tout seul.');
    });
  }

  arreter(): void {
    this.#arretVoulu = true;
    this.#processus?.kill();
  }

  #tomber(raison: string): void {
    this.panne = raison;
    this.#dire('error', raison);
  }

  #dire(niveau: 'info' | 'error', texte: string): void {
    this.#journal[niveau](`[messenger] ${texte}`, { timestamp: true });
  }
}

function lignes(morceau: Buffer): string[] {
  return morceau.toString('utf8').split(/\r?\n/).filter(Boolean);
}

function relais(cible: string, ecritures: boolean): ProxyOptions {
  return {
    target: cible,
    changeOrigin: true,
    configure: (proxy) => {
      if (!ecritures) return;
      proxy.on('proxyReq', (requeteApi, requete) => {
        const origine = requete.headers.origin;
        const memePage = origine !== undefined && origine === `http://${requete.headers.host}`;
        if (memePage) requeteApi.setHeader('origin', cible);
        else requeteApi.removeHeader('origin');
      });
    },
  };
}

function trouverPython(explicite: string | undefined): string {
  const candidats = explicite
    ? [explicite]
    : process.platform === 'win32' ? ['python', 'py', 'python3'] : ['python3', 'python'];
  for (const candidat of candidats) {
    const essai = spawnSync(candidat, ['-c', 'import sys; sys.exit(sys.version_info < (3, 8))'], { stdio: 'ignore' });
    if (essai.status === 0) return candidat;
  }
  throw new Error('Python 3.8 ou plus est introuvable : installe-le, ou indique-le dans MESSENGER_PYTHON.');
}

function portLibre(): Promise<number> {
  return new Promise((resoudre, rejeter) => {
    const sonde = createServer();
    sonde.unref();
    sonde.on('error', rejeter);
    sonde.listen(0, '127.0.0.1', () => {
      const adresse = sonde.address();
      const libre = typeof adresse === 'object' && adresse ? adresse.port : 0;
      sonde.close(() => resoudre(libre));
    });
  });
}
