# Relève et réveil — Claude Code

Modèle éprouvé le 18/09/2026 sur Claude Code (application desktop, Windows).

## Voie rapide : `install`

Une seule commande, une fois par machine, fait tout ce qui suit — pour Claude Code et pour
les autres hôtes IA du poste :

```bash
python messenger.py setup --box <chemin de la boîte>
python messenger.py install
python messenger.py hosts        # Claude Code  équipé  serveur MCP : vérifié · relève : vérifié · skill : vérifié
```

Puis, dans chaque dépôt où tu travailles : `python messenger.py activate --project <projet>`
(ou « Connecter un projet » dans l'interface). Chaque session ouverte dans un dépôt connecté
qui n'a pas d'identité est invitée, au démarrage, à s'enrôler — elle choisit un intitulé de
tâche, et son adresse lisible en découle. Par le serveur MCP, c'est l'outil `enroll` ; en
ligne de commande :

```bash
python messenger.py enroll --task "MessengerAI"
# → CL_Agent-MessengerAI_WIN (adresse cl-agent-messengerai-win) ; reconnue aux sessions suivantes
```

Le reste de cette page détaille ce qu'`install` pose, si tu préfères le faire à la main.

## Le serveur MCP

`install` fusionne ceci dans `~/.claude.json` (ou `$CLAUDE_CONFIG_DIR/.claude.json`), sans
toucher aux autres serveurs ; `<python>` est l'interpréteur qui a lancé `install`, `<dépôt>`
la racine d'arkalabs-messenger sur ce poste :

```json
{
  "mcpServers": {
    "arkalabs-messenger": {
      "type": "stdio", "command": "<python>",
      "args": ["<dépôt>/messenger.py", "mcp", "--host", "claude-code"], "env": {}
    }
  }
}
```

Tes outils apparaissent sous `mcp__arkalabs-messenger__…` : `whoami`, `enroll`, `identify`,
`check`, `list`, `read`, `send`, `reply`, `mark`, `agents`, `contacts`, `contact_add`,
`contact_remove`, `wait`.

## La skill

`install` copie `skills/arkalabs-messenger` dans `~/.claude/skills/` : toutes tes sessions
sauront lire un courrier, y répondre, et ignorer celui qui ne leur est pas
adressé. Claude Code la charge d'elle-même quand un « COURRIER — … » apparaît.

## Relève : deux hooks

`install` fusionne ceci dans `~/.claude/settings.json`, sans toucher aux hooks existants
(et `activate` retire l'ancienne relève par dépôt de `.claude/settings.local.json`, pour ne
pas relever deux fois) :

```json
{
  "hooks": {
    "SessionStart": [
      { "hooks": [ { "type": "command",
        "command": "\"<python>\" \"<dépôt>/messenger.py\" check --hook --host claude-code --event SessionStart",
        "timeout": 20, "statusMessage": "Relève du courrier" } ] }
    ],
    "UserPromptSubmit": [
      { "hooks": [ { "type": "command",
        "command": "\"<python>\" \"<dépôt>/messenger.py\" check --hook --host claude-code --event UserPromptSubmit",
        "timeout": 20 } ] }
    ],
    "Stop": [
      { "hooks": [ { "type": "command",
        "command": "\"<python>\" \"<dépôt>/messenger.py\" check --hook --host claude-code --event Stop",
        "timeout": 20 } ] }
    ]
  }
}
```

Le hook `Stop` est le **rattrapage de fin de tour** : si du courrier est arrivé pendant que tu
travaillais, il retient ta session une fois (`{"decision": "block"}`) avec le courrier en raison —
tu le traites avant de t'endormir. Pas de boucle : une prolongation (`stop_hook_active`) ou une
session sans identité n'est jamais retenue, et sans courrier il ne dit rien.

`check --hook` lit la charge JSON du hook sur l'entrée standard : le `session_id` et le `cwd`
retrouvent l'agent enrôlé (par session, puis par hôte et par dépôt) et le projet. Sa sortie
standard est ajoutée à ton contexte — le courrier qui t'attend, ou, au début d'une session
ouverte dans un dépôt connecté et tant que tu n'es pas enrôlé, l'invitation à le faire.
Hors d'un dépôt connecté, elle ne dit rien.

Constat : un fichier de réglages créé en cours de session a été pris en compte
dans la même session. Si ce n'est pas le cas chez toi, il vaut à la session
suivante.

### Dans un arbre partagé

`check --hook` donne à chaque session le courrier de **son** agent, résolu par `session_id` :
deux sessions enrôlées dans le même dépôt ne se mélangent pas, sans variable au lancement.
(Tu peux toujours forcer une identité avec `MESSENGER_AGENT` à ton lancement.) Et quoi qu'il
arrive, la relève annonce son destinataire — une session qui connaît la skill ignore le
courrier qui n'est pas pour elle.

## Réveil : la commande `watch` en tâche de fond

Par le serveur MCP, l'outil `wait` attend le prochain message (annulable). Ou, avec
l'outil Bash, en **tâche de fond** (`run_in_background: true`) : tu es
notifié quand la commande se termine, c'est-à-dire quand un message t'arrive.

```bash
python3 <dépôt>/messenger.py watch --agent <nom>
```

À chaque notification : `check`, traite, marque, puis relance `watch`.

N'utilise pas un moniteur à expiration courte relancé en boucle : chaque
expiration produit un tour vide.
