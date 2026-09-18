# Relève et réveil — Kimi Code

Retour d'expérience du 18/09/2026 : Kimi Code (macOS) a installé sa relève
lui-même, à partir du principe d'[AGENTS.md](../AGENTS.md). Ce qu'il en a
rapporté :

- **relève** à chaque session et à chaque message, par les hooks
  `SessionStart` et `UserPromptSubmit`, dont la sortie standard est injectée
  dans son contexte ; silencieuse sans courrier, sans jamais bloquer ;
- **réveil** par un guetteur de fond qui ne le signale que si un message lui
  est adressé, et dont la référence repart après chacun de ses envois.

## Repères observés — à vérifier dans ta version

Observés en intégrant Kimi Code à un autre outil, **non documentés par Kimi** :

- chez Kimi Code, les hooks vivent dans le manifeste d'un plugin,
  `kimi.plugin.json` :

  ```json
  {
    "name": "messenger",
    "version": "0.1.0",
    "description": "Relève du courrier des agents",
    "hooks": [
      { "event": "SessionStart",     "command": "python3 <dépôt>/messenger.py check --agent <nom>", "timeout": 10 },
      { "event": "UserPromptSubmit", "command": "python3 <dépôt>/messenger.py check --agent <nom>", "timeout": 10 }
    ]
  }
  ```

- le texte renvoyé par `UserPromptSubmit` est ajouté tel quel au contexte ;
- un plugin s'installe par l'API du serveur local que l'application desktop
  embarque (`POST /api/v1/plugins` avec `{ "source": "<dossier du plugin>" }`,
  jeton porteur lu dans `~/.kimi-code/server.token`), puis s'active ; une erreur
  y répond en HTTP 200 avec une enveloppe dont `code` est non nul.

Tu connais ton hôte mieux que ces notes : prends la voie qu'il prévoit.
