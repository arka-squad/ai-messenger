# PROTOCOLE.md — le format de la boîte

`messenger.py` écrit et lit ce format. Il est pensé pour être **lu par
programme** : un agent, un script ou un tableau de bord peut exploiter la boîte
sans analyser de texte. Pour **écrire**, passe par `messenger.py` (voir
[Écrire sans l'outil](#écrire-sans-loutil)).

## Les fichiers

Une boîte est un dossier **`.aimessenger/`**, dans un dossier partagé vu par toutes les
machines :

| Chemin | Rôle | Qui l'écrit |
|---|---|---|
| `.aimessenger/mail/boite.json` | les messages — **la source de vérité** | `send`, `mark` |
| `.aimessenger/manifest.json` | les comptes des agents | `register`, `enroll`, `deactivate` |
| `.aimessenger/boite.md` | vue lisible pour les humains, régénérée à chaque écriture | l'outil seul — **ne pas éditer** |
| `.aimessenger/onboarding.md` | guide d'accueil d'un agent invité (relève puis compte) ; les agents le cochent | `init`, puis les agents |
| `.aimessenger/pj/` | les pièces jointes, une par fichier | `send --attach` |

`init <dossier>` crée cette arbo ; l'interface aussi (bouton « Créer la boîte »). Tout est
en UTF-8, fins de ligne LF.

**Anciennes boîtes** (première version), toujours lisibles pour être migrées : un `boite.json`
à plat (avec `boite.manifest.json`, `boite.md` et les pièces jointes dans le même dossier) reste
inscriptible ; un `boite.md` seul s'ouvre en lecture seule. `migrate <dossier>` les reprend dans
une arbo `.aimessenger/` et y rapatrie les pièces jointes.

## La boîte : `boite.json`

```json
{
  "version": 1,
  "messages": [
    {
      "id": "20260918-2250-claude-windows",
      "date": "2026-09-18T22:50:12+02:00",
      "de": "claude-windows",
      "a": ["kimi-mac", "owner"],
      "objet": "Build 0.2.55 déposé",
      "corps": ["Installeurs signés, empreintes en pièce jointe.", "Rien à faire de ton côté."],
      "pj": "livraison-0.2.55.md",
      "re": null,
      "statut": "nouveau",
      "statuts": { "kimi-mac": "lu", "owner": "nouveau" },
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
| `statut` | texte | la **vue d'ensemble** : le statut le moins avancé de ses destinataires. Calculé, jamais écrit à la main |
| `statuts` | table | **le statut de chaque destinataire** : `{"<destinataire>": "nouveau"\|"lu"\|"traité"}`. C'est lui qui fait foi. Absent d'un message écrit avant cette version : tous les destinataires prennent alors son `statut` |
| `historique` | liste | chaque changement de statut : `date`, `par` (le compte qui agit), `statut` |
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

- **Un destinataire** fait avancer **son** statut, et seulement vers l'avant :
  `nouveau` → `lu` → `traité`. Chaque avancée s'ajoute à `historique`.
- **Le statut appartient à chaque destinataire.** Qu'un destinataire lise ne change
  rien pour les autres : le message reste `nouveau` pour eux, donc leur relève et
  leur veille le voient toujours. Un message écrit à dix comptes est dix attentes,
  pas une. `statut` n'est que la vue d'ensemble : `traité` seulement quand tous
  l'ont traité.
- Rien d'autre ne se modifie. Une correction est un nouveau message, relié par
  `re`.

Un lecteur doit **ignorer les champs qu'il ne connaît pas**, et un écrivain doit
**les conserver** — `messenger.py` le fait, au niveau de la boîte, de chaque
message et de chaque compte : de nouveaux champs facultatifs pourront s'ajouter
sans changer `version`. Un changement incompatible incrémentera `version`.

## Le manifeste des comptes : `manifest.json`

(`boite.manifest.json` pour une ancienne boîte à plat.)

```json
{
  "version": 1,
  "boite": "boite.json",
  "comptes": [
    {
      "nom": "km-agent-plugins-mac@talos",
      "hote": "kimi-code",
      "machine": "mac-studio",
      "role": "Kimi Code : dev, plugins, intégration",
      "affichage": "KM_Agent-Plugins_MAC",
      "humain": "Camille",
      "releve": "hooks + watch",
      "cree": "2026-09-18T22:55:19+02:00",
      "actif": true,
      "contacts": [
        { "alias": "release", "adresses": ["cl-agent-release-win@cortex", "owner"],
          "note": "la chaîne de release", "cree": "2026-09-20T12:40:00+02:00" }
      ]
    }
  ],
  "projets": [
    { "nom": "talos", "cree": "2026-09-20T12:30:00+02:00" }
  ]
}
```

| Champ | Règle |
|---|---|
| `nom` | unique dans la boîte ; c'est l'adresse utilisée dans `de` et `a` (`nom` ou `nom@projet`) |
| `hote` | l'outil de l'agent : `claude-code`, `kimi-code`, `codex`, `hermes`, `humain`… |
| `role` | obligatoire ; une ligne qui dit quand écrire à ce compte |
| `affichage` | facultatif ; le nom lisible pour un humain (`KM_Agent-Plugins_MAC`), posé par `enroll`. L'adresse reste `nom` |
| `machine`, `modele`, `humain`, `releve` | facultatifs, informatifs |
| `cree` | date de création, conservée lors des mises à jour |
| `actif` | `false` après `deactivate` ; un compte n'est jamais supprimé |
| `fusionne_dans` | facultatif ; l'adresse du compte qui a **absorbé** celui-ci (`merge`, ou la fiche de l'agent dans l'interface). Le compte est désactivé ; sa relève, son courrier « nouveau » et tout envoi vers son adresse vont au compte nommé (les fusions se suivent en chaîne). Les messages déjà envoyés ne changent pas : l'historique reste vrai |
| `projet` | facultatif, seulement pour une adresse **sans** `@projet` : le projet où l'humain a rangé ce compte commun (`attach`, ou la fiche de l'agent dans l'interface). L'adresse ne change pas ; le compte compte dès lors parmi ceux du projet (groupes, filtres, résolution des noms courts) |
| `contacts` | facultatif ; le **carnet d'adresses** du compte, que lui seul modifie (`contact-add`, `contact-remove`). Un `alias` (même forme qu'un nom) désigne une ou plusieurs `adresses` complètes, 20 au plus ; `note` tient en une ligne de 200 caractères ; 200 contacts au plus |

`projets` (facultatif) liste les projets **connectés** à la boîte par `activate` ou « Connecter un
projet » : un projet est ainsi connu, et montré par l'interface, avant qu'un agent s'y enrôle. Les
projets d'une boîte sont ceux-là, ceux des comptes et ceux vus dans les messages.

**Un alias n'entre jamais dans la boîte.** À l'envoi, un destinataire au nom court est cherché parmi
les comptes du projet de l'expéditeur, puis parmi les comptes communs, et seulement ensuite dans le
carnet de l'expéditeur ; l'alias est alors remplacé par ses adresses, et le message enregistre les
adresses réelles dans `a`. Un compte l'emporte donc toujours sur un alias : on ne peut pas noter un
alias qui est déjà l'adresse d'un compte, et si un compte homonyme est créé plus tard, c'est lui
qui reçoit (`contacts` signale l'alias masqué).

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

L'interface locale (`npm run dev`, ou `messenger.py start`) expose aussi une API sur
127.0.0.1 : `GET /api/boite` rend les messages, enrichis pour le compte de
l'interface de `suite` (le statut qu'il peut donner, ou `null`), de `mien` (où en
est ce message **pour lui** : son propre statut s'il en est destinataire, sinon la
vue d'ensemble) et de `pj_presente`, ainsi que la liste des `projets`, l'état des `notifications` et
l'`invite` — le texte à coller à un agent pour qu'il s'enrôle (`null` sans vraie boîte).
Les écritures (`POST /api/statut`, `/api/notifications`, `/api/creer`, `/api/activer`,
`/api/choisir-dossier`, `/api/boite-du-poste`, `/api/invite`, `/api/rattacher`, `/api/contact`,
`/api/contact-retirer`, `/api/fusionner`, `/api/preparer`, `/api/eteindre`) n'acceptent qu'une
requête JSON venue de l'interface elle-même.
`GET /api/version` rend l'empreinte de la boîte **et de son manifeste** (elle change à chaque écriture de
l'un ou de l'autre), avec `outil: "arkalabs-messenger"` — c'est ainsi que `start` reconnaît une boîte déjà
allumée. `GET /api/poste` dit où en sont les outils d'IA du poste et si la boîte peut être éteinte d'ici ;
`POST /api/preparer` les équipe, `POST /api/eteindre` arrête une boîte allumée par `start`. Pour organiser :
`POST /api/invite` (`{"projet": "<nom>"|null}` — le projet est créé au besoin — ou `{"compte": "<adresse>"}`)
rend le texte à coller à un agent ; `POST /api/rattacher` (`{"compte", "projet"|null}`), `POST /api/contact`
(`{"compte", "alias", "adresses", "note"?, "remplacer"?}`), `POST /api/contact-retirer` (`{"compte", "alias"}`)
et `POST /api/fusionner` (`{"compte", "dans"}` — fusionne deux comptes d'un même agent).
`POST /api/boite-du-poste` (`{"dossier"}`) dit à ce poste où est la boîte : un dossier à arbo
`.aimessenger/`, un dossier contenant un `boite.json` à plat, ou le fichier lui-même.
`POST /api/activer` rend le dépôt connecté et, pour chaque hôte IA du poste, où il en est
(`hotes` : `id`, `nom`, `present`, `equipe`, `mcp`, `releve`, `skill`, `note`).

Enfin, `messenger.py mcp` expose la boîte à un hôte IA par le **Model Context Protocol**
(JSON-RPC 2.0 sur l'entrée et la sortie standard, un message par ligne ; versions
`2025-06-18`, `2025-03-26`, `2024-11-05`) : les outils `whoami`, `enroll`, `identify`,
`check`, `list`, `read`, `send`, `reply`, `mark`, `agents`, `contacts`, `contact_add`,
`contact_remove`, `wait`, et les ressources
`messenger://boite`, `messenger://comptes`, `messenger://accueil`. Un refus du domaine
(destinataire inconnu, statut qui recule…) revient comme un résultat d'outil `isError`,
avec le même message que la ligne de commande ; une requête mal formée, comme une erreur
JSON-RPC. Les règles sont celles de ce document : le serveur n'en ajoute ni n'en lève aucune.

Quelques lectures utiles :

```python
import json
# le chemin dépend de la disposition : `.aimessenger/mail/boite.json`, ou `boite.json` à plat
boite = json.load(open(".aimessenger/mail/boite.json", encoding="utf-8"))["messages"]
# le statut qui compte est le sien : `statuts`, avec repli sur `statut` pour un message d'avant
en_attente = [m for m in boite
              if m.get("statuts", {}).get("kimi-mac", m["statut"] if "kimi-mac" in m["a"] else None) == "nouveau"]
fil = [m for m in boite if m["re"] == "20260918-2250-claude-windows"]      # les réponses
delai = [(m["id"], m["historique"][0]["date"]) for m in boite if m["historique"]]  # première prise en compte
```

## Concurrence

`messenger.py` prend un verrou `<fichier>.lock` (création exclusive) le temps
d'une écriture, écrit dans `<fichier>.tmp`, puis remplace le fichier en une
opération. Un lecteur voit donc toujours un JSON complet. Un verrou plus vieux
que 60 secondes est considéré comme abandonné.

**Une boîte ne rétrécit jamais.** Un message n'est jamais retiré : seul son statut avance. L'outil
s'en sert comme garde-fou : chaque poste retient, dans son dossier personnel
(`~/.arkalabs-messenger.temoins.json`, à côté de `~/.arkalabs-messenger.json` et du dossier
`~/.arkalabs-messenger.veilles/`), le plus grand nombre de messages qu'il a lu dans chaque
boîte. Si une relecture en rend moins, l'écriture est **refusée** — ce n'est pas la boîte qui a
maigri, c'est la lecture qui est fausse. Le témoin est local et ne voyage pas avec la boîte : il
protège la boîte contre *ce poste-là* lorsqu'il lit mal, pas contre les autres.

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
python3 messenger.py migrate --from ancienne-boite.md --box /chemin/partagé
```

La source n'est pas modifiée. Les messages gardent identifiant, statut, pièce
jointe et fil de réponse (`Re : <id> — …` devient `re`) ; les comptes trouvés
sont créés en `hote: "inconnu"`, à compléter par chaque agent avec
`register --update`. Ensuite, tous les agents passent à la boîte JSON : l'outil
refuse d'écrire dans une boîte `.md`.
