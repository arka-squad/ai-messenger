/**
 * Plugin de développement : `npm run dev` lance l'API Python (`messenger.py ui --api`)
 * sur un port libre et la relaie sous /api et /pj. Une seule commande, un seul onglet.
 *
 * - L'API démarre quand Vite écoute : elle connaît alors l'adresse de l'interface, que
 *   les notifications système ouvrent au clic.
 * - Si l'API ne tourne pas, /api et /pj répondent la vraie raison, pas un 502 muet.
 * - Vite recharge le front à chaud ; l'API, elle, garderait son ancien code jusqu'à la fin de la
 *   session. Elle redémarre donc dès qu'un fichier Python du dépôt change : la page et l'API ne
 *   peuvent plus être de deux versions différentes.
 * - Les écritures restent protégées : l'origine n'est réécrite vers l'API que pour une
 *   requête venue de cette page elle-même ; toute autre origine est retirée, et l'API refuse.
 */
import { type ChildProcess, spawn, spawnSync } from 'node:child_process';
import { connect, createServer } from 'node:net';
import { join, relative } from 'node:path';
import { type Logger, type Plugin, type ProxyOptions, normalizePath } from 'vite';

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

      // Le code Python du dépôt : `src/` et `messenger.py`. Un changement relance l'API (regroupés : un
      // `git pull` touche vingt fichiers d'un coup).
      const surveilles = [join(options.depot, 'src'), join(options.depot, 'messenger.py')];
      serveur.watcher.add(surveilles);
      const racines = surveilles.map((chemin) => normalizePath(chemin));
      let minuterie: ReturnType<typeof setTimeout> | null = null;
      const surChangement = (fichier: string) => {
        const chemin = normalizePath(fichier);
        if (!chemin.endsWith('.py') || !racines.some((r) => chemin === r || chemin.startsWith(`${r}/`))) return;
        if (minuterie) clearTimeout(minuterie);
        minuterie = setTimeout(() => api.relancer(normalizePath(relative(options.depot, fichier))), 300);
      };
      for (const evenement of ['add', 'change', 'unlink'] as const) serveur.watcher.on(evenement, surChangement);

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
  #adresseInterface: string | null = null;
  #arretVoulu = false;
  #relance = false;

  constructor(options: OptionsApi, port: number, journal: Logger) {
    this.#options = options;
    this.#port = port;
    this.#journal = journal;
  }

  demarrer(adresseInterface: string | null): void {
    this.#adresseInterface = adresseInterface;
    this.#erreurs.length = 0;
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
    // L'API n'écoute pas à l'instant où elle est lancée : tant que son port ne répond pas, on le dit.
    this.panne = "l'API Python démarre — un instant";
    void attendrePort(this.#port).then((pret) => {
      if (this.#processus === processus && pret) this.panne = null;
    });
    processus.on('exit', (code) => {
      if (this.#processus === processus) this.#processus = null;
      if (this.#arretVoulu || this.#relance) return;
      this.#tomber(`l'API Python s'est arrêtée : ${this.#erreurs.at(-1) ?? `code ${code ?? '?'}`}`);
      this.#dire('info', 'Corrige ui/.env.local (MESSENGER_BOX=…) : Vite redémarre tout seul.');
    });
  }

  /** Arrête l'API puis la relance avec le code à jour. Sans API en cours (elle était tombée), la lance. */
  relancer(fichier: string): void {
    if (this.#arretVoulu || this.#relance) return;
    this.#dire('info', `${fichier} a changé : l'API Python redémarre`);
    const processus = this.#processus;
    if (!processus) {
      this.demarrer(this.#adresseInterface);
      return;
    }
    this.#relance = true;
    this.panne = "l'API Python redémarre (code modifié) — un instant";
    processus.once('exit', () => {
      this.#relance = false;
      if (!this.#arretVoulu) this.demarrer(this.#adresseInterface);
    });
    processus.kill();
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

/** Attend que l'API écoute sur son port. Rend false si elle ne répond pas dans le délai. */
function attendrePort(port: number, delaiMs = 15000): Promise<boolean> {
  const fin = Date.now() + delaiMs;
  return new Promise((resoudre) => {
    const essayer = () => {
      const prise = connect({ port, host: '127.0.0.1' });
      prise.once('connect', () => {
        prise.destroy();
        resoudre(true);
      });
      prise.once('error', () => {
        prise.destroy();
        if (Date.now() > fin) resoudre(false);
        else setTimeout(essayer, 120);
      });
    };
    essayer();
  });
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
