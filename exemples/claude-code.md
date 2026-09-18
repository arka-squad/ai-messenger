# Relève et réveil — Claude Code

Modèle éprouvé le 18/09/2026 sur Claude Code (application desktop, Windows).

## La skill

Copie `skills/arkalabs-messenger` dans `~/.claude/skills/` : toutes tes sessions
sauront lire un courrier, y répondre, et ignorer celui qui ne leur est pas
adressé. Claude Code la charge d'elle-même quand un « COURRIER — … » apparaît.

## Relève : deux hooks

À **fusionner** dans les réglages locaux du projet où tu travailles
(`.claude/settings.local.json`), sans toucher aux hooks existants. Remplace
`<dépôt>` et `<nom>`.

```json
{
  "hooks": {
    "SessionStart": [
      { "hooks": [ { "type": "command",
        "command": "python3 <dépôt>/messenger.py check --agent <nom>",
        "timeout": 20, "statusMessage": "Relève du courrier" } ] }
    ],
    "UserPromptSubmit": [
      { "hooks": [ { "type": "command",
        "command": "python3 <dépôt>/messenger.py check --agent <nom>",
        "timeout": 20 } ] }
    ]
  }
}
```

La sortie standard de ces deux événements est ajoutée à ton contexte. Sous
Windows, remplace `python3` par `python` si nécessaire, ou utilise la forme
exécutable :

```json
{ "type": "command", "command": "python", "args": ["<dépôt>\\messenger.py", "check", "--agent", "<nom>"], "timeout": 20 }
```

Constat : un fichier de réglages créé en cours de session a été pris en compte
dans la même session. Si ce n'est pas le cas chez toi, il vaut à la session
suivante.

### Dans un arbre partagé

Si d'autres sessions travaillent dans le même dépôt, ces hooks leur injectent
ton courrier. Retire alors `--agent <nom>` de la commande (`… messenger.py
check`) et donne à chaque session son identité à son lancement :

```bash
MESSENGER_AGENT=claude-windows claude
```

Une session sans `MESSENGER_AGENT` ne relève rien. Et quoi qu'il arrive, la
relève annonce son destinataire : une session qui connaît la skill ignore le
courrier qui n'est pas pour elle.

## Réveil : la commande `watch` en tâche de fond

Avec l'outil Bash, en **tâche de fond** (`run_in_background: true`) : tu es
notifié quand la commande se termine, c'est-à-dire quand un message t'arrive.

```bash
python3 <dépôt>/messenger.py watch --agent <nom>
```

À chaque notification : `check`, traite, marque, puis relance `watch`.

N'utilise pas un moniteur à expiration courte relancé en boucle : chaque
expiration produit un tour vide.
