/**
 * L'interface construite est **livrée avec l'outil** (`ui/dist` est versionné) : un humain ouvre sa boîte
 * sans Node ni `npm run build`. Pour qu'elle ne soit jamais en retard sur son code, chaque build y pose
 * un tampon — l'empreinte des sources — que `tests/test_interface.py` recalcule et compare.
 *
 * L'empreinte : SHA-256 de `chemin \0 contenu \0` pour `index.html` et chaque fichier de `src/` hors tests,
 * chemins relatifs à `ui/` avec des `/`, triés, fins de ligne ramenées à `\n`.
 */
import { createHash } from 'node:crypto';
import { readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { join, relative, sep } from 'node:path';
import type { Plugin } from 'vite';

export function empreinteDesSources(racine: string): string {
  const fichiers = ['index.html', ...lister(join(racine, 'src')).map((f) => relative(racine, f).split(sep).join('/'))]
    .filter((f) => !f.endsWith('.test.ts'))
    .sort();
  const hache = createHash('sha256');
  for (const f of fichiers) {
    hache.update(f, 'utf8');
    hache.update('\0');
    hache.update(readFileSync(join(racine, f), 'utf8').replace(/\r\n/g, '\n'), 'utf8');
    hache.update('\0');
  }
  return hache.digest('hex');
}

function lister(dossier: string): string[] {
  return readdirSync(dossier, { withFileTypes: true }).flatMap((e) =>
    e.isDirectory() ? lister(join(dossier, e.name)) : [join(dossier, e.name)]);
}

export function tamponDeBuild(racine: string): Plugin {
  let sortie = join(racine, 'dist');
  return {
    name: 'arkalabs-messenger:tampon',
    apply: 'build',
    configResolved(config) {
      sortie = join(config.root, config.build.outDir);
    },
    closeBundle() {
      writeFileSync(join(sortie, 'build.json'), `${JSON.stringify({ sources: empreinteDesSources(racine) }, null, 2)}\n`);
    },
  };
}
