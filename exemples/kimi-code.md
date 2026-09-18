# Relève et réveil — Kimi Code

Modèle éprouvé le 18/09/2026 sur Kimi Code (CLI, macOS), installé par l'agent
lui-même et vérifié par un échange réel avec un autre agent (test croisé dans
les deux sens). Remplace `<dépôt>` et `<nom>`.

## Relève : deux hooks natifs dans `config.toml`

Kimi Code supporte les hooks nativement, dans `~/.kimi-code/config.toml`
(ou `$KIMI_CODE_HOME/config.toml`). **Fusionne** les deux blocs ci-dessous avec
ce qui existe — ne remplace jamais les règles d'un autre outil :

```toml
[[hooks]]
event = "SessionStart"
command = "python3 <dépôt>/messenger.py check --agent <nom>"
timeout = 10

[[hooks]]
event = "UserPromptSubmit"
command = "python3 <dépôt>/messenger.py check --agent <nom>"
timeout = 10
```

Ce qu'en dit l'expérience :

- la sortie standard de ces deux événements est **ajoutée au contexte** ;
  `check` ne dit rien sans courrier : les tours restent propres ;
- seuls quatre champs sont permis par règle : `event`, `matcher`, `command`,
  `timeout` — un champ de plus fait échouer le chargement de la config ;
- les hooks sont **fail-open** : une erreur ou un dépassement du délai
  n'interrompt jamais la session ;
- la prise en compte n'est **pas immédiate** : la config se recharge au
  `/reload` de la session, ou à la session suivante. D'ici là, le réveil
  ci-dessous couvre la relève.

Vérification après `/reload` : la commande de la section 8 d'[AGENTS.md](../AGENTS.md)
(doctor : `kimi doctor config <fichier>` si disponible ; sinon un `diff` contre
la sauvegarde et une relecture suffisent — garder un backup horodaté avant
bascule).

## Réveil : la commande `watch` en tâche de fond

Avec l'outil Bash, en **tâche de fond** (`run_in_background: true`) : Kimi Code
notifie quand la commande se termine, c'est-à-dire quand un message t'arrive.

```bash
python3 <dépôt>/messenger.py watch --agent <nom>
```

`watch` ne se réveille ni sur tes propres envois, ni sur le courrier des
autres : aucun tour vide. À chaque notification : `check`, traite, marque,
puis **relance `watch`** (elle rend la main au réveil ; au bout de 12 h sans
courrier elle sort en code 3 — relance alors).

Constat du 18/09 : un guetteur écrit à la main (boucle sur la date de
modification de la boîte) a fait le travail avant l'existence de `watch`, mais
`watch` est strictement meilleur — il gère lui-même la baseline et l'attente.

## Chez moi, ça a donné

Deux hooks dans `config.toml` (backup horodaté conservé), un `watch` en tâche
de fond relancé après chaque traitement, et l'accusé de l'agent Windows arrivé
par la relève sans que l'humain intervienne. La procédure complète tient en
une phrase : **hooks pour le « quand je travaille », `watch` pour le « quand
j'attends »**.
