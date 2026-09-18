/**
 * Plugin de développement : `npm run dev` lance l'API Python (`messenger.py ui --api`)
 * sur un port libre et la relaie sous /api et /pj. Une seule commande, un seul onglet.
 *
 * Les écritures restent protégées : l'origine n'est réécrite vers l'API que pour une
 * requête venue de cette page elle-même ; toute autre origine est retirée, et l'API refuse.
 */
import { type ChildProcess, spawn, spawnSync } from 'node:child_process';
import { createServer } from 'node:net';
import { join } from 'node:path';
import type { Plugin, ProxyOptions } from 'vite';

export interface OptionsApi {
  /** Racine du dépôt, où se trouve messenger.py. */
  depot: string;
  /** Chemin de la boîte ; sinon MESSENGER_BOX, sinon la boîte mémorisée par `setup`. */
  boite?: string | undefined;
  /** Compte au nom duquel l'interface fait avancer les statuts (défaut : owner). */
  agent?: string | undefined;
  /** Interpréteur Python ; sinon python3, python ou py selon le système. */
  python?: string | undefined;
}

export function apiMessenger(options: OptionsApi): Plugin {
  let port = 0;
  let enfant: ChildProcess | null = null;

  return {
    name: 'arkalabs-messenger:api',
    apply: 'serve',

    async config() {
      port = await portLibre();
      const cible = `http://127.0.0.1:${port}`;
      return { server: { proxy: { '/api': relais(cible, true), '/pj': relais(cible, false) } } };
    },

    configureServer(serveur) {
      const journal = serveur.config.logger;
      const interpreteur = trouverPython(options.python);
      const args = [
        join(options.depot, 'messenger.py'), 'ui', '--api', '--no-browser', '--exit-with-parent',
        '--port', String(port),
        ...(options.boite ? ['--box', options.boite] : []),
        ...(options.agent ? ['--agent', options.agent] : []),
      ];
      enfant = spawn(interpreteur, args, {
        cwd: options.depot,
        env: { ...process.env, PYTHONIOENCODING: 'utf-8', PYTHONUNBUFFERED: '1' },
        // L'entrée standard reste ouverte : sa fermeture, à la mort de Vite, arrête l'API.
        stdio: ['pipe', 'pipe', 'pipe'],
      });
      const relayer = (niveau: 'info' | 'error') => (morceau: Buffer) => {
        for (const ligne of morceau.toString('utf8').split(/\r?\n/).filter(Boolean)) {
          journal[niveau](`[messenger] ${ligne}`, { timestamp: true });
        }
      };
      enfant.stdout?.on('data', relayer('info'));
      enfant.stderr?.on('data', relayer('error'));
      enfant.on('exit', (code) => {
        if (code) journal.error(`[messenger] l'API s'est arrêtée (code ${code}) — voir le message ci-dessus.`);
        enfant = null;
      });

      const arreter = () => enfant?.kill();
      serveur.httpServer?.once('close', arreter);
      process.once('exit', arreter);
    },
  };
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
