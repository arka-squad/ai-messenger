# ARCHITECTURE.md

arkalabs-messenger suit une **architecture hexagonale** (ports et adaptateurs),
côté Python comme côté interface. Le domaine ne connaît ni fichier, ni ligne de
commande, ni navigateur : on peut changer de stockage ou d'interface sans
toucher aux règles.

```
                 adaptateurs pilotes                         adaptateurs pilotés
            (ce qui déclenche un cas d'usage)          (ce que les cas d'usage utilisent)

   CLI des agents ─┐                                    ┌─ boîte JSON (+ vue .md)
   (messenger.py)  │     ┌───────────────────────┐      ├─ annuaire JSON (manifeste)
                   ├───▶ │  application          │ ───▶ ├─ pièces jointes (dossier)
   API web locale ─┘     │  Messagerie + ports   │      ├─ ancienne boîte .md (lecture)
   (messenger.py ui)     │   ┌───────────────┐   │      └─ horloge système
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
| `domain/modele.py` | `Message` (immuable, seul son statut avance), `Brouillon` (un message validé, pas encore envoyé), `Boite` et `Annuaire` (les agrégats), `Compte`, et les règles : noms, deux lignes de corps, statut qui n'avance que par un destinataire et jamais en arrière |
| `domain/erreurs.py` | les refus, chacun avec un message qui dit quoi faire |
| `application/ports.py` | les interfaces attendues : `DepotBoite`, `DepotAnnuaire`, `PiecesJointes`, `Horloge`, `SourceAncienne` |
| `application/messagerie.py` | les cas d'usage : initialiser, inscrire, envoyer, relever, marquer, lister, guetter, importer |
| `adapters/codec.py` | le format d'échange JSON de [PROTOCOLE.md](PROTOCOLE.md) ; conserve les champs inconnus |
| `adapters/driven/` | boîte et annuaire en fichiers JSON (verrou, écriture atomique), vue Markdown, ancienne boîte Markdown en lecture seule, pièces jointes, horloge |
| `adapters/driving/cli.py` | la ligne de commande des agents |
| `adapters/driving/web.py` | l'API locale de l'interface (et l'interface construite) |
| `adapters/driving/poste.py` | la boîte mémorisée par `setup`, les variables d'environnement |
| `bootstrap.py` | l'assemblage : choisit les adaptateurs selon l'extension de la boîte |

`messenger.py`, à la racine, ne fait que rendre `src/` importable et appeler
`bootstrap.main` : aucune installation n'est nécessaire.

## L'interface — `ui/app/`

Même découpage, en TypeScript :

| Dossier | Rôle |
|---|---|
| `src/domain/` | les types de l'API et les dérivations pures : filtres, compteurs, agents, couloirs du trafic, fil |
| `src/application/` | les ports (`PortBoite`, `PortNotifications`, `PortPreferences`) et la `Veille`, qui relève la boîte sans rien savoir de React |
| `src/adapters/` | l'API HTTP, les notifications et le stockage du navigateur |
| `src/ui/` | les composants React et leur feuille de style |
| `src/main.tsx` | l'assemblage |
| `vite/api-messenger.ts` | le plugin qui lance l'API Python avec `npm run dev` |

**Les règles restent en Python.** L'interface ne décide jamais qui peut faire
avancer un statut : l'API le dit, message par message, dans le champ `suite`,
calculé par le domaine. L'interface affiche, filtre et demande ; le domaine
tranche.

`ui/messenger/` est la **maquette** d'origine : l'interface en reprend les
jetons de design (`tokens/`, `base/`) sans les copier.

## Choix structurants

- **Bibliothèque standard seulement, côté Python.** Un agent doit pouvoir faire
  tourner l'outil sur n'importe quel poste, sans rien installer. Node n'est
  nécessaire que pour développer l'interface.
- **Le fichier JSON est la source de vérité.** La vue `.md` est régénérée à
  chaque écriture et ne se relit jamais.
- **Chaque écriture relit la boîte sous verrou.** Une transaction ne travaille
  jamais sur un état périmé ; une erreur en cours de route n'écrit rien.
- **L'API n'écoute que 127.0.0.1**, refuse un hôte inconnu, et n'accepte une
  écriture que d'une page de même origine, en JSON.

## Étendre

Pour un nouveau stockage (une base, un service), implémente `DepotBoite` et
`DepotAnnuaire`, puis branche-les dans `bootstrap.Usine.ouvrir`. Pour une
nouvelle façon de piloter (un bot de messagerie, un serveur MCP), écris un
adaptateur dans `adapters/driving/` qui appelle `Messagerie`. Dans les deux
cas, le domaine et les cas d'usage ne changent pas.

## Tests

```bash
python3 -m unittest            # domaine, cas d'usage (doublures en mémoire), adaptateurs, CLI, API
npm test                       # domaine et veille du front
npm run typecheck              # TypeScript strict
```
