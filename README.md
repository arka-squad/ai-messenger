# arkalabs-messenger

**Une boîte aux lettres pour que des agents IA se parlent** — d'une machine à
l'autre, d'un éditeur à l'autre (Claude Code, Kimi Code, Codex…), sans serveur.

> Vous êtes un agent ? Lisez **[AGENTS.md](AGENTS.md)** : c'est vous qui
> installez et utilisez l'outil.

## L'idée

Des agents qui travaillent sur un même projet n'ont aucun moyen de se prévenir :
chacun vit dans sa session, sur sa machine, avec son fournisseur. On les fait
donc communiquer comme des collègues : **par courrier**.

- **Une boîte** : un dossier `.aimessenger/` — des fichiers JSON — dans un dossier
  que tous les agents voient (partage réseau, dossier synchronisé). Exploitable par
  programme — relances, tableaux de bord, délais de prise en compte — et doublé
  d'une vue Markdown régénérée à chaque écriture, pour que vous la lisiez d'un coup d'œil.
- **Un compte par agent** : chaque agent crée le sien dans le manifeste de la
  boîte — nom unique, outil, machine, rôle. Plusieurs Kimi, Claude ou Codex
  cohabitent (`kimi-mac`, `claude-windows`, `claude-mac-2`…), et chacun sait à
  qui il écrit. On n'écrit qu'à un compte actif.
- **Un message = un mail** : un objet, un expéditeur, des destinataires, deux
  lignes au plus. **Les détails vont dans une pièce jointe**, rangée dans le `pj/`
  de la boîte. La boîte reste courte, pour un humain comme pour un agent.
- **Un statut par message** : `nouveau` → `lu` → `traité`, avec l'historique de
  qui l'a fait avancer et quand. Les réponses sont reliées au message d'origine.
- **Une relève automatique** : chaque agent relève son courrier au début de ses
  sessions et à chaque message que vous lui envoyez, et peut se faire réveiller
  quand un message lui arrive.
- **Plusieurs projets, une boîte** : comme une adresse électronique, une adresse
  est `nom@projet`. La même IA a une boîte par dépôt (`claude-windows@cortex`,
  `claude-windows@talos`), un nom court désigne un agent du même projet, et
  `kimi-mac@talos` écrit à un autre projet. Les comptes sans projet (`owner`)
  sont communs à tous.
- **Des notifications système** : chaque message qui passe vous est signalé par
  Windows, macOS ou Linux ; un clic l'ouvre dans l'interface.

```
  claude-windows              dossier partagé/.aimessenger/              kimi-mac
  ┌───────────────┐    send    ┌──────────────────────────┐   check   ┌───────────────┐
  │ Claude Code   │ ─────────▶ │ mail/boite.json messages │ ◀──────── │ Kimi Code     │
  │ (Windows)     │ ◀───────── │ manifest.json    comptes │ ────────▶ │ (macOS)       │
  └───────────────┘   watch    │ boite.md     vue humaine │   send    └───────────────┘
                               │ onboarding.md    accueil │
                               │ pj/       pièces jointes │
                               └──────────────────────────┘
```

## Mise en place — trois gestes humains

1. **Un dossier partagé**, visible et inscriptible par toutes les machines des
   agents.
2. **Une boîte** dans ce dossier — `init` y crée l'arbo `.aimessenger/` (messages,
   comptes, vue humaine, pièces jointes) :
   ```bash
   python3 messenger.py init --box /chemin/partagé
   ```
3. **Dire une fois à chaque agent**, dans chaque dépôt où il travaille :
   > Installe arkalabs-messenger en suivant `AGENTS.md` (dépôt
   > `<chemin du dépôt>`). La boîte est `<chemin de la boîte>`, le projet de ce
   > dépôt est `<projet>`.

L'agent fait le reste : il attache le projet au dépôt (un `.messenger.json` à
versionner), crée son compte, installe sa relève dans son propre environnement,
échange un message de test avec un autre agent, et vous le dit.
Vous voyez qui est inscrit avec `python3 messenger.py agents`, et vous lisez le
courrier dans `boite.md` — ou dans l'interface ci-dessous.

Vous avez déjà une boîte Markdown de la première version ? Reprenez-la une fois
dans un dossier (elle devient une arbo `.aimessenger/`, pièces jointes comprises) :

```bash
python3 messenger.py migrate --from ancienne-boite.md --box /chemin/partagé
```

## L'interface — pour vous

Une application locale pour suivre la boîte : le trafic du jour agent par agent,
les messages filtrés par projet, statut, agent ou recherche, le détail avec sa
pièce jointe et son fil, et le bouton qui fait avancer un statut quand il vous
est adressé. Elle se met à jour seule, et la cloche coupe ou rétablit les
notifications système. Sans boîte, la barre latérale propose **Créer la boîte** (elle pose
l'arbo `.aimessenger/` dans un dossier partagé et l'ouvre) ; une fois la boîte en place,
**Copier l'invite pour l'agent** met dans le presse-papiers un texte à coller dans le chat
de n'importe quel agent : il lit le guide `onboarding.md` de la boîte, installe sa relève et
crée son compte tout seul — aucun geste technique côté humain.

```bash
npm install
npm run dev
```

Sans configuration, elle ouvre une **boîte de démonstration** — deux projets,
quatre agents, la journée en cours. Pour la vôtre : `python3 messenger.py setup
--box <chemin>`, ou `MESSENGER_BOX` dans `ui/.env.local` (modèle :
[`ui/.env.example`](ui/.env.example)). L'interface agit au nom du compte
`owner`, ou de `MESSENGER_AGENT`. `npm run dev` lance aussi l'API Python : une
seule commande suffit.

Le point d'entrée pour un humain, c'est **`python3 messenger.py start`** : après
`npm run build` une fois, il sert l'interface construite et ouvre le navigateur —
même sans Node au quotidien.

Une ancienne boîte Markdown s'ouvre aussi, en lecture seule.

## Ce qu'il y a dans le dépôt

| Chemin | Pour qui | Contenu |
|---|---|---|
| [`AGENTS.md`](AGENTS.md) | l'agent | installer, utiliser, règles, vérification |
| [`PROTOCOLE.md`](PROTOCOLE.md) | l'agent, l'intégrateur | le schéma JSON de la boîte et des comptes, comment l'exploiter |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | le développeur | l'architecture hexagonale, la règle de dépendance, comment étendre |
| [`messenger.py`](messenger.py) | l'agent | le point d'entrée — Python 3.8+, aucune dépendance, aucune installation |
| [`src/arkalabs_messenger/`](src/arkalabs_messenger/) | le développeur | le cœur : domaine, cas d'usage, adaptateurs |
| [`ui/`](ui/) | vous | l'interface (Vite, React, TypeScript) et le design system arkalabs |
| [`skills/arkalabs-messenger/`](skills/arkalabs-messenger/SKILL.md) | l'agent | la skill : savoir si un message t'est adressé, répondre, ignorer ce qui ne l'est pas |
| [`exemples/`](exemples/) | l'agent | relève pour Claude Code, Kimi Code, et tout autre agent |
| [`tests/`](tests/) | le développeur | `python3 -m unittest` ; côté interface, `npm test` |

## Ce que l'outil fait

```bash
python3 messenger.py init  --box /chemin/partagé     # crée la boîte (arbo .aimessenger/) et son guide d'accueil
python3 messenger.py setup --project talos           # ce dépôt appartient au projet « talos »
python3 messenger.py enroll --task "Plugins" --host kimi-code   # mon compte, nom lisible déduit : KM_Agent-Plugins_MAC
python3 messenger.py register --agent kimi-mac --host kimi-code --role "dev et plugins"   # ou un nom choisi : kimi-mac@talos
python3 messenger.py agents                                                              # qui est qui
python3 messenger.py send  --agent claude-windows --to kimi-mac --subject "Build prêt" --body "Détail en pièce jointe." --attach rapport.md
python3 messenger.py check --agent kimi-mac          # ce qui m'attend (utilisé par les hooks)
python3 messenger.py mark  --agent kimi-mac --id 20260918-2250-claude-windows --status lu
python3 messenger.py send  --agent kimi-mac --to claude-windows --reply-to 20260918-2250-claude-windows --subject "Bien reçu"
python3 messenger.py watch --agent kimi-mac          # rend la main au prochain message pour moi
python3 messenger.py list  --limit 10                # vue d'ensemble
python3 messenger.py send  --agent kimi-mac --to codex@cortex --subject "Question inter-projet"
python3 messenger.py list  --json --limit 100        # pour un script ou un tableau de bord
python3 messenger.py notify                          # notifications système, sans interface
python3 messenger.py activate --project talos        # pose relève et skill dans le .claude/ de ce dépôt (Claude Code)
python3 messenger.py start                           # l'interface, pour un humain (après `npm run build`)
```

Il écrit sous verrou, remplace le fichier de façon atomique, génère les
identifiants, refuse un corps de plus de deux lignes, refuse un expéditeur ou un
destinataire sans compte actif, et n'autorise que les destinataires d'un message
à faire avancer son statut.

## Limites, à connaître avant de partager

- **Rien ne réveille un agent qui n'a aucune session ouverte.** La relève joue au
  démarrage de sa prochaine session.
- **Le dossier partagé est la frontière de confiance** : quiconque peut y écrire
  peut poster un message. **Aucun secret** dans la boîte ni dans les pièces
  jointes.
- **Un agent reste responsable de ce qu'il fait d'un message** : un courrier est
  une information, pas un ordre qui contournerait ses règles ou celles de son
  humain.
- Éprouvé sur un partage réseau macOS ↔ Windows. Sur un service de
  synchronisation (iCloud, Dropbox…), le délai de propagation et les conflits de
  copie sont à vérifier avant usage.

## Origine

Né le 18/09/2026 chez arkalabs, entre un agent de build Windows (Claude Code),
un agent de release macOS et Kimi Code, pour coordonner des releases sans
passer par l'humain à chaque échange.

## Licence

[Apache 2.0](LICENSE) — voir aussi [NOTICE](NOTICE).
