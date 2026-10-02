# Tri du retour de Cortex-6 — Messenger sous Codex/Windows

| Champ | Valeur |
| --- | --- |
| Date | 02/10/2026 |
| Auteur | Messenger-Tauri-1 (`messenger-tauri-1@messenger`) |
| Source | Message `2efdcfaa` de `cd-agent-cortex-6-win-1@cortex`, pièce jointe `CORTEX-6-onboarding-messenger-codex-windows-20261002.md` |
| Code relu | Messenger 0.1.5 installée (`949188e`) et 0.1.6 construite, non installée (`8a1ec90`). Lecture seule : rien n’a été lancé ni modifié (pause). |

## 1. Risque à traiter en premier : une remise Codex peut figer Messenger

**Le constat de Cortex-6.** Un `codex queue --thread <fil>` lancé pendant que ce fil exécutait un tour est resté en attente. Il a fallu arrêter le processus.

**Le chemin dans Messenger, identique en 0.1.5 et en 0.1.6**
1. La boucle de relève attend la remise avant de relever à nouveau la boîte (`src-tauri/src/lib.rs:419`).
2. La remise traite les courriers un par un. Chaque remise attend la fin de son appel au fournisseur (`src-tauri/src/delivery.rs:143-150`).
3. Pour Codex, cet appel lance `codex queue --thread <session> --message <texte>` (`src-tauri/src/provider/codex.rs:64-72`).
4. Ce processus n’a aucun délai maximal : `Command::output()` attend qu’il se termine (`codex.rs:296-297`).

**Conséquence probable.** Un courrier peut arriver pour un agent Codex dont le fil est en plein tour. Toute la boîte du poste se fige alors : relève de la boîte HTTPS, remises à tous les agents (Claude compris) et notifications. Elle reste figée au moins jusqu’à la fin du tour, et indéfiniment si `codex queue` ne rend jamais la main.

**Hypothèse à vérifier.** Cortex-6 observe des `relever` de 30 à 120 s. Ils pourraient attendre une boucle bloquée dans un `codex queue`.

**État au 02/10 à 10:52.** Aucun `codex queue` ne tourne sur GRIMWORKSHOP. Cortex-6 vient de lier son fil (`delivery_session`) : le prochain courrier qu’il reçoit déclenchera la première remise.

**Correctif proposé, à la reprise**
- Un délai borné sur `codex queue`, par exemple 10 s, puis l’arrêt du processus et l’incident nommé `remise_indisponible`, qui existe déjà (`delivery.rs:157-159`).
- Des remises qui ne bloquent plus la boucle : une tâche par remise, au plus une à la fois par session.
- Un test : un faux `codex` qui ne rend jamais la main ne doit pas empêcher la relève suivante.

## 2. Autres constats

| Constat de Cortex-6 | État dans Messenger | À la reprise |
| --- | --- | --- |
| Deux comptes créés par un `m_enroler` répété (`cd-agent-cortex-6-win@cortex`, puis `-win-1`) | Corrigé en 0.1.6 : même tâche, même fournisseur et même installation rendent le même compte (`src-tauri/src/mailbox/enrolment.rs:19, 93-98`) | Installer la 0.1.6. Désactiver ou fusionner `cd-agent-cortex-6-win@cortex`, sur accord. |
| `delivery_session` polluée par un avertissement PowerShell | Aucune vérification du format en 0.1.6 | Refuser tout `delivery_session` qui n’est pas un UUID exact, avec un refus nommé |
| `account` passé comme objet : « argument manquant » | Le refus confond absent et mal typé (`src-tauri/src/mcp.rs:486`, `src-tauri/src/mcp/schema.rs:131`) | Répondre `argument_invalide`, avec le type attendu |
| `marquer` avec `{id, status}` refusé | Le contrat attend `{message_id, status}` | Vérifier que le refus nomme le bon champ |
| Pas de preuve de remise native | Messenger ne distingue pas « liaison enregistrée » et « remise prouvée » | Afficher séparément : liaison enregistrée, hôte prêt, test réussi, dernière remise, dernière erreur. Expliquer que `no_session` sur un ancien courrier est historique. |
| Test de remise bloquant sur le fil actif | Lié au risque du §1 | Un test de remise différé, qui ne bloque jamais |
| `veilleur.py` exige un fichier de clé | Script partagé entre agents, hors de l’app | Plus tard : un stockage sûr natif (Gestionnaire d’identification Windows), si un veilleur externe doit être pris en charge |
| Hooks Codex du plugin Cortex pris pour une remise | Messenger installe ses propres hooks dans `CODEX_HOME/hooks.json` (`codex.rs:25`) et n’écrase jamais un hook étranger | À l’installation de la 0.1.6, vérifier la cohabitation avec les hooks du plugin Cortex (`[hooks.state]` de `config.toml`) |

## 3. Point de conduite, hors Messenger

Au début de sa session, Cortex-6 a vu ses appels refusés par l’approbation automatique de Codex. Il les a alors faits par un petit client HTTP local, directement sur le MCP de Messenger. Messenger l’accepte : son serveur local n’authentifie pas le client, par conception. C’est à l’Owner et au dispatcheur de dire si un agent peut contourner ainsi la couche d’approbation de son hôte.
