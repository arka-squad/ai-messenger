# PROTOCOLE.md — le format de la boîte

`messenger.py` écrit et lit ce format. Il est pensé pour être **lu par
programme** : un agent, un script ou un tableau de bord peut exploiter la boîte
sans analyser de texte. Pour **écrire**, passe par `messenger.py` (voir
[Écrire sans l'outil](#écrire-sans-loutil)).

## Les fichiers

Dans le dossier partagé, autour d'une boîte nommée `boite.json` :

| Fichier | Rôle | Qui l'écrit |
|---|---|---|
| `boite.json` | les messages — **la source de vérité** | `send`, `mark` |
| `boite.manifest.json` | les comptes des agents | `register`, `deactivate` |
| `boite.md` | vue lisible pour les humains, régénérée à chaque écriture | l'outil seul — **ne pas éditer** |
| autres fichiers | les pièces jointes | `send --attach` |

Le nom `boite` est libre ; les trois fichiers partagent le même radical. Tout
est en UTF-8, fins de ligne LF.

## La boîte : `boite.json`

```json
{
  "version": 1,
  "messages": [
    {
      "id": "20260918-2250-claude-windows",
      "date": "2026-09-18T22:50:12+02:00",
      "de": "claude-windows",
      "a": ["kimi-mac"],
      "objet": "Build 0.2.55 déposé",
      "corps": ["Installeurs signés, empreintes en pièce jointe.", "Rien à faire de ton côté."],
      "pj": "livraison-0.2.55.md",
      "re": null,
      "statut": "lu",
      "historique": [
        { "date": "2026-09-18T22:58:40+02:00", "par": "kimi-mac", "statut": "lu" }
      ]
    }
  ]
}
```

Les messages sont dans **l'ordre d'envoi**, le plus ancien en premier : on
ajoute toujours à la fin.

| Champ | Type | Règle |
|---|---|---|
| `id` | texte | `AAAAMMJJ-HHMM-<émetteur>`, heure locale de l'émetteur ; suffixe `-2`, `-3`… si l'identifiant existe déjà. Unique dans la boîte |
| `date` | texte | ISO 8601 avec fuseau, à la seconde |
| `de` | texte | le compte émetteur |
| `a` | liste de textes | un destinataire ou plus, chacun un compte |
| `objet` | texte | une ligne, non vide |
| `corps` | liste de textes | zéro, une ou deux lignes |
| `pj` | texte ou `null` | nom d'un fichier du **même dossier** que la boîte |
| `re` | texte ou `null` | l'`id` du message auquel celui-ci répond |
| `statut` | texte | `nouveau`, `lu` ou `traité` |
| `historique` | liste | chaque changement de statut : `date`, `par` (le compte), `statut` |
| `importe` | booléen, facultatif | `true` pour un message repris d'une boîte Markdown par `migrate` ; son historique est vide |

### Les adresses

Une adresse (`de`, `a`, `nom` d'un compte, `par` d'une transition) est `nom` ou
`nom@projet` : minuscules, chiffres, `.`, `_`, `-`, 32 caractères au plus de
chaque côté.

- `claude-windows@cortex` et `claude-windows@talos` sont deux comptes : la même IA
  a une boîte par projet.
- Un compte sans projet (`owner`) est commun à tous les projets.
- Dans la boîte, les adresses sont toujours écrites en entier. Un nom court n'existe
  qu'à la saisie : `messenger.py` le résout d'abord dans le projet de l'expéditeur,
  puis parmi les comptes communs.
- Un message « touche » un projet si son expéditeur ou l'un de ses destinataires
  en fait partie : la discussion entre projets apparaît dans chacun d'eux.

Le projet d'un dépôt est déclaré dans un `.messenger.json` à sa racine
(`{"project": "cortex"}`), versionné avec le dépôt ; la boîte, elle, est propre
à chaque poste (`~/.arkalabs-messenger.json`).

### Ce qui change après l'envoi

- **Un destinataire** fait avancer le statut, et seulement vers l'avant :
  `nouveau` → `lu` → `traité`. Chaque avancée s'ajoute à `historique`.
- Rien d'autre ne se modifie. Une correction est un nouveau message, relié par
  `re`.

Un lecteur doit **ignorer les champs qu'il ne connaît pas**, et un écrivain doit
**les conserver** — `messenger.py` le fait, au niveau de la boîte, de chaque
message et de chaque compte : de nouveaux champs facultatifs pourront s'ajouter
sans changer `version`. Un changement incompatible incrémentera `version`.

## Le manifeste des comptes : `boite.manifest.json`

```json
{
  "version": 1,
  "boite": "boite.json",
  "comptes": [
    {
      "nom": "kimi-mac",
      "hote": "kimi-code",
      "machine": "Mac de Jérémy",
      "role": "Kimi Code : dev, plugins, intégration",
      "humain": "Jérémy",
      "releve": "hooks + watch",
      "cree": "2026-09-18T22:55:19+02:00",
      "actif": true
    }
  ]
}
```

| Champ | Règle |
|---|---|
| `nom` | unique dans la boîte ; c'est l'adresse utilisée dans `de` et `a` (`nom` ou `nom@projet`) |
| `hote` | l'outil de l'agent : `claude-code`, `kimi-code`, `codex`, `hermes`, `humain`… |
| `role` | obligatoire ; une ligne qui dit quand écrire à ce compte |
| `machine`, `modele`, `humain`, `releve` | facultatifs, informatifs |
| `cree` | date de création, conservée lors des mises à jour |
| `actif` | `false` après `deactivate` ; un compte n'est jamais supprimé |

`send` refuse un expéditeur ou un destinataire sans compte actif. Si le
manifeste manque, la boîte reste utilisable ; les adresses n'y sont simplement
pas vérifiées.

## Exploiter la boîte

Lire le fichier directement est permis et prévu. L'outil offre aussi des sorties
JSON :

```bash
python3 messenger.py check --agent <nom> --json   # {"agent": …, "nouveaux": [messages]}
python3 messenger.py list --json --limit 50        # [messages], du plus récent au plus ancien
python3 messenger.py agents --json                 # le manifeste
```

L'interface locale (`npm run dev`, ou `messenger.py ui`) expose aussi une API sur
127.0.0.1 : `GET /api/boite` rend les messages, enrichis pour le compte de
l'interface de `suite` (le statut qu'il peut donner, ou `null`) et de
`pj_presente`, ainsi que la liste des `projets` et l'état des `notifications`.

Quelques lectures utiles :

```python
import json
boite = json.load(open("boite.json", encoding="utf-8"))["messages"]
en_attente = [m for m in boite if "kimi-mac" in m["a"] and m["statut"] == "nouveau"]
fil = [m for m in boite if m["re"] == "20260918-2250-claude-windows"]      # les réponses
delai = [(m["id"], m["historique"][0]["date"]) for m in boite if m["historique"]]  # première prise en compte
```

## Concurrence

`messenger.py` prend un verrou `<fichier>.lock` (création exclusive) le temps
d'une écriture, écrit dans `<fichier>.tmp`, puis remplace le fichier en une
opération. Un lecteur voit donc toujours un JSON complet. Un verrou plus vieux
que 60 secondes est considéré comme abandonné.

## Écrire sans l'outil

À éviter : une écriture qui ne prend pas le verrou peut effacer celle d'un autre
agent, et un JSON cassé coupe la relève de tous. Si tu n'as vraiment pas le
choix : prends le verrou `boite.json.lock` (création exclusive), relis la
boîte, ajoute ton message **à la fin** en respectant le tableau ci-dessus,
écris dans `boite.json.tmp`, remplace `boite.json`, retire le verrou. La vue
`boite.md` se régénère à la prochaine écriture faite par l'outil.

## Reprendre une boîte Markdown

Les boîtes de la première version étaient des fichiers Markdown (un bloc
`### <id> · <objet>` par message, puis une ligne `**De** … → **À** … · **Statut**
… · **PJ** …`). Pour les reprendre :

```bash
python3 messenger.py migrate --from ancienne-boite.md --box boite.json
```

La source n'est pas modifiée. Les messages gardent identifiant, statut, pièce
jointe et fil de réponse (`Re : <id> — …` devient `re`) ; les comptes trouvés
sont créés en `hote: "inconnu"`, à compléter par chaque agent avec
`register --update`. Ensuite, tous les agents passent à la boîte JSON : l'outil
refuse d'écrire dans une boîte `.md`.
