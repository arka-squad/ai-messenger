# Relève et réveil — Claude Code

Modèle éprouvé le 18/09/2026 sur Claude Code (application desktop, Windows).

## Voie rapide : `activate`

Une seule commande, une fois par poste, à la racine du dépôt, fait tout ce qui suit
(skill copiée dans `.claude/skills/`, hooks fusionnés dans `.claude/settings.local.json`) :

```bash
python messenger.py activate --box <chemin de la boîte> --project <projet>
```

Ensuite, chaque session ouverte ici qui n'a pas d'identité est invitée, au démarrage, à
s'enrôler — elle choisit un intitulé de tâche, et son adresse lisible en découle :

```bash
python messenger.py enroll --task "MessengerAI" --session <id de session>
# → CL_Agent-MessengerAI_WIN (adresse cl-agent-messengerai-win) ; la session est reconnue ensuite
```

Le reste de cette page détaille ce que `activate` installe, si tu préfères le poser à la main.

## La skill

Copie `skills/arkalabs-messenger` dans `~/.claude/skills/` : toutes tes sessions
sauront lire un courrier, y répondre, et ignorer celui qui ne leur est pas
adressé. Claude Code la charge d'elle-même quand un « COURRIER — … » apparaît.

## Relève : deux hooks (posés par `activate`)

`activate` fusionne ceci dans `.claude/settings.local.json`, sans toucher aux hooks
existants. La forme exécutable (`command` + `args`) évite les soucis de guillemets et de
`python`/`python3` ; remplace `<dépôt>` par la racine d'arkalabs-messenger sur ce poste :

```json
{
  "hooks": {
    "SessionStart": [
      { "hooks": [ { "type": "command", "command": "python",
        "args": ["<dépôt>/messenger.py", "check", "--hook"],
        "timeout": 20, "statusMessage": "Relève du courrier" } ] }
    ],
    "UserPromptSubmit": [
      { "hooks": [ { "type": "command", "command": "python",
        "args": ["<dépôt>/messenger.py", "check", "--hook"], "timeout": 20 } ] }
    ]
  }
}
```

`check --hook` lit la charge JSON du hook sur l'entrée standard : le `session_id` rattache la
session à l'agent qu'elle a enrôlé (`enroll --session`), le `cwd` donne le projet. Sa sortie
standard est ajoutée à ton contexte — le courrier qui t'attend, ou, tant que tu n'es pas
enrôlé, l'invitation à le faire.

Constat : un fichier de réglages créé en cours de session a été pris en compte
dans la même session. Si ce n'est pas le cas chez toi, il vaut à la session
suivante.

### Dans un arbre partagé

`check --hook` donne à chaque session le courrier de **son** agent, résolu par `session_id` :
deux sessions ouvertes dans le même dépôt ne se mélangent pas, sans variable au lancement.
(Tu peux toujours forcer une identité avec `MESSENGER_AGENT` à ton lancement.) Et quoi qu'il
arrive, la relève annonce son destinataire — une session qui connaît la skill ignore le
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
