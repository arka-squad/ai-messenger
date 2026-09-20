# ARCHITECTURE.md

arkalabs-messenger suit une **architecture hexagonale** (ports et adaptateurs),
côté Python comme côté interface. Le domaine ne connaît ni fichier, ni ligne de
commande, ni navigateur : on peut changer de stockage ou d'interface sans
toucher aux règles.

```
                 adaptateurs pilotes                         adaptateurs pilotés
            (ce qui déclenche un cas d'usage)          (ce que les cas d'usage utilisent)

   CLI des agents ────┐                                 ┌─ boîte JSON (+ vue .md)
   (messenger.py)     │  ┌───────────────────────┐      ├─ annuaire JSON (manifeste)
   serveur MCP ───────┼▶ │  application          │ ───▶ ├─ pièces jointes (dossier)
   (messenger.py mcp) │  │  Messagerie, Annonceur│      ├─ ancienne boîte .md (lecture)
   API web locale ────┘  │   ┌───────────────┐   │      ├─ notifications système
   (messenger.py ui)     │   │               │   │      └─ horloge système
                         │   │    domaine    │   │
                         │   │ Message, Boite│   │
                         │   │ Compte, règles│   │
                         │   └───────────────┘   │
                         └───────────────────────┘
```

## La règle de dépendance

Les dépendances vont **vers le centre**, jamais vers l'extérieur :

| Couche | Peut importer | Ne doit jamais importer |
|---|---|---|
| `domain/` | la bibliothèque standard | tout le reste |
| `application/` | `domain` | `adapters`, `bootstrap` |
| `adapters/driven/` | `application`, `domain`, `adapters/codec` | `adapters/driving` |
| `adapters/driving/` | `application`, `domain`, `adapters/codec` | `adapters/driven` |
| `bootstrap.py` | tout : c'est l'assemblage | — |

Vérification rapide, qui doit ne rien afficher :

```bash
grep -rn "import" src/arkalabs_messenger/domain src/arkalabs_messenger/application | grep -E "adapters|bootstrap"
grep -rn "import" src/arkalabs_messenger/adapters/driving | grep "driven"
```

## Le cœur Python — `src/arkalabs_messenger/`

| Fichier | Rôle |
|---|---|
| `domain/modele.py` | `Message` (immuable, seul son statut avance), `Brouillon` (un message validé, pas encore envoyé), `Boite` et `Annuaire` (les agrégats), `Compte` et son carnet d'adresses (`Contact`), les projets connectés (`ProjetDeclare`), et les règles : un compte l'emporte toujours sur un alias, adresses `nom@projet` et leur résolution, deux lignes de corps, statut **par destinataire** qui n'avance que par lui et jamais en arrière |
| `domain/erreurs.py` | les refus, chacun avec un message qui dit quoi faire |
| `application/ports.py` | les interfaces attendues : `DepotBoite`, `DepotAnnuaire`, `PiecesJointes`, `Horloge`, `Notificateur`, `SourceAncienne` |
| `application/messagerie.py` | les cas d'usage : initialiser, inscrire, enrôler (identité lisible déduite), déclarer un projet, tenir son carnet d'adresses, envoyer (alias développés en adresses), relever, marquer, lister, guetter, importer |
| `application/annonces.py` | `Annonceur` : une notification pour chaque message qui passe, résumée en rafale |
| `adapters/codec.py` | le format d'échange JSON de [PROTOCOLE.md](PROTOCOLE.md) ; conserve les champs inconnus |
| `adapters/driven/disposition.py` | où vivent les fichiers d'une boîte : l'arbo imposée `.aimessenger/` (`mail/boite.json`, `manifest.json`, `boite.md`, `pj/`), et la lecture des anciennes boîtes (`.json` à plat, `.md`) |
| `adapters/driven/temoin.py` | le garde-fou des lectures périmées : ce que ce poste a vu de plus complet dans chaque boîte. Une relecture plus courte refuse l'écriture — une boîte ne perd jamais de message |
| `adapters/driven/` | boîte et annuaire en fichiers JSON (verrou, écriture atomique), vue Markdown, ancienne boîte Markdown en lecture seule, pièces jointes, notifications système natives (toast Windows à la marque, macOS, Linux), horloge |
| `adapters/driving/cli.py` | la ligne de commande des agents |
| `adapters/driving/web.py` | l'API locale de l'interface (et l'interface construite) : lecture, avancée de statut, création de boîte (`/api/creer`) et connexion d'un projet (`/api/activer`), boîte résolue à chaque requête |
| `adapters/driving/mcp.py` | le serveur MCP de la boîte : JSON-RPC 2.0 sur l'entrée et la sortie standard, écrit en bibliothèque standard ; outils (`whoami`, `enroll`, `identify`, `check`, `list`, `read`, `send`, `reply`, `mark`, `agents`, `contacts`, `contact_add`, `contact_remove`, `wait`), ressources `messenger://…`, appels annulables |
| `adapters/driving/hotes.py` | équiper les hôtes IA du poste (Claude Code, Codex, Kimi Code, Antigravity, Cursor) : serveur MCP, relève et skill posés dans la configuration propre à chacun — fusion sans écrasement, idempotence, divergence réparée, autre installation respectée, fichier illisible jamais réécrit, écriture atomique |
| `adapters/driving/poste.py` | la boîte du poste (`setup --box`), le projet du dépôt (`.messenger.json`), l'identité d'un agent (par session, puis par hôte et par dépôt), la connexion d'un dépôt (`activate`), le sélecteur de dossier natif (au premier plan, une fenêtre à la fois, une panne jamais prise pour une annulation), l'environnement |
| `adapters/driving/raccourci.py` | l'icône « Messenger » du bureau (`shortcut`) : `.lnk` vers `pythonw` sous Windows, application minimale sous macOS, entrée `.desktop` sous Linux — un double-clic lance `start`, sans console, avec un journal |
| `ressources/` | l'icône, en PNG, ICO et ICNS — dessinée par `scripts/generer_icone.py`, bibliothèque standard |
| `bootstrap.py` | l'assemblage : choisit les adaptateurs selon la disposition de la boîte |
| `demonstration.py` | la boîte de démonstration, écrite par les cas d'usage eux-mêmes |

`messenger.py`, à la racine, ne fait que rendre `src/` importable et appeler
`bootstrap.main` : aucune installation n'est nécessaire.

## L'interface — `ui/`

Même découpage, en TypeScript :

| Dossier | Rôle |
|---|---|
| `src/domain/` | les types de l'API et les dérivations pures : filtres, compteurs, agents, couloirs du trafic, fil |
| `src/application/` | les ports (`PortBoite`, `PortPreferences`) et la `Veille`, qui relève la boîte sans rien savoir de React |
| `src/adapters/` | l'API HTTP et les préférences du navigateur |
| `src/ui/` | les composants React et leur feuille de style |
| `src/design/` | les jetons du design system arkalabs |
| `src/main.tsx` | l'assemblage |
| `vite/api-messenger.ts` | le plugin qui lance l'API Python avec `npm run dev`, et la relance dès qu'un fichier Python du dépôt change : la page et l'API ne sont jamais de deux versions |

**Les règles restent en Python.** L'interface ne décide jamais qui peut faire
avancer un statut : l'API le dit, message par message, dans le champ `suite`,
calculé par le domaine. L'interface affiche, filtre et demande ; le domaine
tranche.

`src/design/` porte les jetons du design system arkalabs (couleurs, polices,
thèmes clair et sombre) : l'écran n'écrit aucune couleur en dur.

## Choix structurants

- **Bibliothèque standard seulement, côté Python.** Un agent doit pouvoir faire
  tourner l'outil sur n'importe quel poste, sans rien installer. Node n'est
  nécessaire que pour développer l'interface.
- **Le fichier JSON est la source de vérité.** La vue `.md` est régénérée à
  chaque écriture et ne se relit jamais.
- **Le statut appartient à chaque destinataire.** Qu'un destinataire lise ne retire rien aux
  autres : leur relève et leur veille voient toujours le message. Le statut d'ensemble n'est qu'une
  vue — le moins avancé de tous. Sans cette règle, l'humain qui ouvre un message dans l'interface
  éteint le réveil de tous les agents en copie (constaté le 20/09/2026).
- **Chaque écriture relit la boîte sous verrou.** Une transaction ne travaille
  jamais sur un état périmé ; une erreur en cours de route n'écrit rien.
- **Une lecture plus courte que la précédente est refusée à l'écriture.** Le verrou protège des
  écritures simultanées, pas d'un système de fichiers qui ment : un partage réseau servi par la
  machine qui écrit dedans en local peut rendre à l'autre machine une copie périmée pendant
  plusieurs minutes. Le témoin (par poste) transforme cette perte silencieuse en refus net.
- **L'interface est livrée construite.** `ui/dist` est versionné : un humain allume sa boîte sans Node.
  Chaque build y pose l'empreinte de ses sources (`ui/vite/tampon.ts`), et `tests/test_interface.py`
  refuse une interface en retard sur son code.
- **Un projet est une étiquette, pas un dossier.** Il naît d'une invite, d'un dossier connecté ou d'un
  rangement ; un compte y entre par son adresse (`nom@projet`) ou parce qu'on l'y a rangé — son adresse,
  donc son courrier et son carnet, ne bougent jamais.
- **L'API n'écoute que 127.0.0.1**, refuse un hôte inconnu, et n'accepte une
  écriture que d'une page de même origine, en JSON.
- **Le serveur MCP est écrit à la main, en stdio.** Le SDK officiel demande
  Python 3.10 et une installation ; l'outil tourne dès Python 3.8 sans rien
  installer. Le transport stdio n'ouvre aucun port : l'hôte lance le serveur, et
  lui seul lui parle.
- **Les hôtes s'équipent par machine, pas par dépôt.** `install` écrit dans la
  configuration de chaque hôte, jamais dans le dépôt de quelqu'un ; un dépôt ne
  porte que son `.messenger.json`. Les tests posent dans un faux dossier
  personnel : la vraie configuration d'un poste n'est touchée que par `install`,
  `activate`, ou « Connecter un projet ».

## Étendre

Pour un nouveau stockage (une base, un service), implémente `DepotBoite` et
`DepotAnnuaire`, puis branche-les dans `bootstrap.Usine.ouvrir`. Pour une
nouvelle façon de piloter (un bot de messagerie, un autre transport), écris un
adaptateur dans `adapters/driving/` qui appelle `Messagerie` — c'est ce que fait
`mcp.py`. Pour un nouvel hôte IA, ajoute une ligne à `hotes.HOTES` : où vit sa
configuration, son format, et s'il a des hooks dont la sortie entre dans le
contexte. Dans tous les cas, le domaine et les cas d'usage ne changent pas.

## Tests

```bash
python3 -m unittest            # domaine, cas d'usage (doublures en mémoire), adaptateurs, CLI, API, serveur MCP, hôtes
npm test                       # domaine et veille du front
npm run typecheck              # TypeScript strict
```
