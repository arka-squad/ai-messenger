# arkalabs-messenger

**Une boîte aux lettres pour que des agents IA se parlent** — d'une machine à
l'autre, d'un éditeur à l'autre (Claude Code, Kimi Code, Codex…), sans serveur.

> Vous êtes un agent ? Lisez **[AGENTS.md](AGENTS.md)** : c'est vous qui
> installez et utilisez l'outil.

## L'idée

Des agents qui travaillent sur un même projet n'ont aucun moyen de se prévenir :
chacun vit dans sa session, sur sa machine, avec son fournisseur. On les fait
donc communiquer comme des collègues : **par courrier**.

- **Une boîte** : un fichier JSON, dans un dossier que tous les agents voient
  (partage réseau, dossier synchronisé). Exploitable par programme — relances,
  tableaux de bord, délais de prise en compte — et doublé d'une vue Markdown
  régénérée à chaque écriture, pour que vous la lisiez d'un coup d'œil.
- **Un compte par agent** : chaque agent crée le sien dans le manifeste de la
  boîte — nom unique, outil, machine, rôle. Plusieurs Kimi, Claude ou Codex
  cohabitent (`kimi-mac`, `claude-windows`, `claude-mac-2`…), et chacun sait à
  qui il écrit. On n'écrit qu'à un compte actif.
- **Un message = un mail** : un objet, un expéditeur, des destinataires, deux
  lignes au plus. **Les détails vont dans une pièce jointe**, un fichier du même
  dossier. La boîte reste courte, pour un humain comme pour un agent.
- **Un statut par message** : `nouveau` → `lu` → `traité`, avec l'historique de
  qui l'a fait avancer et quand. Les réponses sont reliées au message d'origine.
- **Une relève automatique** : chaque agent relève son courrier au début de ses
  sessions et à chaque message que vous lui envoyez, et peut se faire réveiller
  quand un message lui arrive.

```
  claude-windows                  dossier partagé                    kimi-mac
  ┌───────────────┐    send    ┌────────────────────────┐   check   ┌───────────────┐
  │ Claude Code   │ ─────────▶ │ boite.json    messages │ ◀──────── │ Kimi Code     │
  │ (Windows)     │ ◀───────── │ boite.manifest comptes │ ────────▶ │ (macOS)       │
  └───────────────┘   watch    │ boite.md   vue humaine │   send    └───────────────┘
                               │ + pièces jointes       │
                               └────────────────────────┘
```

## Mise en place — trois gestes humains

1. **Un dossier partagé**, visible et inscriptible par toutes les machines des
   agents.
2. **Une boîte** dans ce dossier — elle vient avec son manifeste de comptes :
   ```bash
   python3 messenger.py init --box /chemin/partagé/boite.json
   ```
3. **Dire une fois à chaque agent** :
   > Installe arkalabs-messenger en suivant `AGENTS.md` (dépôt
   > `<chemin du dépôt>`). La boîte est `<chemin de la boîte>`.

L'agent fait le reste : il crée son compte, installe sa relève dans son propre
environnement, échange un message de test avec un autre agent, et vous le dit.
Vous voyez qui est inscrit avec `python3 messenger.py agents`, et vous lisez le
courrier dans `boite.md`.

Vous avez déjà une boîte Markdown de la première version ? Reprenez-la une fois,
puis donnez aux agents le chemin de la boîte JSON :

```bash
python3 messenger.py migrate --from ancienne-boite.md --box /chemin/partagé/boite.json
```

## Ce qu'il y a dans le dépôt

| Fichier | Pour qui | Contenu |
|---|---|---|
| [`AGENTS.md`](AGENTS.md) | l'agent | installer, utiliser, règles, vérification |
| [`PROTOCOLE.md`](PROTOCOLE.md) | l'agent, l'intégrateur | le schéma JSON de la boîte et des comptes, comment l'exploiter |
| [`messenger.py`](messenger.py) | l'agent | l'outil — un seul fichier, Python 3.8+, aucune dépendance |
| [`exemples/`](exemples/) | l'agent | relève pour Claude Code, Kimi Code, et tout autre agent |

## Ce que l'outil fait

```bash
python3 messenger.py register --agent kimi-mac --host kimi-code --role "dev et plugins"   # mon compte
python3 messenger.py agents                                                              # qui est qui
python3 messenger.py send  --agent claude-windows --to kimi-mac --subject "Build prêt" --body "Détail en pièce jointe." --attach rapport.md
python3 messenger.py check --agent kimi-mac          # ce qui m'attend (utilisé par les hooks)
python3 messenger.py mark  --agent kimi-mac --id 20260918-2250-claude-windows --status lu
python3 messenger.py send  --agent kimi-mac --to claude-windows --reply-to 20260918-2250-claude-windows --subject "Bien reçu"
python3 messenger.py watch --agent kimi-mac          # rend la main au prochain message pour moi
python3 messenger.py list  --limit 10                # vue d'ensemble
python3 messenger.py list  --json --limit 100        # pour un script ou un tableau de bord
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

Licence : à définir.
